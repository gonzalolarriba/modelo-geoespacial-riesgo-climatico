from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd


GROUP_KEYS = ["municipio", "CODNUT2", "CODNUT3", "fecha"]

INSTANT_VARIABLES = {
    "dewpoint_c": {
        "dewpoint_media_dia": "mean",
        "dewpoint_max_dia": "max",
        "dewpoint_min_dia": "min",
    },
    "surface_pressure_hpa": {
        "presion_superficie_media_hpa": "mean",
        "presion_superficie_max_hpa": "max",
        "presion_superficie_min_hpa": "min",
    },
    "soil_water_layer1_m3_m3": {
        "humedad_suelo_capa1_media_m3_m3": "mean",
        "humedad_suelo_capa1_max_m3_m3": "max",
        "humedad_suelo_capa1_min_m3_m3": "min",
    },
}

ACCUMULATED_VARIABLES = {
    "surface_runoff_mm": "runoff_superficial_total_dia_mm",
    "solar_radiation_mj_m2": "radiacion_solar_total_dia_mj_m2",
}


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_path(path: Path, root: Path) -> Path:
    return path if path.is_absolute() else root / path


def build_municipality_grid_assignment(
    df_grid_source: pd.DataFrame,
    municipios_file: Path,
) -> gpd.GeoDataFrame:
    gdf_cv = gpd.read_file(municipios_file)
    required_cols = {"municipio", "CODNUT2", "CODNUT3", "geometry"}
    missing_cols = required_cols.difference(gdf_cv.columns)
    if missing_cols:
        raise ValueError(f"La capa municipal no contiene columnas requeridas: {sorted(missing_cols)}")

    grid = df_grid_source[["lon", "lat"]].drop_duplicates().reset_index(drop=True)
    if grid.empty:
        raise ValueError("No se encontraron puntos de rejilla lon-lat en la muestra ERA5-Land.")

    gdf_grid = gpd.GeoDataFrame(
        grid,
        geometry=gpd.points_from_xy(grid["lon"], grid["lat"]),
        crs="EPSG:4326",
    )

    gdf_municipios_ref = gdf_cv.copy()
    gdf_municipios_ref["geometry_rep"] = gdf_municipios_ref.representative_point()
    gdf_municipios_ref = gpd.GeoDataFrame(
        gdf_municipios_ref.drop(columns="geometry"),
        geometry=gdf_municipios_ref["geometry_rep"],
        crs="EPSG:4326",
    ).drop(columns="geometry_rep", errors="ignore")

    gdf_assign = gpd.sjoin_nearest(
        gdf_municipios_ref.to_crs(epsg=25830),
        gdf_grid.to_crs(epsg=25830)[["lon", "lat", "geometry"]],
        how="left",
        distance_col="dist_metros",
    ).to_crs(epsg=4326)

    lookup_cols = ["municipio", "CODNUT2", "CODNUT3", "lon", "lat", "dist_metros"]
    return gdf_assign[lookup_cols].copy()


def load_extended_sample(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"No existe la muestra extendida: {path}")

    df = pd.read_csv(path, parse_dates=["time"])
    required_cols = {"time", "lon", "lat"}
    missing_cols = required_cols.difference(df.columns)
    if missing_cols:
        raise ValueError(f"La muestra no contiene columnas requeridas: {sorted(missing_cols)}")

    return df


def aggregate_instant_variables(df: pd.DataFrame) -> pd.DataFrame:
    df_natural = df.copy()
    df_natural["fecha"] = df_natural["time"].dt.floor("D")

    agg_spec: dict[str, tuple[str, str]] = {
        "lon": ("lon", "mean"),
        "lat": ("lat", "mean"),
        "dist_metros": ("dist_metros", "mean"),
    }

    for source_col, output_map in INSTANT_VARIABLES.items():
        if source_col not in df_natural.columns:
            continue
        for output_col, method in output_map.items():
            agg_spec[output_col] = (source_col, method)

    return (
        df_natural.groupby(GROUP_KEYS, as_index=False)
        .agg(**agg_spec)
        .sort_values(GROUP_KEYS)
        .reset_index(drop=True)
    )


