import cdsapi
from pathlib import Path


DATASET = "reanalysis-era5-land"

YEARS = ["2019", "2020", "2021", "2022", "2023", "2024"]
MONTHS = [f"{m:02d}" for m in range(1, 13)]

VARIABLES = [
    "2m_dewpoint_temperature",
    "surface_pressure",
    "surface_runoff",
    "volumetric_soil_water_layer_1",
    "surface_solar_radiation_downwards",
]

AREA = [40.90, -1.75, 37.70, 0.80]  # N, W, S, E - Comunidad Valenciana aprox.

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "DATA" / "RAW" / "era5_land_extended"
RAW_DIR.mkdir(parents=True, exist_ok=True)

client = cdsapi.Client()

for year in YEARS:
    for month in MONTHS:
        out_path = RAW_DIR / f"era5_land_cv_extended_{year}_{month}.nc"

        if out_path.exists():
            print(f"[SKIP] Ya existe: {out_path}")
            continue

        request = {
            "variable": VARIABLES,
            "year": [year],
            "month": [month],
            "day": [f"{d:02d}" for d in range(1, 32)],
            "time": [f"{h:02d}:00" for h in range(24)],
            "data_format": "netcdf",
            "download_format": "unarchived",
            "area": AREA,
        }

        print(f"[DOWNLOAD] Descargando {year}-{month} ...")
        client.retrieve(DATASET, request, str(out_path))
        print(f"[OK] Guardado en: {out_path}")

print("\nProceso terminado.")
