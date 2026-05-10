"""Inspeccion rapida del shapefile municipal bruto del IGN.

Script auxiliar de diagnostico. La construccion de la capa CV queda documentada
y validada dentro del Notebook 1.
"""

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
