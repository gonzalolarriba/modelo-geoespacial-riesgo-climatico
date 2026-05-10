"""Procesa el piloto Catastro BU usado antes del escalado completo.

El pipeline completo de Catastro para los 542 municipios usa
build_catastro_buildings_cv_summary.py.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd


# Mismo piloto descargado con download_catastro_buildings_pilot.py.
MUNICIPALITIES = {
    "03002": "Agost",
    "12080": "Morella",
    "46181": "Oliva",
}

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "DATA" / "RAW" / "catastro" / "buildings"
PROC_DIR = ROOT / "DATA" / "PROCESSED"
INE_FILE = PROC_DIR / "ine_contexto_municipal.csv"
OUT_FILE = PROC_DIR / "catastro_buildings_pilot_summary.csv"


def build_gml_path(zip_path: Path, code: str, layer: str) -> str:
    zip_posix = zip_path.resolve().as_posix()
    return f"/vsizip/{zip_posix}/A.ES.SDGC.BU.{code}.{layer}.gml"


def read_catastro_layer(zip_path: Path, code: str, layer: str) -> gpd.GeoDataFrame:
    gml_path = build_gml_path(zip_path, code, layer)
    gdf = gpd.read_file(gml_path)

    if gdf.crs is None:
        raise ValueError(f"La capa {layer} de {code} no tiene CRS informado.")

    if gdf.crs.to_epsg() != 25830:
        gdf = gdf.to_crs(25830)

    return gdf


def to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def summarize_municipality(code: str, name: str, area_km2: float) -> dict[str, float | str]:
    zip_path = RAW_DIR / f"A.ES.SDGC.BU.{code}.zip"
    if not zip_path.exists():
        raise FileNotFoundError(f"No existe el ZIP de Catastro: {zip_path}")

    buildings = read_catastro_layer(zip_path, code, "building")
    building_parts = read_catastro_layer(zip_path, code, "buildingpart")
    other_constructions = read_catastro_layer(zip_path, code, "otherconstruction")

    num_buildings = len(buildings)
    num_building_parts = len(building_parts)
    num_other_constructions = len(other_constructions)

    footprint_m2 = float(buildings.geometry.area.sum())
    other_construction_m2 = float(other_constructions.geometry.area.sum())

    gross_floor_area_m2 = (
        float(to_numeric(buildings["value"]).sum()) if "value" in buildings else 0.0
    )
    building_units = (
        float(to_numeric(buildings["numberOfBuildingUnits"]).sum())
        if "numberOfBuildingUnits" in buildings
        else 0.0
    )
    dwellings = (
        float(to_numeric(buildings["numberOfDwellings"]).sum())
        if "numberOfDwellings" in buildings
        else 0.0
    )

    area_m2 = area_km2 * 1_000_000

    return {
        "cod_ine": code,
        "municipio": name,
        "area_km2": area_km2,
        "num_edificios_catastro": num_buildings,
        "num_partes_edificio_catastro": num_building_parts,
        "num_otras_construcciones_catastro": num_other_constructions,
        "huella_edificada_m2": round(footprint_m2, 2),
        "superficie_construida_catastro_m2": round(gross_floor_area_m2, 2),
        "num_unidades_edificatorias_catastro": round(building_units, 2),
        "num_viviendas_catastro": round(dwellings, 2),
        "superficie_media_huella_edificio_m2": round(
            footprint_m2 / num_buildings if num_buildings else 0.0,
            2,
        ),
        "superficie_media_construida_edificio_m2": round(
            gross_floor_area_m2 / num_buildings if num_buildings else 0.0,
            2,
        ),
        "densidad_edificios_km2": round(num_buildings / area_km2, 2),
        "densidad_viviendas_catastro_km2": round(dwellings / area_km2, 2),
        "ratio_huella_edificada_pct": round((footprint_m2 / area_m2) * 100, 4),
        "intensidad_constructiva_m2_km2": round(gross_floor_area_m2 / area_km2, 2),
        "superficie_otras_construcciones_m2": round(other_construction_m2, 2),
    }


def main() -> None:
    df_ine = pd.read_csv(INE_FILE, dtype={"cod_ine": "string"})
    df_ine["cod_ine"] = df_ine["cod_ine"].str.zfill(5)

    rows = []
    for code, name in MUNICIPALITIES.items():
        area = df_ine.loc[df_ine["cod_ine"] == code, "area_km2"]
        if area.empty:
            raise ValueError(f"No se encontro area municipal para {code} - {name}")

        print(f"[READ] Procesando Catastro BU {code} - {name} ...")
        rows.append(summarize_municipality(code, name, float(area.iloc[0])))

    df_out = pd.DataFrame(rows).sort_values("cod_ine").reset_index(drop=True)
    df_out.to_csv(OUT_FILE, index=False)

    print("\nResumen generado:")
    print(df_out)
    print(f"\n[OK] Guardado en: {OUT_FILE}")
    print("\nProceso terminado.")


if __name__ == "__main__":
    main()
