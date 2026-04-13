from pathlib import Path
import pandas as pd

DATA = Path("DATA")
PROC = DATA / "PROCESSED"

files = sorted(PROC.glob("era5_land_cv_*_flat.csv"))
out_file = PROC / "dataset_clima_cv_2019_2024_merge.csv"
if not files:
    raise FileNotFoundError(f"No se encontraron CSVs en {PROC}")

print(f"Archivos encontrados: {len(files)}")
if out_file.exists():
    out_file.unlink()
first = True
for i, f in enumerate(files, start=1):
    print(f"[{i}/{len(files)}] Añadiendo: {f.name}")
    df = pd.read_csv(f)

    df.to_csv(
        out_file,
        mode="w" if first else "a",
        header=first,
        index=False
    )
    first = False

print(f"\n✅ Dataset final creado en: {out_file}")