from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "DATA"
PROC = DATA / "PROCESSED"
FLAT_DIR = PROC / "dataset_clima_cv_2019_2024.csv"

out_file = PROC / "dataset_clima_cv_2019_2024_merge.csv"
tmp_file = PROC / "dataset_clima_cv_2019_2024_merge.tmp.csv"

files = sorted(FLAT_DIR.glob("era5_land_cv_*_flat.csv"))
if not files:
    files = sorted(PROC.glob("era5_land_cv_*_flat.csv"))

if not files:
    raise FileNotFoundError(
        f"No se encontraron CSVs mensuales ni en {FLAT_DIR} ni en {PROC}"
    )

print(f"Archivos encontrados: {len(files)}")

if tmp_file.exists():
    tmp_file.unlink()

first = True
for i, path in enumerate(files, start=1):
    print(f"[{i}/{len(files)}] Anadiendo: {path.name}")
    for chunk in pd.read_csv(path, chunksize=200_000):
        chunk.to_csv(
            tmp_file,
            mode="w" if first else "a",
            header=first,
            index=False,
        )
        first = False

tmp_file.replace(out_file)
print(f"\nDataset final creado en: {out_file}")
