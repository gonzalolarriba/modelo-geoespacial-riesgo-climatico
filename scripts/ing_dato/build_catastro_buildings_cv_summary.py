from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
from pyogrio.errors import DataLayerError


ROOT = Path(__file__).resolve().parents[2]
PROC_DIR = ROOT / "DATA" / "PROCESSED"
RAW_DIR = ROOT / "DATA" / "RAW" / "catastro" / "buildings"

INE_FILE = PROC_DIR / "ine_contexto_municipal.csv"
STATUS_FILE = PROC_DIR / "catastro_buildings_cv_download_status.csv"
OUT_FILE = PROC_DIR / "catastro_buildings_cv_summary.csv"
REPORT_FILE = PROC_DIR / "catastro_buildings_cv_processing_report.csv"


def load_cv_municipalities() -> pd.DataFrame:
    df_ine = pd.read_csv(
        INE_FILE,
        dtype={"cod_ine": "string"},
        usecols=["cod_ine", "municipio", "area_km2"],
    )
    df_ine["cod_ine"] = df_ine["cod_ine"].str.zfill(5)
    df_ine = df_ine.drop_duplicates("cod_ine")

    if not STATUS_FILE.exists():
        raise FileNotFoundError(
            "No existe el estado de descarga de Catastro. Ejecuta antes "
            "download_catastro_buildings_cv.py."
        )

    df_status = pd.read_csv(
        STATUS_FILE,
        dtype={"cod_ine": "string", "catastro_code": "string"},
    )
    df_status["cod_ine"] = df_status["cod_ine"].str.zfill(5)
    df_status["catastro_code"] = df_status["catastro_code"].fillna("")
    has_code = df_status["catastro_code"].str.strip() != ""
    df_status.loc[has_code, "catastro_code"] = df_status.loc[
        has_code, "catastro_code"
    ].str.zfill(5)

    df = df_ine.merge(
        df_status[
            [
                "cod_ine",
                "catastro_code",
                "catastro_name",
                "status",
                "path",
                "exists_after",
            ]
        ],
        on="cod_ine",
        how="left",
        validate="one_to_one",
    )
    return df.sort_values("cod_ine").reset_index(drop=True)


def build_gml_path(zip_path: Path, catastro_code: str, layer: str) -> str:
    zip_posix = zip_path.resolve().as_posix()
    return f"/vsizip/{zip_posix}/A.ES.SDGC.BU.{catastro_code}.{layer}.gml"


def read_catastro_layer(zip_path: Path, catastro_code: str, layer: str) -> gpd.GeoDataFrame:
    gml_path = build_gml_path(zip_path, catastro_code, layer)
    try:
        gdf = gpd.read_file(gml_path)
    except (DataLayerError, IndexError):
        # Algunos municipios tienen capas GML validas pero sin entidades para
        # buildingpart u otherconstruction. Se representan como capas vacias.
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:25830")

    if gdf.crs is None:
        raise ValueError(f"La capa {layer} de {catastro_code} no tiene CRS informado.")

    if gdf.crs.to_epsg() != 25830:
        gdf = gdf.to_crs(25830)

    return gdf


def to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def summarize_municipality(row: pd.Series) -> dict[str, float | str]:
    code = str(row["cod_ine"]).zfill(5)
    municipality = str(row["municipio"])
    catastro_code = str(row["catastro_code"]).strip()
    catastro_name = str(row.get("catastro_name", ""))
    if not catastro_code:
        raise FileNotFoundError(f"No hay codigo Catastro asociado a {code} - {municipality}")
    catastro_code = catastro_code.zfill(5)
    area_km2 = float(row["area_km2"])
    zip_path = Path(str(row.get("path", "")))
    if not zip_path.is_absolute():
        zip_path = RAW_DIR / f"A.ES.SDGC.BU.{catastro_code}.zip"

    if not zip_path.exists():
        raise FileNotFoundError(f"No existe el ZIP de Catastro: {zip_path}")

    buildings = read_catastro_layer(zip_path, catastro_code, "building")
    building_parts = read_catastro_layer(zip_path, catastro_code, "buildingpart")
    other_constructions = read_catastro_layer(zip_path, catastro_code, "otherconstruction")

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
        "municipio": municipality,
        "catastro_code": catastro_code,
        "catastro_name": catastro_name,
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
    municipalities = load_cv_municipalities()
    rows = []
    report_rows = []

    for idx, row in municipalities.iterrows():
        code = str(row["cod_ine"]).zfill(5)
        municipality = str(row["municipio"])
        print(f"[READ] {idx + 1:03d}/{len(municipalities)} {code} - {municipality}")

        try:
            rows.append(summarize_municipality(row))
            status = "ok"
            message = ""
        except Exception as exc:
            status = "error"
            message = str(exc)
            print(f"[WARN] {code} - {municipality}: {message}")

        report_rows.append(
            {
                "cod_ine": code,
                "municipio": municipality,
                "catastro_code": row.get("catastro_code", ""),
                "catastro_name": row.get("catastro_name", ""),
                "status": status,
                "message": message,
            }
        )

    df_report = pd.DataFrame(report_rows)
    df_report.to_csv(REPORT_FILE, index=False)

    if rows:
        df_out = pd.DataFrame(rows).sort_values("cod_ine").reset_index(drop=True)
        df_out.to_csv(OUT_FILE, index=False)
        print(f"\n[OK] Resumen guardado en: {OUT_FILE}")
        print("Shape:", df_out.shape)
        print("Municipios procesados:", df_out["cod_ine"].nunique())
    else:
        print("\n[WARN] No se genero resumen porque no se pudo procesar ningun municipio.")

    print(f"[OK] Informe guardado en: {REPORT_FILE}")
    print("\nEstado del procesamiento:")
    print(df_report["status"].value_counts(dropna=False))
    print("\nProceso terminado.")


if __name__ == "__main__":
    main()
