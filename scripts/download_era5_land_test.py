from pathlib import Path
import cdsapi

out_path = Path("data/raw/era5_land_cv_2024_01.nc")
out_path.parent.mkdir(parents=True, exist_ok=True)

client = cdsapi.Client()

dataset = "reanalysis-era5-land"
request = {
    "variable": [
        "total_precipitation",
        "2m_temperature",
        "10m_u_component_of_wind",
        "10m_v_component_of_wind",
    ],
    "year": ["2024"],
    "month": ["01"],
    "day": [f"{d:02d}" for d in range(1, 32)],
    "time": [f"{h:02d}:00" for h in range(24)],
    "data_format": "netcdf",
    "download_format": "unarchived",
    "area": [40.90, -1.75, 37.70, 0.80],
}

client.retrieve(dataset, request, str(out_path))

print(f"Descarga completada: {out_path}")
