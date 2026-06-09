"""Valida ERA5-Land frente a observaciones AEMET seleccionadas.

Uso en el pipeline:
    Script auxiliar de validacion externa en Ingenieria del Dato.

Entradas:
    DATA/PROCESSED/dataset_cv_municipios.csv
    API de AEMET OpenData configurada mediante variable de entorno o argumento.

Salidas:
    DATA/PROCESSED/aemet_selected_stations_cv.csv
    DATA/PROCESSED/aemet_daily_raw_selected.csv
    DATA/PROCESSED/aemet_vs_era5_daily_comparison.csv
    DATA/PROCESSED/aemet_vs_era5_metrics.csv

Notas:
    Requiere red y API key de AEMET. Su objetivo es contrastar la coherencia
    climatica de ERA5-Land, no sustituir la fuente principal.
"""

from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import pandas as pd
import requests


BASE_URL = "https://opendata.aemet.es/opendata/api"
DEFAULT_START = "2024-07-01"
DEFAULT_END = "2024-10-31"
DEFAULT_STATIONS = "8501,8058X"
PROV_MAP = {
    "ES521": "ALICANTE",
    "ES522": "CASTELLON",
    "ES523": "VALENCIA",
}
STATION_MUNICIPALITY_OVERRIDES = {
    # AEMET labels this station as CASTELLO DE LA PLANA. In the cached spatial
    # assignment it had been joined to Onda, which distorted the ERA5 contrast.
    "8501": {
        "municipio": "Castell\u00f3 de la Plana/Castell\u00f3n de la Plana",
        "CODNUT3": "ES522",
        "CODNUT3_prov": "ES522",
    },
    "8058X": {
        "municipio": "Oliva",
        "CODNUT3": "ES523",
        "CODNUT3_prov": "ES523",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Descarga una muestra acotada de AEMET OpenData y valida "
            "ERA5 municipal frente a estaciones seleccionadas de la CV."
        )
    )
    parser.add_argument(
        "--start",
        default=DEFAULT_START,
        help=(
            "Fecha inicial en formato YYYY-MM-DD. Por defecto reproduce "
            "la validacion documentada en el notebook 2."
        ),
    )
    parser.add_argument(
        "--end",
        default=DEFAULT_END,
        help=(
            "Fecha final en formato YYYY-MM-DD. Por defecto reproduce "
            "la validacion documentada en el notebook 2."
        ),
    )
    parser.add_argument(
        "--api-key-env",
        default="AEMET_API_KEY",
        help="Variable de entorno que contiene la API key de AEMET.",
    )
    parser.add_argument(
        "--output-dir",
        default="DATA/PROCESSED",
        help="Directorio donde guardar salidas CSV, relativo a la raiz del proyecto.",
    )
    parser.add_argument(
        "--stations",
        default=DEFAULT_STATIONS,
        help=(
            "Lista opcional de indicativos AEMET separados por comas. "
            "Por defecto usa las estaciones de referencia documentadas. "
            "Si se deja vacio, el script selecciona una estacion por provincia."
        ),
    )
    parser.add_argument(
        "--chunk-days",
        type=int,
        default=31,
        help="Numero maximo de dias por peticion diaria a AEMET.",
    )
    return parser.parse_args()


def get_api_key(env_var: str) -> str:
    api_key = os.getenv(env_var, "").strip()
    if not api_key:
        raise ValueError(
            f"No se encontro la API key en la variable de entorno {env_var!r}."
        )
    return api_key


def request_aemet_json(
    endpoint: str, api_key: str, allow_empty: bool = False
) -> list[dict]:
    resp = requests.get(
        f"{BASE_URL}{endpoint}",
        params={"api_key": api_key},
        timeout=60,
    )
    resp.raise_for_status()
    meta = resp.json()
    if "datos" not in meta:
        if allow_empty and meta.get("estado") == 404:
            return []
        raise RuntimeError(f"Respuesta inesperada de AEMET: {meta}")

    data_resp = requests.get(meta["datos"], timeout=120)
    data_resp.raise_for_status()
    data = data_resp.json()
    if not isinstance(data, list):
        raise RuntimeError(f"Respuesta de datos inesperada: {data}")
    return data


