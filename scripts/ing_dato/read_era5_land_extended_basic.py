from pathlib import Path

import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "DATA"
RAW = DATA / "RAW" / "era5_land_extended"
PROC = DATA / "PROCESSED"

# Carpeta paralela a dataset_clima_cv_2019_2024.csv, pero para variables extendidas.
FLAT_DIR = PROC / "dataset_clima_cv_extended_2019_2024.csv"

PROC.mkdir(parents=True, exist_ok=True)
FLAT_DIR.mkdir(parents=True, exist_ok=True)

files = sorted(RAW.glob("era5_land_cv_extended_*.nc"))

if not files:
    raise FileNotFoundError(f"No se encontraron archivos .nc en {RAW}")

print(f"Total archivos encontrados: {len(files)}")

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
            "2m_dewpoint_temperature": "d2m",
            "surface_pressure": "sp",
            "surface_runoff": "sro",
            "volumetric_soil_water_layer_1": "swvl1",
            "surface_solar_radiation_downwards": "ssrd",
        }
        df_raw = df_raw.rename(columns=rename_map)

        cols_keep = [
            c
            for c in ["time", "lon", "lat", "d2m", "sp", "sro", "swvl1", "ssrd", "expver"]
            if c in df_raw.columns
        ]
        df = df_raw[cols_keep].copy()

        # ERA5-Land puede incluir expver. Se conserva la version modal para
        # evitar duplicar observaciones entre versiones del producto.
        if "expver" in df.columns:
            mode_expver = df["expver"].mode(dropna=True)
            if not mode_expver.empty:
                df = df[df["expver"] == mode_expver.iloc[0]].copy()
            df = df.drop(columns=["expver"], errors="ignore")

        required_cols = [c for c in ["d2m", "sp", "sro", "swvl1", "ssrd"] if c in df.columns]
        n_before = len(df)
        df = df.dropna(subset=required_cols).copy()
        n_after = len(df)
        removed = n_before - n_after
        removed_pct = (removed / n_before * 100) if n_before else 0.0

        if "time" in df.columns:
            df["time"] = pd.to_datetime(df["time"])

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
