from __future__ import annotations

import argparse
import calendar
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xarray as xr


DATASET = "reanalysis-era5-land"

BASE_VARIABLES = [
    "total_precipitation",
    "2m_temperature",
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
]

EXTENDED_VARIABLES = [
    "2m_dewpoint_temperature",
    "surface_pressure",
    "surface_runoff",
    "volumetric_soil_water_layer_1",
    "surface_solar_radiation_downwards",
]

AREA_CV = [40.90, -1.75, 37.70, 0.80]  # N, W, S, E - Comunidad Valenciana aprox.

RENAME_MAP = {
    "longitude": "lon",
    "latitude": "lat",
    "valid_time": "time",
    "total_precipitation": "tp",
    "2m_temperature": "t2m",
    "10m_u_component_of_wind": "u10",
    "10m_v_component_of_wind": "v10",
    "2m_dewpoint_temperature": "d2m",
    "surface_pressure": "sp",
    "surface_runoff": "sro",
    "volumetric_soil_water_layer_1": "swvl1",
    "surface_solar_radiation_downwards": "ssrd",
}

RAW_VARIABLE_COLUMNS = ["tp", "t2m", "u10", "v10", "d2m", "sp", "sro", "swvl1", "ssrd"]
EXTENDED_RAW_COLUMNS = ["d2m", "sp", "sro", "swvl1", "ssrd"]


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_path(path: Path, root: Path) -> Path:
    return path if path.is_absolute() else root / path


def month_as_text(month: int | str) -> str:
    return f"{int(month):02d}"


def select_variables(variable_set: str) -> list[str]:
    if variable_set == "base":
        return BASE_VARIABLES
    if variable_set == "extended":
        return EXTENDED_VARIABLES
    if variable_set == "all":
        return BASE_VARIABLES + EXTENDED_VARIABLES
    raise ValueError(f"Conjunto de variables no soportado: {variable_set}")


def resolve_days(year: int | str, month: int | str, day_start: int | None, day_end: int | None) -> list[str]:
    year_text = str(int(year))
    month_text = month_as_text(month)
    days_in_month = calendar.monthrange(int(year_text), int(month_text))[1]
    start = 1 if day_start is None else int(day_start)
    end = days_in_month if day_end is None else int(day_end)

    if start < 1 or end > days_in_month or start > end:
        raise ValueError(
            f"Rango de dias invalido para {year_text}-{month_text}: "
            f"{start}-{end}. El mes tiene {days_in_month} dias."
        )

    return [f"{day:02d}" for day in range(start, end + 1)]


def build_request(
    year: int | str,
    month: int | str,
    variable_set: str,
    day_start: int | None,
    day_end: int | None,
) -> dict[str, Any]:
    year_text = str(int(year))
    month_text = month_as_text(month)

    return {
        "variable": select_variables(variable_set),
        "year": [year_text],
        "month": [month_text],
        "day": resolve_days(year, month, day_start, day_end),
        "time": [f"{hour:02d}:00" for hour in range(24)],
        "data_format": "netcdf",
        "download_format": "unarchived",
        "area": AREA_CV,
    }


def download_sample(request: dict[str, Any], out_file: Path, overwrite: bool) -> None:
    if out_file.exists() and not overwrite:
        print(f"[SKIP] Ya existe el NetCDF de prueba: {out_file}")
        return

    import cdsapi

    out_file.parent.mkdir(parents=True, exist_ok=True)
    client = cdsapi.Client()
    print(f"[DOWNLOAD] Descargando muestra extendida en: {out_file}")
    client.retrieve(DATASET, request, str(out_file))
    print(f"[OK] Descarga completada: {out_file}")