def dms_to_decimal(value: str) -> float:
    value = str(value).strip().upper()
    if not value:
        return math.nan

    hem = value[-1]
    body = value[:-1]

    if hem in {"N", "S"}:
        deg, minutes, seconds = int(body[:2]), int(body[2:4]), int(body[4:6])
    elif hem in {"E", "W"}:
        deg, minutes, seconds = int(body[:3]), int(body[3:5]), int(body[5:7])
    else:
        raise ValueError(f"Formato DMS no reconocido: {value}")

    decimal = deg + minutes / 60 + seconds / 3600
    if hem in {"S", "W"}:
        decimal *= -1
    return decimal


def parse_number(value: object) -> float:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return math.nan

    text = str(value).strip()
    if not text:
        return math.nan
    if text.lower() == "ip":
        return 0.0

    text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return math.nan


def load_cv_inputs(root: Path) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    gdf_cv = gpd.read_file(root / "DATA" / "EXTERNAL" / "municipios_cv.geojson")
    if gdf_cv.crs is None or gdf_cv.crs.to_string() != "EPSG:4326":
        gdf_cv = gdf_cv.to_crs(4326)

    df_municipios = pd.read_csv(
        root / "DATA" / "PROCESSED" / "dataset_cv_municipios.csv",
        parse_dates=["fecha"],
    )
    return gdf_cv, df_municipios


def build_station_gdf(stations: Iterable[dict]) -> gpd.GeoDataFrame:
    df = pd.DataFrame(stations)
    df["lon"] = df["longitud"].map(dms_to_decimal)
    df["lat"] = df["latitud"].map(dms_to_decimal)
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["lon"], df["lat"]),
        crs="EPSG:4326",
    )
    return gdf


def select_stations(
    gdf_stations_cv: gpd.GeoDataFrame,
    gdf_cv: gpd.GeoDataFrame,
    station_ids: list[str],
) -> gpd.GeoDataFrame:
    if station_ids:
        selected = gdf_stations_cv[
            gdf_stations_cv["indicativo"].isin(station_ids)
        ].copy()
        if selected.empty:
            raise ValueError(
                "No se encontro ninguna estacion AEMET con los indicativos pedidos."
            )
        return selected

    # Keep only province geometry here. If municipal columns from the dissolved
    # layer remain on the left side of the nearest join, they can overwrite the
    # actual station municipality and corrupt the ERA5 merge.
    gdf_prov = gdf_cv[["CODNUT3", "geometry"]].dissolve(by="CODNUT3").reset_index()
    gdf_prov["CODNUT3_prov"] = gdf_prov["CODNUT3"]
    gdf_prov["rep_point"] = gdf_prov.representative_point()
    gdf_prov = gpd.GeoDataFrame(
        gdf_prov[["CODNUT3_prov", "rep_point"]],
        geometry=gdf_prov["rep_point"],
        crs="EPSG:4326",
    ).drop(columns="rep_point")

    stations_proj = gdf_stations_cv.to_crs(25830)
    prov_proj = gdf_prov.to_crs(25830)

    selected_parts = []
    for codnut3 in sorted(gdf_prov["CODNUT3_prov"].dropna().unique()):
        station_subset = stations_proj[stations_proj["CODNUT3"] == codnut3].copy()
        if station_subset.empty:
            continue

        target = prov_proj.loc[prov_proj["CODNUT3_prov"] == codnut3].copy()
        nearest = gpd.sjoin_nearest(
            target,
            station_subset[
                [
                    "indicativo",
                    "nombre",
                    "provincia",
                    "altitud",
                    "municipio",
                    "CODNUT3",
                    "geometry",
                ]
            ],
            how="left",
            distance_col="dist_ref_m",
        )
        selected_parts.append(nearest.to_crs(4326))

    if not selected_parts:
        raise ValueError("No se pudieron seleccionar estaciones AEMET en la CV.")

    selected = pd.concat(selected_parts, ignore_index=True)
    selected = gpd.GeoDataFrame(selected, geometry="geometry", crs="EPSG:4326")
    selected = selected[
        [
            "indicativo",
            "nombre",
            "provincia",
            "altitud",
            "municipio",
            "CODNUT3",
            "CODNUT3_prov",
            "dist_ref_m",
            "geometry",
        ]
    ].copy()
    selected = apply_station_municipality_overrides(selected)
    return selected


