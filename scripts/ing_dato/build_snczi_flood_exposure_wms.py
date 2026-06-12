"""Calcula exposicion municipal aproximada a inundacion desde SNCZI WMS.

Uso en el pipeline:
    Script operativo de Ingenieria del Dato para incorporar una fuente oficial
    adicional sobre zonas inundables. Descarga recortes WMS del SNCZI/IDEE y
    estima, por municipio, el porcentaje de superficie cubierto por cada capa.

Entradas:
    DATA/EXTERNAL/municipios_cv.geojson
    Servicio WMS oficial:
    https://servicios.idee.es/wms-inspire/riesgos-naturales/inundaciones

Salidas:
    DATA/RAW/snczi/snczi_<capa>_<resolucion>px.tif
    DATA/PROCESSED/snczi_flood_exposure_municipal.csv

Notas:
    Es una aproximacion rasterizada a partir de WMS. Para cartografia legal o
    calculos finales de precision maxima, la alternativa seria descargar las
    capas vectoriales oficiales del portal SNCZI y hacer intersecciones.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import geopandas as gpd
import numpy as np
import pandas as pd
from affine import Affine
from PIL import Image
from rasterio.features import rasterize


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "DATA"
EXTERNAL_DIR = DATA / "EXTERNAL"
RAW_DIR = DATA / "RAW" / "snczi"
PROC_DIR = DATA / "PROCESSED"

MUNICIPIOS_FILE = EXTERNAL_DIR / "municipios_cv.geojson"
OUT_FILE = PROC_DIR / "snczi_flood_exposure_municipal.csv"

WMS_BASE = "https://servicios.idee.es/wms-inspire/riesgos-naturales/inundaciones"
BBOX = (-1.75, 37.70, 0.80, 40.90)  # lon_min, lat_min, lon_max, lat_max

LAYERS = {
    "fluvial_t10": "NZ.Flood.FluvialT10",
    "fluvial_t100": "NZ.Flood.FluvialT100",
    "fluvial_t500": "NZ.Flood.FluvialT500",
    "marina_t100": "NZ.Flood.MarinaT100",
    "marina_t500": "NZ.Flood.MarinaT500",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calcula exposicion municipal aproximada a inundacion SNCZI."
    )
    parser.add_argument(
        "--resolution",
        type=int,
        default=4096,
        help="Ancho y alto del recorte WMS en pixeles. Maximo recomendado: 4096.",
    )
    parser.add_argument(
        "--layers",
        nargs="+",
        choices=sorted(LAYERS),
        default=sorted(LAYERS),
        help="Capas SNCZI a procesar.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Fuerza la descarga aunque el TIFF ya exista.",
    )
    parser.add_argument(
        "--alpha-threshold",
        type=int,
        default=0,
        help="Umbral del canal alpha para considerar un pixel inundable.",
    )
    parser.add_argument(
        "--flag-min-share",
        type=float,
        default=0.001,
        help="Porcentaje minimo de area municipal para marcar presencia relevante.",
    )
    return parser.parse_args()


def build_wms_url(layer_name: str, resolution: int) -> str:
    lon_min, lat_min, lon_max, lat_max = BBOX
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.1.1",
        "REQUEST": "GetMap",
        "LAYERS": layer_name,
        "STYLES": "",
        "SRS": "EPSG:4326",
        "BBOX": f"{lon_min},{lat_min},{lon_max},{lat_max}",
        "WIDTH": str(resolution),
        "HEIGHT": str(resolution),
        "FORMAT": "image/tiff",
        "TRANSPARENT": "true",
    }
    return f"{WMS_BASE}?{urlencode(params)}"


def download_layer(layer_key: str, resolution: int, force: bool) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RAW_DIR / f"snczi_{layer_key}_{resolution}px.tif"

    if out_path.exists() and not force:
        print(f"[SKIP] Ya existe: {out_path}")
        return out_path

    url = build_wms_url(LAYERS[layer_key], resolution)
    print(f"[DOWNLOAD] {layer_key} ({resolution}x{resolution})")

    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=180) as response:
        content_type = response.headers.get("Content-Type", "")
        data = response.read()

    header = data[:1000].lower()
    if b"serviceexception" in header or b"<html" in header:
        raise RuntimeError(
            f"La descarga WMS de {layer_key} no devolvio un TIFF valido "
            f"(Content-Type: {content_type})."
        )

    out_path.write_bytes(data)
    print(f"[OK] Guardado en: {out_path}")
    return out_path


def load_municipal_grid(resolution: int) -> tuple[gpd.GeoDataFrame, np.ndarray]:
    if not MUNICIPIOS_FILE.exists():
        raise FileNotFoundError(f"No existe el GeoJSON municipal: {MUNICIPIOS_FILE}")

    gdf = gpd.read_file(MUNICIPIOS_FILE).to_crs("EPSG:4326")
    gdf = gdf[["municipio", "CODNUT2", "CODNUT3", "geometry"]].copy()
    gdf = gdf.sort_values(["CODNUT3", "municipio"]).reset_index(drop=True)
    gdf["snczi_muni_id"] = np.arange(1, len(gdf) + 1, dtype=np.int32)

    if len(gdf) != 542:
        raise RuntimeError("El GeoJSON municipal no contiene los 542 municipios esperados.")

    lon_min, lat_min, lon_max, lat_max = BBOX
    transform = Affine(
        (lon_max - lon_min) / resolution,
        0,
        lon_min,
        0,
        -(lat_max - lat_min) / resolution,
        lat_max,
    )

    shapes = zip(gdf.geometry, gdf["snczi_muni_id"])
    municipal_grid = rasterize(
        shapes,
        out_shape=(resolution, resolution),
        transform=transform,
        fill=0,
        dtype="int32",
        all_touched=True,
    )

    pixel_counts = np.bincount(
        municipal_grid.ravel(), minlength=len(gdf) + 1
    )[1:]

    if (pixel_counts == 0).any():
        missing = gdf.loc[pixel_counts == 0, "municipio"].tolist()
        raise RuntimeError(
            "Hay municipios sin pixeles en la malla. Sube --resolution hasta 4096. "
            f"Ejemplos: {missing[:10]}"
        )

    gdf["snczi_pixeles_muestra_municipio"] = pixel_counts
    return gdf, municipal_grid


def read_flood_mask(tiff_path: Path, alpha_threshold: int) -> np.ndarray:
    with Image.open(tiff_path) as image:
        rgba = image.convert("RGBA")
        arr = np.asarray(rgba)

    alpha = arr[:, :, 3]
    if alpha.max() == 0:
        raise RuntimeError(f"La capa {tiff_path.name} no contiene pixeles visibles.")

    return alpha > alpha_threshold


def summarize_layer(
    gdf: gpd.GeoDataFrame,
    municipal_grid: np.ndarray,
    layer_key: str,
    tiff_path: Path,
    alpha_threshold: int,
    flag_min_share: float,
) -> pd.DataFrame:
    flood_mask = read_flood_mask(tiff_path, alpha_threshold)
    if flood_mask.shape != municipal_grid.shape:
        raise RuntimeError(
            f"La forma de {tiff_path.name} no coincide con la malla municipal."
        )

    n_municipios = len(gdf)
    pixel_counts = gdf["snczi_pixeles_muestra_municipio"].to_numpy()
    flood_labels = municipal_grid[flood_mask & (municipal_grid > 0)]
    flood_counts = np.bincount(flood_labels, minlength=n_municipios + 1)[1:]
    share = np.divide(
        flood_counts,
        pixel_counts,
        out=np.zeros(n_municipios, dtype=float),
        where=pixel_counts > 0,
    )

    prefix = f"snczi_{layer_key}"
    return pd.DataFrame(
        {
            f"{prefix}_pct_area_aprox": np.round(share, 6),
            f"{prefix}_pixeles_inundables": flood_counts.astype(int),
            f"{prefix}_tiene_zona_inundable": share >= flag_min_share,
        }
    )


def add_combined_columns(df: pd.DataFrame, flag_min_share: float) -> pd.DataFrame:
    for period in ["t100", "t500"]:
        cols = [
            f"snczi_{source}_{period}_pct_area_aprox"
            for source in ["fluvial", "marina"]
            if f"snczi_{source}_{period}_pct_area_aprox" in df.columns
        ]
        if not cols:
            continue

        out_col = f"snczi_inundacion_{period}_pct_area_aprox"
        df[out_col] = df[cols].max(axis=1).round(6)
        df[f"snczi_inundacion_{period}_tiene_zona_inundable"] = (
            df[out_col] >= flag_min_share
        )

    pct_cols = [col for col in df.columns if col.endswith("_pct_area_aprox")]
    if pct_cols:
        df["snczi_inundacion_max_pct_area_aprox"] = df[pct_cols].max(axis=1).round(6)

    return df


def main() -> None:
    args = parse_args()
    if args.resolution < 128 or args.resolution > 4096:
        raise ValueError("La resolucion debe estar entre 128 y 4096 pixeles.")
    if args.alpha_threshold < 0 or args.alpha_threshold > 255:
        raise ValueError("El umbral alpha debe estar entre 0 y 255.")
    if args.flag_min_share < 0 or args.flag_min_share > 1:
        raise ValueError("El umbral de presencia debe estar entre 0 y 1.")

    PROC_DIR.mkdir(parents=True, exist_ok=True)

    print("Cargando municipios y creando malla de calculo...")
    gdf, municipal_grid = load_municipal_grid(args.resolution)

    df_out = gdf[
        ["municipio", "CODNUT2", "CODNUT3", "snczi_pixeles_muestra_municipio"]
    ].copy()
    df_out["snczi_resolucion_px"] = args.resolution

    for layer_key in args.layers:
        tiff_path = download_layer(layer_key, args.resolution, args.force)
        layer_summary = summarize_layer(
            gdf,
            municipal_grid,
            layer_key,
            tiff_path,
            args.alpha_threshold,
            args.flag_min_share,
        )
        df_out = pd.concat([df_out, layer_summary], axis=1)

    df_out = add_combined_columns(df_out, args.flag_min_share)
    df_out = df_out.sort_values("municipio").reset_index(drop=True)

    n_municipios = df_out["municipio"].nunique()
    duplicados = df_out["municipio"].duplicated().sum()
    nulos = df_out.isna().sum().sum()

    print("\nValidando salida SNCZI...")
    print("Shape:", df_out.shape)
    print("Municipios:", n_municipios)
    print("Duplicados municipio:", int(duplicados))
    print("Nulos totales:", int(nulos))

    if n_municipios != 542 or duplicados != 0:
        raise RuntimeError("La salida SNCZI no contiene 542 municipios unicos.")
    if nulos != 0:
        raise RuntimeError("La salida SNCZI contiene valores nulos.")

    df_out.to_csv(OUT_FILE, index=False)
    print(f"\n[OK] CSV guardado en: {OUT_FILE}")

    ranking_col = "snczi_inundacion_t100_pct_area_aprox"
    if ranking_col not in df_out.columns:
        ranking_candidates = [
            col for col in df_out.columns if col.endswith("_pct_area_aprox")
        ]
        ranking_col = ranking_candidates[0] if ranking_candidates else ""

    if ranking_col:
        print(f"\nTop municipios por {ranking_col}:")
        top = df_out.nlargest(15, ranking_col)[["municipio", ranking_col]]
        print(top.to_string(index=False))

    print("\nProceso terminado.")


if __name__ == "__main__":
    main()