def aggregate_accumulated_variables(df: pd.DataFrame) -> pd.DataFrame:
    available = {
        source_col: output_col
        for source_col, output_col in ACCUMULATED_VARIABLES.items()
        if source_col in df.columns
    }
    if not available:
        return pd.DataFrame(columns=GROUP_KEYS)

    df_acc = df.copy()
    fecha_min = df_acc["time"].dt.floor("D").min()
    fecha_max = df_acc["time"].dt.floor("D").max()

    # ERA5-Land accumulations close the previous hour. This mirrors the
    # precipitation handling used in notebook 1.
    df_acc["fecha"] = (df_acc["time"] - pd.Timedelta(hours=1)).dt.floor("D")
    df_acc = df_acc[df_acc["fecha"].between(fecha_min, fecha_max)].copy()

    agg_spec = {
        output_col: (source_col, "max")
        for source_col, output_col in available.items()
    }

    return (
        df_acc.groupby(GROUP_KEYS, as_index=False)
        .agg(**agg_spec)
        .sort_values(GROUP_KEYS)
        .reset_index(drop=True)
    )


def build_municipal_daily_sample(df: pd.DataFrame, assignment: pd.DataFrame) -> pd.DataFrame:
    df_municipal = df.merge(
        assignment,
        on=["lon", "lat"],
        how="inner",
        validate="many_to_many",
    )

    df_daily = aggregate_instant_variables(df_municipal)
    df_acc = aggregate_accumulated_variables(df_municipal)

    if not df_acc.empty:
        df_daily = df_daily.merge(df_acc, on=GROUP_KEYS, how="left", validate="one_to_one")

    df_daily["fecha"] = pd.to_datetime(df_daily["fecha"]).dt.date.astype(str)
    df_daily = df_daily.sort_values(["municipio", "fecha"]).reset_index(drop=True)

    preferred_cols = [
        "municipio",
        "CODNUT2",
        "CODNUT3",
        "fecha",
        "lon",
        "lat",
        "dist_metros",
        "dewpoint_media_dia",
        "dewpoint_max_dia",
        "dewpoint_min_dia",
        "presion_superficie_media_hpa",
        "presion_superficie_max_hpa",
        "presion_superficie_min_hpa",
        "runoff_superficial_total_dia_mm",
        "humedad_suelo_capa1_media_m3_m3",
        "humedad_suelo_capa1_max_m3_m3",
        "humedad_suelo_capa1_min_m3_m3",
        "radiacion_solar_total_dia_mj_m2",
    ]
    cols = [col for col in preferred_cols if col in df_daily.columns]
    cols += [col for col in df_daily.columns if col not in cols]
    return df_daily[cols]


def numeric_range(series: pd.Series) -> dict[str, float | None]:
    if series.empty:
        return {"min": None, "max": None, "mean": None}

    return {
        "min": float(series.min()),
        "max": float(series.max()),
        "mean": float(series.mean()),
    }


