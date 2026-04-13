from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr

# =========================
# Rutas
# =========================
DATA = Path("DATA")
RAW = DATA / "RAW"
PROC = DATA / "PROCESSED"
PROC.mkdir(parents=True, exist_ok=True)

# Buscar todos los NetCDF de ERA5-Land
files = sorted(RAW.glob("era5_land_cv_*.nc"))

if not files:
    raise FileNotFoundError(f"No se encontraron archivos .nc en {RAW}")

print(f"Total archivos encontrados: {len(files)}")

# =========================
# Procesamiento por lotes
# =========================
for i, era5_file in enumerate(files, start=1):
    print(f"\n[{i}/{len(files)}] Procesando: {era5_file.name}")

    out_file = PROC / f"{era5_file.stem}_flat.csv"

    # Evitar reprocesar si ya existe
    if out_file.exists():
        print(f"[SKIP] Ya existe: {out_file}")
        continue

    try:
        # 1) Abrir NetCDF
        ds = xr.open_dataset(era5_file)

        # 2) Pasar a DataFrame
        df_raw = ds.to_dataframe().reset_index()

        # 3) Renombrado flexible
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

        # 4) Selección de columnas útiles
        cols_keep = [
            c
            for c in ["time", "lon", "lat", "tp", "t2m", "u10", "v10", "expver"]
            if c in df_raw.columns
        ]
        df = df_raw[cols_keep].copy()

        # 5) Filtrado opcional de expver (si existe)
        # En tu caso suele ser único, pero lo dejamos para robustez
        if "expver" in df.columns:
            mode_expver = df["expver"].mode(dropna=True)
            if not mode_expver.empty:
                df = df[df["expver"] == mode_expver.iloc[0]].copy()
            df = df.drop(columns=["expver"], errors="ignore")

        # 6) Eliminar registros sin información climática completa
        required_cols = [c for c in ["tp", "t2m", "u10", "v10"] if c in df.columns]
        n_before = len(df)
        df = df.dropna(subset=required_cols).copy()
        n_after = len(df)
        removed = n_before - n_after
        removed_pct = (removed / n_before * 100) if n_before else 0.0

        # 7) Conversiones
        if "time" in df.columns:
            df["time"] = pd.to_datetime(df["time"])

        if "tp" in df.columns:
            df["precip_mm"] = df["tp"] * 1000.0

        if "t2m" in df.columns:
            df["temp_c"] = df["t2m"] - 273.15

        if {"u10", "v10"}.issubset(df.columns):
            df["viento_ms"] = np.sqrt(df["u10"] ** 2 + df["v10"] ** 2)

        # 8) Variables temporales útiles para fases posteriores
        if "time" in df.columns:
            df["year"] = df["time"].dt.year
            df["month"] = df["time"].dt.month

        # 9) Ordenar
        sort_cols = [c for c in ["time", "lat", "lon"] if c in df.columns]
        if sort_cols:
            df = df.sort_values(sort_cols).copy()

        # 10) Guardar CSV plano
        df.to_csv(out_file, index=False)

        print(f"[OK] Guardado: {out_file}")
        print(f"     Filas iniciales: {n_before:,}")
        print(f"     Filas finales:   {n_after:,}")
        print(f"     Eliminadas:      {removed:,} ({removed_pct:.2f}%)")
        print(f"     Columnas finales: {df.columns.tolist()}")

    except Exception as e:
        print(f"[ERROR] Falló {era5_file.name}: {e}")

    finally:
        try:
            ds.close()
        except Exception:
            pass

print("\n✅ Proceso terminado.")
