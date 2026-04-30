from pathlib import Path

import geopandas as gpd


ROOT = Path(__file__).resolve().parents[2]
SHAPEFILE = (
    ROOT
    / "DATA"
    / "EXTERNAL"
    / "municipios"
    / "recintos_municipales_inspire_peninbal_etrs89.shp"
)

if not SHAPEFILE.exists():
    raise FileNotFoundError(f"No se encontro el shapefile municipal: {SHAPEFILE}")

gdf = gpd.read_file(SHAPEFILE)
print("Shape:", gdf.shape)
print("CRS:", gdf.crs)
print(gdf.head())