def apply_station_municipality_overrides(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["indicativo"] = df["indicativo"].astype(str)
    for station_id, values in STATION_MUNICIPALITY_OVERRIDES.items():
        mask = df["indicativo"] == station_id
        if not mask.any():
            continue
        for col, value in values.items():
            if col not in df.columns:
                df[col] = pd.NA
            df.loc[mask, col] = value
    return df


def date_chunks(start: str, end: str, chunk_days: int) -> Iterable[tuple[str, str]]:
    start_date = pd.Timestamp(start).normalize()
    end_date = pd.Timestamp(end).normalize()
    if end_date < start_date:
        raise ValueError("La fecha final no puede ser anterior a la inicial.")
    if chunk_days < 1:
        raise ValueError("--chunk-days debe ser mayor o igual que 1.")

    current = start_date
    while current <= end_date:
        chunk_end = min(current + pd.Timedelta(days=chunk_days - 1), end_date)
        yield current.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")
        current = chunk_end + pd.Timedelta(days=1)


def fetch_daily_station_chunk(
    station_id: str, start: str, end: str, api_key: str
) -> pd.DataFrame:
    endpoint = (
        "/valores/climatologicos/diarios/datos/"
        f"fechaini/{start}T00:00:00UTC/"
        f"fechafin/{end}T23:59:59UTC/"
        f"estacion/{station_id}"
    )
    rows = request_aemet_json(endpoint, api_key, allow_empty=True)
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["fecha"] = pd.to_datetime(df["fecha"])
    if "tmed" in df.columns:
        df["tmed"] = df["tmed"].map(parse_number)
    else:
        df["tmed"] = math.nan
    if "prec" in df.columns:
        df["prec"] = df["prec"].map(parse_number)
    else:
        df["prec"] = math.nan
    df["indicativo"] = station_id
    return df


def fetch_daily_station_data(
    station_id: str, start: str, end: str, api_key: str, chunk_days: int
) -> pd.DataFrame:
    parts = []
    for chunk_start, chunk_end in date_chunks(start, end, chunk_days):
        df_chunk = fetch_daily_station_chunk(
            station_id,
            chunk_start,
            chunk_end,
            api_key,
        )
        if not df_chunk.empty:
            parts.append(df_chunk)

    if not parts:
        return pd.DataFrame()

    return (
        pd.concat(parts, ignore_index=True)
        .drop_duplicates(subset=["indicativo", "fecha"])
        .sort_values(["indicativo", "fecha"])
        .reset_index(drop=True)
    )


def build_validation_table(
    selected_stations: gpd.GeoDataFrame,
    df_municipios: pd.DataFrame,
    start: str,
    end: str,
    api_key: str,
    chunk_days: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    selected_stations = selected_stations.copy()
    selected_stations["indicativo"] = selected_stations["indicativo"].astype(str)

    all_daily = []
    for station_id in selected_stations["indicativo"].tolist():
        df_station = fetch_daily_station_data(
            str(station_id),
            start,
            end,
            api_key,
            chunk_days,
        )
        if not df_station.empty:
            all_daily.append(df_station)
        else:
            print(
                f"[WARN] AEMET sin datos para la estacion {station_id} en {start} -> {end}"
            )

    if not all_daily:
        raise RuntimeError(
            "No se descargaron datos diarios de AEMET para las estaciones seleccionadas."
        )

    df_aemet = pd.concat(all_daily, ignore_index=True)
    station_meta = selected_stations.drop(columns="geometry").copy()
    df_aemet = df_aemet.merge(
        station_meta,
        on="indicativo",
        how="left",
        suffixes=("", "_meta"),
    )

    # Algunas respuestas diarias de AEMET ya traen columnas como `nombre` o
    # `provincia`. Si se pisan con la metadata de estacion, priorizamos el
    # valor existente y usamos el metadato solo como respaldo.
    for col in [
        "nombre",
        "provincia",
        "municipio",
        "altitud",
        "CODNUT3",
        "CODNUT3_prov",
        "dist_ref_m",
    ]:
        meta_col = f"{col}_meta"
        if meta_col not in df_aemet.columns:
            continue
        if col in df_aemet.columns:
            df_aemet[col] = df_aemet[col].fillna(df_aemet[meta_col])
            df_aemet = df_aemet.drop(columns=[meta_col])
        else:
            df_aemet = df_aemet.rename(columns={meta_col: col})

    df_aemet = apply_station_municipality_overrides(df_aemet)

    era5_subset = df_municipios[
        ["municipio", "fecha", "precip_total_dia", "temp_media_dia"]
    ].copy()
    df_compare = df_aemet.merge(era5_subset, on=["municipio", "fecha"], how="inner")
    return df_aemet, df_compare


def corr_safe(series_a: pd.Series, series_b: pd.Series) -> float:
    valid = series_a.notna() & series_b.notna()
    if valid.sum() < 2:
        return math.nan
    return float(series_a[valid].corr(series_b[valid]))


def mae_safe(series_a: pd.Series, series_b: pd.Series) -> float:
    valid = series_a.notna() & series_b.notna()
    if valid.sum() == 0:
        return math.nan
    return float((series_a[valid] - series_b[valid]).abs().mean())


def build_metrics(df_compare: pd.DataFrame) -> pd.DataFrame:
    temp_col = "tmed" if "tmed" in df_compare.columns else None
    prec_col = "prec" if "prec" in df_compare.columns else None

    metrics = []
    for station_id, group in df_compare.groupby("indicativo"):
        metrics.append(
            {
                "indicativo": station_id,
                "nombre": group["nombre"].iloc[0],
                "provincia": group["provincia"].iloc[0],
                "municipio": group["municipio"].iloc[0],
                "n_obs": len(group),
                "corr_temp": (
                    corr_safe(group[temp_col], group["temp_media_dia"])
                    if temp_col is not None
                    else math.nan
                ),
                "mae_temp": (
                    mae_safe(group[temp_col], group["temp_media_dia"])
                    if temp_col is not None
                    else math.nan
                ),
                "corr_prec": (
                    corr_safe(group[prec_col], group["precip_total_dia"])
                    if prec_col is not None
                    else math.nan
                ),
                "mae_prec": (
                    mae_safe(group[prec_col], group["precip_total_dia"])
                    if prec_col is not None
                    else math.nan
                ),
            }
        )
    return (
        pd.DataFrame(metrics)
        .sort_values(["provincia", "indicativo"])
        .reset_index(drop=True)
    )


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[2]
    api_key = get_api_key(args.api_key_env)
    output_dir = root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    gdf_cv, df_municipios = load_cv_inputs(root)

    stations_raw = request_aemet_json(
        "/valores/climatologicos/inventarioestaciones/todasestaciones/",
        api_key,
    )
    gdf_stations = build_station_gdf(stations_raw)

    gdf_stations_cv = gpd.sjoin(
        gdf_stations,
        gdf_cv[["municipio", "CODNUT3", "geometry"]],
        how="inner",
        predicate="within",
    )

    station_ids = [s.strip() for s in args.stations.split(",") if s.strip()]
    selected_stations = select_stations(gdf_stations_cv, gdf_cv, station_ids)

    df_aemet, df_compare = build_validation_table(
        selected_stations=selected_stations,
        df_municipios=df_municipios,
        start=args.start,
        end=args.end,
        api_key=api_key,
        chunk_days=args.chunk_days,
    )
    if df_compare.empty:
        raise RuntimeError(
            "La comparacion AEMET vs ERA5 no genero filas. Revisa estaciones, "
            "fechas y correspondencia municipal."
        )

    df_metrics = build_metrics(df_compare)
    if df_metrics.empty or (df_metrics["n_obs"] <= 0).any():
        raise RuntimeError("No se generaron metricas validas de contraste AEMET vs ERA5.")

    selected_stations.drop(columns="geometry").to_csv(
        output_dir / "aemet_selected_stations_cv.csv",
        index=False,
    )
    df_aemet.to_csv(output_dir / "aemet_daily_raw_selected.csv", index=False)
    df_compare.to_csv(output_dir / "aemet_vs_era5_daily_comparison.csv", index=False)
    df_metrics.to_csv(output_dir / "aemet_vs_era5_metrics.csv", index=False)

    print("Estaciones seleccionadas:")
    print(
        selected_stations.drop(columns="geometry")[
            ["indicativo", "nombre", "provincia", "municipio"]
        ]
    )
    print("\nMetricas de validacion:")
    print(df_metrics)
    print("\nArchivos generados en:", output_dir)


if __name__ == "__main__":
    main()
