from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "DATA"
PROC = DATA / "PROCESSED"

BASE_MUNICIPAL_FILE = PROC / "dataset_cv_municipios.csv"
EXTENDED_FILE = PROC / "dataset_clima_cv_extended_2019_2024_merge.csv"
OUT_FILE = PROC / "dataset_cv_municipios_climate_extended.csv"
TMP_FILE = PROC / "dataset_cv_municipios_climate_extended.tmp.csv"

CHUNKSIZE = 500_000
KEYS = ["municipio", "CODNUT2", "CODNUT3", "fecha"]


if not BASE_MUNICIPAL_FILE.exists():
    raise FileNotFoundError(f"No se encontro el dataset municipal base: {BASE_MUNICIPAL_FILE}")

if not EXTENDED_FILE.exists():
    raise FileNotFoundError(f"No se encontro el consolidado extendido: {EXTENDED_FILE}")


print("Cargando asignacion municipal validada del Notebook 1...")
muni_lookup = pd.read_csv(
    BASE_MUNICIPAL_FILE,
    usecols=["municipio", "CODNUT2", "CODNUT3", "lon", "lat", "dist_metros"],
)

muni_lookup = (
    muni_lookup
    .drop_duplicates(subset=["municipio", "CODNUT2", "CODNUT3", "lon", "lat"])
    .copy()
)
muni_lookup["lon_key"] = muni_lookup["lon"].round(4)
muni_lookup["lat_key"] = muni_lookup["lat"].round(4)

print("Municipios en lookup:", muni_lookup["municipio"].nunique())
print("Filas lookup:", len(muni_lookup))

if muni_lookup["municipio"].nunique() != 542:
    raise RuntimeError("La asignacion municipal no contiene los 542 municipios esperados.")


instant_parts = []
accumulated_parts = []
rows_read = 0
rows_joined = 0

print("\nProcesando consolidado extendido por chunks...")

for i, chunk in enumerate(pd.read_csv(EXTENDED_FILE, parse_dates=["time"], chunksize=CHUNKSIZE), start=1):
    rows_read += len(chunk)
    chunk["lon_key"] = chunk["lon"].round(4)
    chunk["lat_key"] = chunk["lat"].round(4)

    df = chunk.merge(
        muni_lookup,
        on=["lon_key", "lat_key"],
        how="inner",
        suffixes=("_era5", ""),
    )
    rows_joined += len(df)

    if df.empty:
        print(f"[{i}] Chunk sin municipios asignados")
        continue

    df["fecha"] = df["time"].dt.floor("D")

    instant_daily = (
        df
        .groupby(KEYS, as_index=False)
        .agg(
            lon=("lon", "mean"),
            lat=("lat", "mean"),
            dist_metros=("dist_metros", "mean"),
            dewpoint_sum=("dewpoint_c", "sum"),
            dewpoint_count=("dewpoint_c", "count"),
            dewpoint_max_dia=("dewpoint_c", "max"),
            dewpoint_min_dia=("dewpoint_c", "min"),
            presion_sum=("surface_pressure_hpa", "sum"),
            presion_count=("surface_pressure_hpa", "count"),
            presion_superficie_max_hpa=("surface_pressure_hpa", "max"),
            presion_superficie_min_hpa=("surface_pressure_hpa", "min"),
            humedad_suelo_sum=("soil_water_layer1_m3_m3", "sum"),
            humedad_suelo_count=("soil_water_layer1_m3_m3", "count"),
            humedad_suelo_capa1_max_m3_m3=("soil_water_layer1_m3_m3", "max"),
            humedad_suelo_capa1_min_m3_m3=("soil_water_layer1_m3_m3", "min"),
        )
    )
    instant_parts.append(instant_daily)

    # Las variables acumuladas de ERA5-Land cierran la hora anterior. Se aplica
    # el mismo desplazamiento usado para la precipitacion en el Notebook 1.
    df_acc = df.copy()
    df_acc["fecha"] = (df_acc["time"] - pd.Timedelta(hours=1)).dt.floor("D")
    df_acc = df_acc[df_acc["fecha"].between("2019-01-01", "2024-12-31")].copy()

    accumulated_daily = (
        df_acc
        .groupby(KEYS, as_index=False)
        .agg(
            runoff_superficial_total_dia_mm=("surface_runoff_mm", "max"),
            radiacion_solar_total_dia_mj_m2=("solar_radiation_mj_m2", "max"),
        )
    )
    accumulated_parts.append(accumulated_daily)

    print(f"[{i}] Leidas: {rows_read:,} | Asignadas: {rows_joined:,}")


if not instant_parts:
    raise RuntimeError("No se genero ninguna agregacion diaria instantanea.")

if not accumulated_parts:
    raise RuntimeError("No se genero ninguna agregacion diaria acumulada.")


print("\nConsolidando agregaciones parciales...")