def build_validation_report(df_daily: pd.DataFrame, assignment: pd.DataFrame) -> dict[str, Any]:
    n_municipios = int(df_daily["municipio"].nunique()) if "municipio" in df_daily.columns else 0
    n_fechas = int(df_daily["fecha"].nunique()) if "fecha" in df_daily.columns else 0
    expected_rows = n_municipios * n_fechas
    duplicate_keys = int(df_daily.duplicated(subset=["municipio", "fecha"]).sum())

    days_by_municipality = df_daily.groupby("municipio")["fecha"].nunique()
    incomplete_municipalities = int((days_by_municipality < n_fechas).sum())

    numeric_cols = [
        col
        for col in df_daily.columns
        if col not in {"municipio", "CODNUT2", "CODNUT3", "fecha"}
        and pd.api.types.is_numeric_dtype(df_daily[col])
    ]

    report: dict[str, Any] = {
        "rows": int(len(df_daily)),
        "columns": list(df_daily.columns),
        "municipalities": n_municipios,
        "dates": n_fechas,
        "expected_rows": int(expected_rows),
        "duplicate_municipio_fecha": duplicate_keys,
        "incomplete_municipalities": incomplete_municipalities,
        "nulls": {col: int(value) for col, value in df_daily.isna().sum().items()},
        "assignment_rows": int(len(assignment)),
        "assignment_missing_grid": int(assignment[["lon", "lat"]].isna().any(axis=1).sum()),
        "assignment_distance_mean_m": float(assignment["dist_metros"].mean()),
        "assignment_distance_max_m": float(assignment["dist_metros"].max()),
        "ranges": {col: numeric_range(df_daily[col]) for col in numeric_cols},
    }

    warnings: list[str] = []
    if n_municipios != 542:
        warnings.append(f"Se esperaban 542 municipios y se obtuvieron {n_municipios}.")
    if len(df_daily) != expected_rows:
        warnings.append("El numero de filas no coincide con municipios x fechas.")
    if duplicate_keys:
        warnings.append("Existen duplicados municipio-fecha.")
    if int(df_daily.isna().sum().sum()) != 0:
        warnings.append("Existen valores nulos en el dataset municipal diario.")
    if incomplete_municipalities:
        warnings.append("Existen municipios con cobertura temporal incompleta.")
    if report["assignment_missing_grid"]:
        warnings.append("Existen municipios sin celda ERA5-Land asignada.")
    if report["assignment_distance_max_m"] >= 10_000:
        warnings.append("Hay asignaciones espaciales con distancia superior o igual a 10 km.")

    report["warnings"] = warnings
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Municipaliza una muestra ERA5-Land extendida y genera una salida "
            "diaria separada para validacion."
        )
    )
    parser.add_argument(
        "--input-file",
        type=Path,
        default=Path("DATA/PROCESSED/era5_land_cv_extended_sample_2024_01_d01_07_extended_flat.csv"),
    )
    parser.add_argument(
        "--municipios-file",
        type=Path,
        default=Path("DATA/EXTERNAL/municipios_cv.geojson"),
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=Path("DATA/PROCESSED/dataset_cv_municipios_extended_sample_2024_01_d01_07.csv"),
    )
    parser.add_argument(
        "--report-file",
        type=Path,
        default=Path("DATA/PROCESSED/dataset_cv_municipios_extended_sample_2024_01_d01_07_validation.json"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = project_root()

    input_file = resolve_path(args.input_file, root)
    municipios_file = resolve_path(args.municipios_file, root)
    output_file = resolve_path(args.output_file, root)
    report_file = resolve_path(args.report_file, root)

    df = load_extended_sample(input_file)
    print(f"[READ] Muestra extendida: {input_file}")
    print(f"       Filas: {len(df):,}")

    assignment = build_municipality_grid_assignment(df, municipios_file)
    print(f"[OK] Municipios asignados: {len(assignment):,}")
    print(f"     Distancia media: {assignment['dist_metros'].mean():.2f} m")
    print(f"     Distancia maxima: {assignment['dist_metros'].max():.2f} m")

    df_daily = build_municipal_daily_sample(df, assignment)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.parent.mkdir(parents=True, exist_ok=True)
    df_daily.to_csv(output_file, index=False)

    report = build_validation_report(df_daily, assignment)
    report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"[OK] Dataset municipal diario: {output_file}")
    print(f"[OK] Informe de validacion: {report_file}")
    print(f"     Shape: {df_daily.shape}")
    print(f"     Municipios: {report['municipalities']}")
    print(f"     Fechas: {report['dates']}")

    if report["warnings"]:
        print("[WARN] Revisar advertencias:")
        for warning in report["warnings"]:
            print(f"  - {warning}")
    else:
        print("[OK] Validacion municipal sin advertencias.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
