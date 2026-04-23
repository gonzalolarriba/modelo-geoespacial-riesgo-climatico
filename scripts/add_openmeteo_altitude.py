"""
Obtiene la altitud de las coordenadas municipales usadas en el TFG.

Entrada:
    DATA/PROCESSED/dataset_cv_municipios_enriched.csv

Salida:
    DATA/PROCESSED/municipios_altitud_openmeteo.csv

La altitud se consulta solo una vez por coordenada unica. Despues se replica en
los municipios que comparten esa misma coordenada ERA5-Land.
"""

from __future__ import annotations

import time
from collections import defaultdict
from pathlib import Path

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "DATA" / "PROCESSED"

INPUT_FILE = PROCESSED_DIR / "dataset_cv_municipios_enriched.csv"
OUTPUT_FILE = PROCESSED_DIR / "municipios_altitud_openmeteo.csv"
REPORT_FILE = PROCESSED_DIR / "municipios_altitud_openmeteo_report.txt"

LAT_COL = "lat"
LON_COL = "lon"
ALT_COL = "altitud_m"

BATCH_SIZE = 50
TIMEOUT_SECONDS = 30
SLEEP_SECONDS = 1.5
MAX_ATTEMPTS = 3
COORD_PRECISION = 5


def normalize_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte lat/lon a numerico y elimina coordenadas invalidas."""
    df = df.copy()

    for col in [LAT_COL, LON_COL]:
        if df[col].dtype == object:
            df[col] = df[col].astype(str).str.replace(",", ".", regex=False).str.strip()
        df[col] = pd.to_numeric(df[col], errors="coerce")

    valid = df[LAT_COL].between(-90, 90) & df[LON_COL].between(-180, 180)
    invalid_count = int((~valid).sum())
    if invalid_count:
        print(f"[WARN] Coordenadas invalidas omitidas: {invalid_count}", flush=True)

    return df.loc[valid].copy()


def prepare_municipal_table() -> pd.DataFrame:
    """Crea una tabla con una fila por municipio y coordenada asignada."""
    required_cols = ["municipio", "CODNUT2", "CODNUT3", LAT_COL, LON_COL]
    optional_cols = ["cod_ine", "area_km2", "poblacion_total", "densidad_poblacion"]

    available_cols = pd.read_csv(INPUT_FILE, nrows=0).columns.tolist()
    missing = [col for col in required_cols if col not in available_cols]
    if missing:
        raise ValueError(f"Faltan columnas obligatorias en {INPUT_FILE}: {missing}")

    usecols = required_cols + [col for col in optional_cols if col in available_cols]
    df = pd.read_csv(INPUT_FILE, usecols=usecols)
    df = df.drop_duplicates(subset=["municipio", "CODNUT2", "CODNUT3"])
    df = normalize_coordinates(df)
    df[ALT_COL] = pd.NA

    return df.reset_index(drop=True)


def load_checkpoint_or_prepare() -> pd.DataFrame:
    """Permite reanudar si el CSV de salida ya existe."""
    if OUTPUT_FILE.exists():
        df = pd.read_csv(OUTPUT_FILE)
        if ALT_COL not in df.columns:
            df[ALT_COL] = pd.NA
        print(f"[INFO] Reanudando desde: {OUTPUT_FILE}", flush=True)
        return normalize_coordinates(df)

    print(f"[INFO] Leyendo dataset de entrada: {INPUT_FILE}", flush=True)
    df = prepare_municipal_table()
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"[INFO] Municipios preparados: {len(df)}", flush=True)
    print(f"[INFO] Checkpoint inicial creado: {OUTPUT_FILE}", flush=True)
    return df


def request_elevations(latitudes: list[float], longitudes: list[float]) -> list[float | None]:
    """Consulta Open-Meteo Elevation para un lote de coordenadas."""
    url = "https://api.open-meteo.com/v1/elevation"
    params = {
        "latitude": ",".join(f"{lat:.10f}" for lat in latitudes),
        "longitude": ",".join(f"{lon:.10f}" for lon in longitudes),
    }

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(
            f"[INFO] Open-Meteo: {len(latitudes)} coordenadas "
            f"(intento {attempt}/{MAX_ATTEMPTS})",
            flush=True,
        )

        try:
            response = requests.get(url, params=params, timeout=TIMEOUT_SECONDS)

            if response.status_code == 429:
                wait_seconds = 60
                print(f"[WARN] Rate limit. Esperando {wait_seconds}s.", flush=True)
                time.sleep(wait_seconds)
                continue

            response.raise_for_status()
            data = response.json()
            values = data.get("elevation")

            if not values:
                print(f"[WARN] Respuesta sin altitud: {data}", flush=True)
                return [None] * len(latitudes)

            if len(values) != len(latitudes):
                print("[WARN] Respuesta con longitud inesperada.", flush=True)
                return (values + [None] * len(latitudes))[: len(latitudes)]

            return values

        except requests.RequestException as exc:
            wait_seconds = 5 * attempt
            print(f"[WARN] Error de conexion: {exc}", flush=True)
            if attempt < MAX_ATTEMPTS:
                print(f"[INFO] Reintentando en {wait_seconds}s.", flush=True)
                time.sleep(wait_seconds)

    print("[STOP] No se pudo conectar con Open-Meteo. Reintenta mas tarde.", flush=True)
    return [None] * len(latitudes)


def build_coordinate_groups(df: pd.DataFrame) -> dict[tuple[float, float], list[int]]:
    """Agrupa municipios que comparten la misma coordenada climatica."""
    groups: dict[tuple[float, float], list[int]] = defaultdict(list)

    pending = df[df[ALT_COL].isna()]
    for idx, row in pending.iterrows():
        coord = (
            round(float(row[LAT_COL]), COORD_PRECISION),
            round(float(row[LON_COL]), COORD_PRECISION),
        )
        groups[coord].append(idx)

    return groups


def write_report(df: pd.DataFrame) -> None:
    missing = df[df[ALT_COL].isna()]

    with REPORT_FILE.open("w", encoding="utf-8") as file:
        file.write("REPORTE DE ALTITUD MUNICIPAL\n")
        file.write("============================\n\n")
        file.write(f"Municipios totales: {len(df)}\n")
        file.write(f"Municipios con altitud: {len(df) - len(missing)}\n")
        file.write(f"Municipios sin altitud: {len(missing)}\n")

        if not missing.empty:
            file.write("\nMunicipios sin altitud:\n")
            file.write("\n".join(missing["municipio"].astype(str).tolist()))


def main() -> None:
    df = load_checkpoint_or_prepare()
    groups = build_coordinate_groups(df)

    if not groups:
        print("[OK] No quedan municipios pendientes.", flush=True)
        write_report(df)
        return

    unique_coords = list(groups.keys())
    print(f"[INFO] Municipios totales: {len(df)}", flush=True)
    print(f"[INFO] Coordenadas unicas pendientes: {len(unique_coords)}", flush=True)

    for start in range(0, len(unique_coords), BATCH_SIZE):
        chunk = unique_coords[start : start + BATCH_SIZE]
        latitudes = [lat for lat, _ in chunk]
        longitudes = [lon for _, lon in chunk]

        elevations = request_elevations(latitudes, longitudes)

        for coord, elevation in zip(chunk, elevations):
            df.loc[groups[coord], ALT_COL] = elevation

        df.to_csv(OUTPUT_FILE, index=False)
        print(
            f"[INFO] Lote guardado: {start + len(chunk)}/{len(unique_coords)} "
            f"coordenadas unicas.",
            flush=True,
        )
        time.sleep(SLEEP_SECONDS)

    write_report(df)
    print(f"[OK] Archivo generado: {OUTPUT_FILE}", flush=True)
    print(f"[OK] Reporte generado: {REPORT_FILE}", flush=True)


if __name__ == "__main__":
    main()