def flatten_era5_land(raw_file: Path) -> pd.DataFrame:
    ds = None
    try:
        ds = xr.open_dataset(raw_file)
        df_raw = ds.to_dataframe().reset_index()
    finally:
        if ds is not None:
            ds.close()

    df_raw = df_raw.rename(columns=RENAME_MAP)

    cols_keep = [
        col
        for col in ["time", "lon", "lat", *RAW_VARIABLE_COLUMNS, "expver"]
        if col in df_raw.columns
    ]
    df = df_raw[cols_keep].copy()

    if "expver" in df.columns:
        mode_expver = df["expver"].mode(dropna=True)
        if not mode_expver.empty:
            df = df[df["expver"] == mode_expver.iloc[0]].copy()
        df = df.drop(columns=["expver"], errors="ignore")

    present_raw_cols = [col for col in RAW_VARIABLE_COLUMNS if col in df.columns]
    if present_raw_cols:
        df = df.dropna(subset=present_raw_cols).copy()

    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"])

    if "tp" in df.columns:
        df["precip_mm"] = df["tp"] * 1000.0

    if "t2m" in df.columns:
        df["temp_c"] = df["t2m"] - 273.15

    if {"u10", "v10"}.issubset(df.columns):
        df["viento_ms"] = np.sqrt(df["u10"] ** 2 + df["v10"] ** 2)

    if "d2m" in df.columns:
        df["dewpoint_c"] = df["d2m"] - 273.15

    if "sp" in df.columns:
        df["surface_pressure_hpa"] = df["sp"] / 100.0

    if "sro" in df.columns:
        df["surface_runoff_mm"] = df["sro"] * 1000.0

    if "swvl1" in df.columns:
        df["soil_water_layer1_m3_m3"] = df["swvl1"]

    if "ssrd" in df.columns:
        df["solar_radiation_mj_m2"] = df["ssrd"] / 1_000_000.0

    if "time" in df.columns:
        df["year"] = df["time"].dt.year
        df["month"] = df["time"].dt.month

    sort_cols = [col for col in ["time", "lat", "lon"] if col in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols).reset_index(drop=True)

    ordered_cols = [
        "time",
        "lon",
        "lat",
        "tp",
        "precip_mm",
        "t2m",
        "temp_c",
        "u10",
        "v10",
        "viento_ms",
        "d2m",
        "dewpoint_c",
        "sp",
        "surface_pressure_hpa",
        "sro",
        "surface_runoff_mm",
        "swvl1",
        "soil_water_layer1_m3_m3",
        "ssrd",
        "solar_radiation_mj_m2",
        "year",
        "month",
    ]
    cols = [col for col in ordered_cols if col in df.columns]
    cols += [col for col in df.columns if col not in cols]
    return df[cols]


def numeric_range(series: pd.Series) -> dict[str, float | None]:
    if series.empty:
        return {"min": None, "max": None, "mean": None}

    return {
        "min": float(series.min()),
        "max": float(series.max()),
        "mean": float(series.mean()),
    }


def build_validation_report(
    df: pd.DataFrame,
    year: int,
    month: int,
    requested_days: list[str],
    variable_set: str,
) -> dict[str, Any]:
    expected_hours = len(requested_days) * 24
    missing_extended = [col for col in EXTENDED_RAW_COLUMNS if col not in df.columns]
    available_extended = [col for col in EXTENDED_RAW_COLUMNS if col in df.columns]

    report: dict[str, Any] = {
        "year": year,
        "month": month_as_text(month),
        "requested_days": requested_days,
        "variable_set": variable_set,
        "rows": int(len(df)),
        "columns": list(df.columns),
        "available_extended_raw_columns": available_extended,
        "missing_extended_raw_columns": missing_extended,
        "nulls": {col: int(value) for col, value in df.isna().sum().items()},
    }

    if {"time", "lat", "lon"}.issubset(df.columns):
        unique_times = int(df["time"].nunique())
        grid_points = int(df[["lat", "lon"]].drop_duplicates().shape[0])
        duplicate_grid_time = int(df.duplicated(subset=["time", "lat", "lon"]).sum())
        report.update(
            {
                "time_min": str(df["time"].min()),
                "time_max": str(df["time"].max()),
                "unique_times": unique_times,
                "expected_hours": expected_hours,
                "grid_points": grid_points,
                "expected_rows_from_grid": unique_times * grid_points,
                "duplicate_time_lat_lon": duplicate_grid_time,
            }
        )

    range_cols = [
        "precip_mm",
        "temp_c",
        "viento_ms",
        "dewpoint_c",
        "surface_pressure_hpa",
        "surface_runoff_mm",
        "soil_water_layer1_m3_m3",
        "solar_radiation_mj_m2",
    ]
    report["ranges"] = {
        col: numeric_range(df[col])
        for col in range_cols
        if col in df.columns and pd.api.types.is_numeric_dtype(df[col])
    }
    return report


