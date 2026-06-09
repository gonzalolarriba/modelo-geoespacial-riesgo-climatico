"""Comprueba el contrato minimo del consolidado ERA5-Land base.

Uso en el pipeline:
    Script auxiliar de validacion de Ingenieria del Dato.

Entrada:
    DATA/PROCESSED/dataset_clima_cv_2019_2024_merge.csv

Validaciones:
    Periodo completo 2019-2024, 72 meses, fechas esperadas y ausencia de
    nulos en el consolidado.
"""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
FILE = ROOT / "DATA" / "PROCESSED" / "dataset_clima_cv_2019_2024_merge.csv"

if not FILE.exists():
    raise FileNotFoundError(f"No se encontro el dataset consolidado: {FILE}")

rows = 0
columns: list[str] | None = None
date_min = None
date_max = None
month_counts: dict[str, int] = {}
null_counts: pd.Series | None = None

for chunk in pd.read_csv(FILE, parse_dates=["time"], chunksize=500_000):
    rows += len(chunk)
    columns = list(chunk.columns)

    current_min = chunk["time"].min()
    current_max = chunk["time"].max()
    date_min = current_min if date_min is None else min(date_min, current_min)
    date_max = current_max if date_max is None else max(date_max, current_max)

    months = chunk["time"].dt.to_period("M").astype(str).value_counts()
    for month, count in months.items():
        month_counts[month] = month_counts.get(month, 0) + int(count)

    current_nulls = chunk.isna().sum()
    null_counts = current_nulls if null_counts is None else null_counts.add(current_nulls, fill_value=0)

counts = pd.Series(month_counts).sort_index()

print("Shape:", (rows, len(columns or [])))
print("Inicio:", date_min)
print("Fin:", date_max)
print("Meses unicos:", len(counts))
print(counts.head())
print("\nResumen de filas por mes:")
print(counts.describe())
print("\nNulos por columna:")
print(null_counts.astype(int) if null_counts is not None else "Sin datos")

expected_months = pd.period_range("2019-01", "2024-12", freq="M").astype(str)
missing_months = sorted(set(expected_months) - set(counts.index))
extra_months = sorted(set(counts.index) - set(expected_months))
total_nulls = int(null_counts.sum()) if null_counts is not None else 0

print("\nContrato minimo:")
print("Meses esperados:", len(expected_months))
print("Meses faltantes:", missing_months)
print("Meses extra:", extra_months)
print("Nulos totales:", total_nulls)

assert len(counts) == len(expected_months), "El numero de meses no coincide con 2019-2024."
assert not missing_months, "Faltan meses en el dataset consolidado."
assert not extra_months, "Hay meses fuera del periodo 2019-2024."
assert str(date_min.date()) == "2019-01-01", "La fecha inicial no coincide."
assert str(date_max.date()) == "2024-12-31", "La fecha final no coincide."
assert total_nulls == 0, "Hay valores nulos en el dataset consolidado."
