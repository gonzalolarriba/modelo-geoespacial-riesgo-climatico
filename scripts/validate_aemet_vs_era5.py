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
PROV_MAP = {
    "ES521": "ALICANTE",
    "ES522": "CASTELLON",
    "ES523": "VALENCIA",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Descarga una muestra pequena de AEMET OpenData y valida "
            "ERA5 municipal frente a estaciones seleccionadas de la CV."
        )
    )
    parser.add_argument(
        "--start",
        default="2019-01-01",
        help="Fecha inicial en formato YYYY-MM-DD.",
    )
    parser.add_argument(
        "--end",
        default="2024-12-31",
        help="Fecha final en formato YYYY-MM-DD.",
    )
    parser.add_argument(
        "--api-key-env",
        default="AEMET_API_KEY",
        help="Variable de entorno que contiene la API key de AEMET.",
    )
    parser.add_argument(
        "--output-dir",
        default="DATA/PROCESSED",
        help="Directorio donde guardar salidas CSV.",
    )
    parser.add_argument(
        "--stations",
        default="",
        help=(
            "Lista opcional de indicativos AEMET separados por comas. "
            "Si no se indica, el script selecciona una estacion por provincia."
        ),
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

    gdf_prov = gdf_cv.dissolve(by="CODNUT3").reset_index()
    gdf_prov["prov_name"] = gdf_prov["CODNUT3"].map(PROV_MAP)
    gdf_prov["rep_point"] = gdf_prov.representative_point()
    gdf_prov = gpd.GeoDataFrame(
        gdf_prov.drop(columns="geometry"),
        geometry=gdf_prov["rep_point"],
        crs="EPSG:4326",
    ).drop(columns="rep_point")

    stations_proj = gdf_stations_cv.to_crs(25830)
    prov_proj = gdf_prov.to_crs(25830)

    selected_parts = []
    for codnut3 in sorted(gdf_prov["CODNUT3"].dropna().unique()):
        station_subset = stations_proj[stations_proj["CODNUT3"] == codnut3].copy()
        if station_subset.empty:
            continue

        target = prov_proj.loc[prov_proj["CODNUT3"] == codnut3].copy()
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
    selected = selected.rename(
        columns={
            "municipio_right": "municipio",
            "CODNUT3_right": "CODNUT3",
            "CODNUT3_left": "CODNUT3_prov",
        }
    )
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
    return selected


def fetch_daily_station_data(
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


def build_validation_table(
    selected_stations: gpd.GeoDataFrame,
    df_municipios: pd.DataFrame,
    start: str,
    end: str,
    api_key: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_daily = []
    for station_id in selected_stations["indicativo"].tolist():
        df_station = fetch_daily_station_data(station_id, start, end, api_key)
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
    root = Path.cwd()
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
    )
    df_metrics = build_metrics(df_compare)

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
