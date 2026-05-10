from pathlib import Path
import re

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "DATA"
PROC = DATA / "PROCESSED"
FLAT_DIR = PROC / "dataset_clima_cv_extended_2019_2024.csv"

out_file = PROC / "dataset_clima_cv_extended_2019_2024_merge.csv"
tmp_file = PROC / "dataset_clima_cv_extended_2019_2024_merge.tmp.csv"

YEARS = range(2019, 2025)
MONTHS = range(1, 13)
EXPECTED_STEMS = {
    f"era5_land_cv_extended_{year}_{month:02d}_flat"
    for year in YEARS
    for month in MONTHS
}
EXTENDED_FLAT_PATTERN = re.compile(r"^era5_land_cv_extended_\d{4}_\d{2}_flat$")

all_files = sorted(FLAT_DIR.glob("era5_land_cv_extended_*_flat.csv"))
if not all_files:
    all_files = sorted(PROC.glob("era5_land_cv_extended_*_flat.csv"))

files = [
    path
    for path in all_files
    if EXTENDED_FLAT_PATTERN.match(path.stem) and path.stem in EXPECTED_STEMS
]
ignored_files = sorted(set(all_files) - set(files))
missing_stems = sorted(EXPECTED_STEMS - {path.stem for path in files})

if not files:
    raise FileNotFoundError(
        f"No se encontraron CSVs mensuales ni en {FLAT_DIR} ni en {PROC}"
    )
if missing_stems:
    missing_names = ", ".join(f"{stem}.csv" for stem in missing_stems)
    raise FileNotFoundError(
        "Faltan CSVs mensuales ERA5-Land extendidos del periodo 2019-2024: "
        f"{missing_names}"
    )

print(f"Archivos encontrados: {len(files)}")
if ignored_files:
    print("CSVs extendidos ignorados por no pertenecer al pipeline 2019-2024:")
    for path in ignored_files:
        print(f" - {path.name}")

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
