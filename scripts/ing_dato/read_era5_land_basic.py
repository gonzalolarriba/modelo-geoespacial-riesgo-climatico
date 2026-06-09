"""Lee NetCDF ERA5-Land base y genera CSV mensuales planos.

Uso en el pipeline:
    Script operativo de Ingenieria del Dato, posterior a la descarga mensual
    ERA5-Land base.

Entradas:
    DATA/RAW/era5_land_cv_YYYY_MM.nc

Salidas:
    DATA/PROCESSED/dataset_clima_cv_2019_2024.csv/era5_land_cv_YYYY_MM_flat.csv

Notas:
    Convierte unidades, calcula viento resultante y descarta registros sin
    variables climaticas clave.
"""

from pathlib import Path
import re

import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "DATA"
RAW = DATA / "RAW"
PROC = DATA / "PROCESSED"

# Historical folder used by the project for monthly flattened CSV files.
FLAT_DIR = PROC / "dataset_clima_cv_2019_2024.csv"

PROC.mkdir(parents=True, exist_ok=True)
FLAT_DIR.mkdir(parents=True, exist_ok=True)

YEARS = range(2019, 2025)
MONTHS = range(1, 13)
EXPECTED_STEMS = {
    f"era5_land_cv_{year}_{month:02d}"
    for year in YEARS
    for month in MONTHS
}
BASE_MONTHLY_PATTERN = re.compile(r"^era5_land_cv_\d{4}_\d{2}$")

all_raw_files = sorted(RAW.glob("era5_land_cv_*.nc"))
files = [
    path
    for path in all_raw_files
    if BASE_MONTHLY_PATTERN.match(path.stem) and path.stem in EXPECTED_STEMS
]
ignored_files = sorted(set(all_raw_files) - set(files))
missing_stems = sorted(EXPECTED_STEMS - {path.stem for path in files})

if not files:
    raise FileNotFoundError(f"No se encontraron archivos .nc en {RAW}")
if missing_stems:
    missing_names = ", ".join(f"{stem}.nc" for stem in missing_stems)
    raise FileNotFoundError(
        "Faltan archivos mensuales ERA5-Land del periodo 2019-2024: "
        f"{missing_names}"
    )

print(f"Total archivos encontrados: {len(files)}")
if ignored_files:
    print("Archivos RAW ignorados por no pertenecer al pipeline base:")
    for path in ignored_files:
        print(f" - {path.name}")

for i, era5_file in enumerate(files, start=1):
    print(f"\n[{i}/{len(files)}] Procesando: {era5_file.name}")

    out_file = FLAT_DIR / f"{era5_file.stem}_flat.csv"

    if out_file.exists():
        print(f"[SKIP] Ya existe: {out_file}")
        continue

    ds = None
    try:
        ds = xr.open_dataset(era5_file)
        df_raw = ds.to_dataframe().reset_index()

        rename_map = {
            "longitude": "lon",
            "latitude": "lat",
            "valid_time": "time",
            "total_precipitation": "tp",
            "2m_temperature": "t2m",
            "10m_u_component_of_wind": "u10",
            "10m_v_component_of_wind": "v10",
        }
        df_raw = df_raw.rename(columns=rename_map)

        cols_keep = [
            c
            for c in ["time", "lon", "lat", "tp", "t2m", "u10", "v10", "expver"]
            if c in df_raw.columns
        ]
        df = df_raw[cols_keep].copy()

        # ERA5-Land can include expver. Keep the modal version to avoid
        # duplicating observations across product versions.
        if "expver" in df.columns:
            mode_expver = df["expver"].mode(dropna=True)
            if not mode_expver.empty:
                df = df[df["expver"] == mode_expver.iloc[0]].copy()
            df = df.drop(columns=["expver"], errors="ignore")

        required_cols = [c for c in ["tp", "t2m", "u10", "v10"] if c in df.columns]
        n_before = len(df)
        df = df.dropna(subset=required_cols).copy()
        n_after = len(df)
        removed = n_before - n_after
        removed_pct = (removed / n_before * 100) if n_before else 0.0

        if "time" in df.columns:
            df["time"] = pd.to_datetime(df["time"])

        if "tp" in df.columns:
            df["precip_mm"] = df["tp"] * 1000.0

        if "t2m" in df.columns:
            df["temp_c"] = df["t2m"] - 273.15

        if {"u10", "v10"}.issubset(df.columns):
            df["viento_ms"] = np.sqrt(df["u10"] ** 2 + df["v10"] ** 2)

        if "time" in df.columns:
            df["year"] = df["time"].dt.year
            df["month"] = df["time"].dt.month

        sort_cols = [c for c in ["time", "lat", "lon"] if c in df.columns]
        if sort_cols:
            df = df.sort_values(sort_cols).copy()

        df.to_csv(out_file, index=False)

        print(f"[OK] Guardado: {out_file}")
        print(f"     Filas iniciales: {n_before:,}")
        print(f"     Filas finales:   {n_after:,}")
        print(f"     Eliminadas:      {removed:,} ({removed_pct:.2f}%)")
        print(f"     Columnas finales: {df.columns.tolist()}")

    except Exception as exc:
        print(f"[ERROR] Fallo {era5_file.name}: {exc}")

    finally:
        if ds is not None:
            ds.close()

print("\nProceso terminado.")