instant_all = pd.concat(instant_parts, ignore_index=True)
instant_final = (
    instant_all
    .groupby(KEYS, as_index=False)
    .agg(
        lon=("lon", "mean"),
        lat=("lat", "mean"),
        dist_metros=("dist_metros", "mean"),
        dewpoint_sum=("dewpoint_sum", "sum"),
        dewpoint_count=("dewpoint_count", "sum"),
        dewpoint_max_dia=("dewpoint_max_dia", "max"),
        dewpoint_min_dia=("dewpoint_min_dia", "min"),
        presion_sum=("presion_sum", "sum"),
        presion_count=("presion_count", "sum"),
        presion_superficie_max_hpa=("presion_superficie_max_hpa", "max"),
        presion_superficie_min_hpa=("presion_superficie_min_hpa", "min"),
        humedad_suelo_sum=("humedad_suelo_sum", "sum"),
        humedad_suelo_count=("humedad_suelo_count", "sum"),
        humedad_suelo_capa1_max_m3_m3=("humedad_suelo_capa1_max_m3_m3", "max"),
        humedad_suelo_capa1_min_m3_m3=("humedad_suelo_capa1_min_m3_m3", "min"),
    )
)

instant_final["dewpoint_media_dia"] = (
    instant_final["dewpoint_sum"] / instant_final["dewpoint_count"]
)
instant_final["presion_superficie_media_hpa"] = (
    instant_final["presion_sum"] / instant_final["presion_count"]
)
instant_final["humedad_suelo_capa1_media_m3_m3"] = (
    instant_final["humedad_suelo_sum"] / instant_final["humedad_suelo_count"]
)

instant_final = instant_final.drop(
    columns=[
        "dewpoint_sum",
        "dewpoint_count",
        "presion_sum",
        "presion_count",
        "humedad_suelo_sum",
        "humedad_suelo_count",
    ]
)

accumulated_all = pd.concat(accumulated_parts, ignore_index=True)
accumulated_final = (
    accumulated_all
    .groupby(KEYS, as_index=False)
    .agg(
        runoff_superficial_total_dia_mm=("runoff_superficial_total_dia_mm", "max"),
        radiacion_solar_total_dia_mj_m2=("radiacion_solar_total_dia_mj_m2", "max"),
    )
)

df_final = (
    instant_final
    .merge(accumulated_final, on=KEYS, how="left", validate="one_to_one")
    .sort_values(["municipio", "fecha"])
    .reset_index(drop=True)
)

cols = [
    "municipio",
    "CODNUT2",
    "CODNUT3",
    "fecha",
    "lon",
    "lat",
    "dist_metros",
    "dewpoint_media_dia",
    "dewpoint_max_dia",
    "dewpoint_min_dia",
    "presion_superficie_media_hpa",
    "presion_superficie_max_hpa",
    "presion_superficie_min_hpa",
    "runoff_superficial_total_dia_mm",
    "humedad_suelo_capa1_media_m3_m3",
    "humedad_suelo_capa1_max_m3_m3",
    "humedad_suelo_capa1_min_m3_m3",
    "radiacion_solar_total_dia_mj_m2",
]
df_final = df_final[cols]


print("\nValidando dataset municipal extendido...")

n_municipios = df_final["municipio"].nunique()
n_fechas = df_final["fecha"].nunique()
filas_esperadas = n_municipios * n_fechas
duplicados = df_final.duplicated(subset=["municipio", "fecha"]).sum()
nulos = df_final.isna().sum().sum()
dias_por_municipio = df_final.groupby("municipio")["fecha"].nunique()
municipios_incompletos = (dias_por_municipio < dias_por_municipio.max()).sum()

print("Shape:", df_final.shape)
print("Municipios:", n_municipios)
print("Fechas:", n_fechas)
print("Filas esperadas:", filas_esperadas)
print("Duplicados municipio-fecha:", duplicados)
print("Nulos totales:", nulos)
print("Municipios con cobertura incompleta:", municipios_incompletos)
print("Rango temporal:", df_final["fecha"].min(), "->", df_final["fecha"].max())
print("Distancia maxima municipio-celda (m):", round(df_final["dist_metros"].max(), 2))

assert n_municipios == 542, "No estan representados los 542 municipios"
assert n_fechas == 2192, "No estan representadas las 2192 fechas esperadas"
assert len(df_final) == 542 * 2192, "El numero de filas no coincide con municipios x fechas"
assert duplicados == 0, "Existen duplicados municipio-fecha"
assert nulos == 0, "Existen valores nulos en el dataset municipal extendido"
assert municipios_incompletos == 0, "Existen municipios con cobertura incompleta"

if TMP_FILE.exists():
    TMP_FILE.unlink()

df_final.to_csv(TMP_FILE, index=False)
TMP_FILE.replace(OUT_FILE)

print(f"\nDataset municipal extendido creado en: {OUT_FILE}")
