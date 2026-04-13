import pandas as pd
from pathlib import Path

file = Path("DATA/PROCESSED/dataset_clima_cv_2019_2024_merge.csv")

df = pd.read_csv(file)

print("Shape:", df.shape)
df["time"] = pd.to_datetime(df["time"])

print("Inicio:", df["time"].min())
print("Fin:", df["time"].max())
df["year_month"] = df["time"].dt.to_period("M")

print("Meses únicos:", df["year_month"].nunique())
counts = df.groupby("year_month").size()

print(counts.head())
print("\nMeses con menos datos:")
print(counts.describe())
print(df.isna().sum())