def validate_report(report: dict[str, Any]) -> list[str]:
    warnings: list[str] = []

    if report.get("unique_times") != report.get("expected_hours"):
        warnings.append("La cobertura horaria no coincide con el mes esperado.")

    if report.get("duplicate_time_lat_lon", 0) != 0:
        warnings.append("Existen duplicados por time-lat-lon.")

    if report.get("missing_extended_raw_columns"):
        warnings.append(
            "Faltan variables extendidas en el NetCDF: "
            + ", ".join(report["missing_extended_raw_columns"])
        )

    if report.get("rows", 0) == 0:
        warnings.append("El dataset procesado no contiene filas.")

    return warnings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prueba controlada de variables ERA5-Land extendidas sin modificar "
            "los datasets oficiales del proyecto."
        )
    )
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--month", type=int, default=1)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--print-request", action="store_true")
    parser.add_argument("--variable-set", choices=["all", "base", "extended"], default="all")
    parser.add_argument("--day-start", type=int)
    parser.add_argument("--day-end", type=int)
    parser.add_argument("--raw-dir", type=Path, default=Path("DATA/RAW"))
    parser.add_argument("--processed-dir", type=Path, default=Path("DATA/PROCESSED"))
    parser.add_argument("--raw-file", type=Path)
    parser.add_argument("--output-file", type=Path)
    parser.add_argument("--report-file", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = project_root()

    raw_dir = resolve_path(args.raw_dir, root)
    processed_dir = resolve_path(args.processed_dir, root)
    year = int(args.year)
    month = int(args.month)
    month_text = month_as_text(month)
    requested_days = resolve_days(year, month, args.day_start, args.day_end)
    full_month = len(requested_days) == calendar.monthrange(year, month)[1]
    day_label = "" if full_month else f"_d{requested_days[0]}_{requested_days[-1]}"
    variable_label = "" if args.variable_set == "all" else f"_{args.variable_set}"
    sample_label = f"{year}_{month_text}{day_label}{variable_label}"

    raw_file = (
        resolve_path(args.raw_file, root)
        if args.raw_file
        else raw_dir / f"era5_land_cv_extended_sample_{sample_label}.nc"
    )
    output_file = (
        resolve_path(args.output_file, root)
        if args.output_file
        else processed_dir / f"era5_land_cv_extended_sample_{sample_label}_flat.csv"
    )
    report_file = (
        resolve_path(args.report_file, root)
        if args.report_file
        else processed_dir / f"era5_land_cv_extended_sample_{sample_label}_validation.json"
    )

    request = build_request(year, month, args.variable_set, args.day_start, args.day_end)
    if args.print_request:
        print(json.dumps(request, indent=2))
        if not args.download and not raw_file.exists():
            return 0

    if args.download:
        download_sample(request, raw_file, args.overwrite)

    if not raw_file.exists():
        raise FileNotFoundError(
            "No existe el NetCDF de prueba. Ejecuta de nuevo con --download "
            f"o indica --raw-file. Ruta esperada: {raw_file}"
        )

    print(f"[READ] Procesando NetCDF: {raw_file}")
    df = flatten_era5_land(raw_file)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(output_file, index=False)
    report = build_validation_report(df, year, month, requested_days, args.variable_set)
    warnings = validate_report(report)
    report["warnings"] = warnings

    report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"[OK] CSV de muestra: {output_file}")
    print(f"[OK] Informe de validacion: {report_file}")
    if warnings:
        print("[WARN] Revisar advertencias:")
        for warning in warnings:
            print(f"  - {warning}")
    else:
        print("[OK] Validacion estructural sin advertencias.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
