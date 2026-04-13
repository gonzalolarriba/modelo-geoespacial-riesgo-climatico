import geopandas as gpd

path = "data/external/recintos_municipales_inspire_peninbal_etrs89.shp"

gdf = gpd.read_file(path)
print(gdf.shape)
gdf.head()