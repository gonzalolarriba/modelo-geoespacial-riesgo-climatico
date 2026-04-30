"""Prepara una tabla municipal de contexto a partir de descargas crudas del INE.

Este script trabaja directamente con los ficheros descargados en
``DATA/EXTERNAL/ine``:

- ``alicante poblacion.xlsx``
- ``castellon poblacion.xlsx``
- ``valencia poblacion.xlsx``
- ``ine_edad_municipal.xlsx``
- ``alicante_renta.xlsx``
- ``castellon_renta.xlsx``
- ``valencia_renta.xlsx``

No descarga datos de internet. Extrae de esos Excel:

- poblacion total municipal
- porcentaje de mayores de 65 anos
- porcentaje de menores de 16 anos
- indice de envejecimiento
- renta neta media por hogar

Despues integra esas variables con la capa municipal del Notebook 1 y calcula
la densidad de poblacion.
"""

from __future__ import annotations

import argparse
import re
import unicodedata
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import geopandas as gpd
import pandas as pd


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

NS = {"a": MAIN_NS}
CV_PROVINCE_PREFIXES = {"03", "12", "46"}

ARTICLE_RE = re.compile(
    r"^(?P<base>.*?),\s*(?P<article>l'|la|el|els|les|los|las)(?P<rest>/.*)?$",
    flags=re.IGNORECASE,
)

EXPECTED_FILES = {
    "poblacion": {
        "description": "Padron municipal por provincias para Alicante, Castellon y Valencia",
        "files": [
            "alicante poblacion.xlsx",
            "castellon poblacion.xlsx",
            "valencia poblacion.xlsx",
        ],
        "required": ["cod_ine", "municipio", "poblacion_total"],
    },
    "edad": {
        "description": "Censo anual de poblacion por sexo y edad (archivo nacional completo)",
        "files": ["ine_edad_municipal.xlsx"],
        "required": [
            "cod_ine",
            "municipio",
            "mayores_65_pct",
            "menores_16_pct",
            "indice_envejecimiento",
        ],
    },
    "renta": {
        "description": "Atlas de renta por provincias con el indicador de renta neta media por hogar",
        "files": [
            "alicante_renta.xlsx",
            "castellon_renta.xlsx",
            "valencia_renta.xlsx",
        ],
        "required": ["cod_ine", "municipio", "renta_media_hogar"],
    },
}


def normalize_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = "".join(
        ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn"
    )
    text = re.sub(r"\s+", " ", text)
    return text


def reorder_trailing_article(name: str) -> str:
    text = str(name).strip()
    match = ARTICLE_RE.match(text)
    if not match:
        return text

    base = match.group("base").strip()
    article = match.group("article").strip()
    rest = match.group("rest") or ""

    if article.lower() == "l'":
        return f"{article}{base}{rest}"
    return f"{article} {base}{rest}"


def normalize_municipio_name(name: object) -> str:
    text = reorder_trailing_article(str(name))
    text = re.sub(r"\s*/\s*", "/", text.strip())
    return normalize_text(text)


def col_to_index(col: str) -> int:
    value = 0
    for ch in col:
        if ch.isalpha():
            value = value * 26 + (ord(ch.upper()) - 64)
    return value


def index_to_col(index: int) -> str:
    out = ""
    while index:
        index, rem = divmod(index - 1, 26)
        out = chr(65 + rem) + out
    return out


def fill_across(row_map: dict[str, object], upto: int) -> dict[str, str]:
    filled: dict[str, str] = {}
    current = ""
    for idx in range(1, upto + 1):
        col = index_to_col(idx)
        if col in row_map and str(row_map[col]).strip():
            current = str(row_map[col]).strip()
        if current:
            filled[col] = current
    return filled


def parse_number(value: object) -> float | pd.NA:
    if value is None or value == "":
        return pd.NA
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return pd.NA

    text = text.replace("\xa0", "").replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")

    try:
        return float(text)
    except ValueError:
        return pd.NA


def parse_year(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        year = int(float(str(value)))
    except ValueError:
        return None
    return year if 1900 <= year <= 2100 else None


def parse_age_label(label: object) -> int | None:
    text = normalize_text(label)
    match = re.match(r"^(\d+)", text)
    if not match:
        return None
    return int(match.group(1))


def parse_code_and_name(raw: object) -> tuple[str, str] | None:
    if raw is None:
        return None
    match = re.match(r"^(?P<code>\d{5})\s+(?P<name>.+?)\s*$", str(raw).strip())
    if not match:
        return None
    return match.group("code"), match.group("name")


def read_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []

    root = ET.parse(zf.open("xl/sharedStrings.xml")).getroot()
    out: list[str] = []
    for item in root.findall("a:si", NS):
        texts = [node.text or "" for node in item.findall(".//a:t", NS)]
        out.append("".join(texts))
    return out


def get_first_sheet_path(zf: zipfile.ZipFile) -> str:
    workbook = ET.parse(zf.open("xl/workbook.xml")).getroot()
    sheets = workbook.find(f"{{{MAIN_NS}}}sheets")
    if sheets is None or len(sheets) == 0:
        raise ValueError("El fichero XLSX no contiene hojas.")

    first_sheet = sheets[0]
    rel_id = first_sheet.attrib.get(f"{{{DOC_REL_NS}}}id")
    if not rel_id:
        raise ValueError("No se pudo resolver la relacion de la primera hoja.")

    rels = ET.parse(zf.open("xl/_rels/workbook.xml.rels")).getroot()
    for rel in rels.findall(f"{{{PKG_REL_NS}}}Relationship"):
        if rel.attrib.get("Id") == rel_id:
            target = rel.attrib["Target"].lstrip("/")
            return f"xl/{target}" if not target.startswith("xl/") else target

    raise ValueError("No se encontro la ruta de la primera hoja en el XLSX.")


def extract_cell_value(cell: ET.Element, shared_strings: list[str]) -> str | None:
    cell_type = cell.attrib.get("t")

    if cell_type == "inlineStr":
        texts = [node.text or "" for node in cell.findall(".//a:t", NS)]
        return "".join(texts).strip() or None

    value_node = cell.find("a:v", NS)
    if value_node is None or value_node.text is None:
        return None

    value = value_node.text
    if cell_type == "s":
        return shared_strings[int(value)]
    return value.strip()


def iter_xlsx_rows(path: Path):
    with zipfile.ZipFile(path) as zf:
        shared_strings = read_shared_strings(zf)
        sheet_path = get_first_sheet_path(zf)

        context = ET.iterparse(zf.open(sheet_path), events=("end",))
        for _, elem in context:
            if elem.tag != f"{{{MAIN_NS}}}row":
                continue

            row_num = int(elem.attrib["r"])
            row_map: dict[str, str] = {}
            for cell in elem.findall(f"{{{MAIN_NS}}}c"):
                ref = cell.attrib.get("r", "")
                match = re.match(r"([A-Z]+)", ref)
                if not match:
                    continue
                value = extract_cell_value(cell, shared_strings)
                if value is not None and value != "":
                    row_map[match.group(1)] = value

            yield row_num, row_map
            elem.clear()


def sum_row_values(row: dict[str, object], columns: list[str]) -> float | pd.NA:
    total = 0.0
    found = False
    for col in columns:
        value = parse_number(row.get(col))
        if pd.notna(value):
            total += float(value)
            found = True
    return total if found else pd.NA


def require_files(input_dir: Path, filenames: list[str]) -> list[Path]:
    paths = [input_dir / name for name in filenames]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Faltan ficheros del INE en el directorio de entrada:\n- " + "\n- ".join(missing)
        )
    return paths


def parse_population_file(path: Path) -> pd.DataFrame:
    row7: dict[str, str] = {}
    row8: dict[str, str] = {}
    filled7: dict[str, str] = {}
    selected_col: str | None = None
    records: list[dict[str, object]] = []

    for row_num, row in iter_xlsx_rows(path):
        if row_num == 7:
            row7 = row
            continue

        if row_num == 8:
            row8 = row
            max_col = max(col_to_index(col) for col in row8)
            filled7 = fill_across(row7, max_col)
            year_candidates = [
                parse_year(value)
                for col, value in row8.items()
                if normalize_text(filled7.get(col)) == "total" and parse_year(value) is not None
            ]
            if not year_candidates:
                raise ValueError(f"No se pudo identificar el ano de poblacion en {path.name}.")
            target_year = max(year_candidates)
            cols = [
                col
                for col, value in row8.items()
                if normalize_text(filled7.get(col)) == "total" and parse_year(value) == target_year
            ]
            selected_col = min(cols, key=col_to_index)
            continue

        if row_num < 9 or selected_col is None:
            continue

        parsed = parse_code_and_name(row.get("A"))
        if not parsed:
            continue

        cod_ine, municipio = parsed
        records.append(
            {
                "cod_ine": cod_ine,
                "municipio_ine": municipio,
                "municipio_norm": normalize_municipio_name(municipio),
                "poblacion_total": parse_number(row.get(selected_col)),
            }
        )

    if not records:
        raise ValueError(f"No se extrajeron municipios de poblacion desde {path.name}.")
    return pd.DataFrame(records)


def parse_population_files(input_dir: Path) -> pd.DataFrame:
    frames = [parse_population_file(path) for path in require_files(input_dir, EXPECTED_FILES["poblacion"]["files"])]
    out = pd.concat(frames, ignore_index=True)
    return drop_duplicate_norm_rows(out, "poblacion")


def parse_age_file(path: Path) -> pd.DataFrame:
    row7: dict[str, str] = {}
    row8: dict[str, str] = {}
    row9: dict[str, str] = {}
    total_col: str | None = None
    young_cols: list[str] = []
    old_cols: list[str] = []
    records: list[dict[str, object]] = []

    for row_num, row in iter_xlsx_rows(path):
        if row_num == 7:
            row7 = row
            continue

        if row_num == 8:
            row8 = row
            continue

        if row_num == 9:
            row9 = row
            max_col = max(col_to_index(col) for col in row9)
            filled7 = fill_across(row7, max_col)
            year_candidates = [
                parse_year(value)
                for col, value in row9.items()
                if normalize_text(filled7.get(col)) == "total" and parse_year(value) is not None
            ]
            if not year_candidates:
                raise ValueError(f"No se pudo identificar el ano de edad en {path.name}.")
            target_year = max(year_candidates)

            for col, value in row9.items():
                if normalize_text(filled7.get(col)) != "total":
                    continue
                if parse_year(value) != target_year:
                    continue

                age_label = normalize_text(row8.get(col))
                if age_label == "todas las edades":
                    total_col = col
                    continue

                age = parse_age_label(age_label)
                if age is None:
                    continue
                if age <= 15:
                    young_cols.append(col)
                if age >= 65:
                    old_cols.append(col)

            if total_col is None or not young_cols or not old_cols:
                raise ValueError(f"No se pudieron identificar correctamente las columnas de edad en {path.name}.")
            continue

        if row_num < 10 or total_col is None:
            continue

        parsed = parse_code_and_name(row.get("A"))
        if not parsed:
            continue

        cod_ine, municipio = parsed
        if cod_ine[:2] not in CV_PROVINCE_PREFIXES:
            continue

        total = parse_number(row.get(total_col))
        if pd.isna(total) or float(total) <= 0:
            continue

        menores_16 = sum_row_values(row, young_cols)
        mayores_65 = sum_row_values(row, old_cols)

        mayores_65_pct = pd.NA
        menores_16_pct = pd.NA
        indice_envejecimiento = pd.NA

        if pd.notna(mayores_65):
            mayores_65_pct = round(float(mayores_65) / float(total) * 100, 2)
        if pd.notna(menores_16):
            menores_16_pct = round(float(menores_16) / float(total) * 100, 2)
        if pd.notna(mayores_65) and pd.notna(menores_16) and float(menores_16) > 0:
            indice_envejecimiento = round(float(mayores_65) / float(menores_16) * 100, 2)

        records.append(
            {
                "cod_ine": cod_ine,
                "municipio_ine": municipio,
                "municipio_norm": normalize_municipio_name(municipio),
                "mayores_65_pct": mayores_65_pct,
                "menores_16_pct": menores_16_pct,
                "indice_envejecimiento": indice_envejecimiento,
            }
        )

    if not records:
        raise ValueError(f"No se extrajeron municipios de edad desde {path.name}.")
    out = pd.DataFrame(records)
    return drop_duplicate_norm_rows(out, "edad")


def parse_income_file(path: Path) -> pd.DataFrame:
    row7: dict[str, str] = {}
    row8: dict[str, str] = {}
    selected_col: str | None = None
    records: list[dict[str, object]] = []

    for row_num, row in iter_xlsx_rows(path):
        if row_num == 7:
            row7 = row
            continue

        if row_num == 8:
            row8 = row
            max_col = max(col_to_index(col) for col in row8)
            filled7 = fill_across(row7, max_col)
            year_candidates = [
                parse_year(value)
                for col, value in row8.items()
                if "renta neta media por hogar" in normalize_text(filled7.get(col))
                and parse_year(value) is not None
            ]
            if not year_candidates:
                raise ValueError(f"No se pudo identificar el ano de renta en {path.name}.")
            target_year = max(year_candidates)
            cols = [
                col
                for col, value in row8.items()
                if "renta neta media por hogar" in normalize_text(filled7.get(col))
                and parse_year(value) == target_year
            ]
            selected_col = min(cols, key=col_to_index)
            continue

        if row_num < 9 or selected_col is None:
            continue

        parsed = parse_code_and_name(row.get("A"))
        if not parsed:
            continue

        cod_ine, municipio = parsed
        records.append(
            {
                "cod_ine": cod_ine,
                "municipio_ine": municipio,
                "municipio_norm": normalize_municipio_name(municipio),
                "renta_media_hogar": parse_number(row.get(selected_col)),
            }
        )

    if not records:
        raise ValueError(f"No se extrajeron municipios de renta desde {path.name}.")
    return pd.DataFrame(records)


def parse_income_files(input_dir: Path) -> pd.DataFrame:
    frames = [parse_income_file(path) for path in require_files(input_dir, EXPECTED_FILES["renta"]["files"])]
    out = pd.concat(frames, ignore_index=True)
    return drop_duplicate_norm_rows(out, "renta")


def load_municipios_context(municipios_file: Path) -> pd.DataFrame:
    gdf = gpd.read_file(municipios_file)
    if gdf.crs is None:
        raise ValueError("La capa municipal no tiene CRS definido.")
    if "municipio" not in gdf.columns:
        raise ValueError("La capa municipal debe incluir la columna 'municipio'.")

    gdf_proj = gdf.to_crs(epsg=25830)

    out = gdf[["municipio", "CODNUT2", "CODNUT3"]].copy()
    out["area_km2"] = (gdf_proj.geometry.area / 1_000_000).round(4)
    out["municipio_norm"] = out["municipio"].map(normalize_municipio_name)
    return out


def drop_duplicate_norm_rows(df: pd.DataFrame, label: str) -> pd.DataFrame:
    dup_count = int(df.duplicated(subset=["municipio_norm"]).sum())
    if dup_count:
        print(f"[WARN] {label}: se eliminaron {dup_count} filas duplicadas por municipio normalizado.")
        df = df.drop_duplicates(subset=["municipio_norm"], keep="first").copy()
    return df


def build_ine_context(input_dir: Path, municipios_file: Path) -> pd.DataFrame:
    muni_ctx = load_municipios_context(municipios_file)

    pop_df = parse_population_files(input_dir)
    age_df = parse_age_file(require_files(input_dir, EXPECTED_FILES["edad"]["files"])[0])
    rent_df = parse_income_files(input_dir)

    ine_ctx = pop_df[["cod_ine", "municipio_norm", "poblacion_total"]].merge(
        age_df[["cod_ine", "mayores_65_pct", "menores_16_pct", "indice_envejecimiento"]],
        on="cod_ine",
        how="left",
        validate="one_to_one",
    )
    ine_ctx = ine_ctx.merge(
        rent_df[["cod_ine", "renta_media_hogar"]],
        on="cod_ine",
        how="left",
        validate="one_to_one",
    )

    out = muni_ctx.merge(
        ine_ctx,
        on="municipio_norm",
        how="left",
        validate="one_to_one",
    )

    out["densidad_poblacion"] = (out["poblacion_total"] / out["area_km2"]).round(2)

    cols = [
        "municipio",
        "CODNUT2",
        "CODNUT3",
        "area_km2",
        "cod_ine",
        "poblacion_total",
        "densidad_poblacion",
        "mayores_65_pct",
        "menores_16_pct",
        "indice_envejecimiento",
        "renta_media_hogar",
    ]
    out = out[cols].sort_values(["CODNUT3", "municipio"]).reset_index(drop=True)
    return out


def build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Armoniza descargas municipales del INE y genera una tabla de contexto."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("DATA/EXTERNAL/ine"),
        help="Directorio con los ficheros crudos del INE.",
    )
    parser.add_argument(
        "--municipios-file",
        type=Path,
        default=Path("DATA/EXTERNAL/municipios_cv.geojson"),
        help="GeoJSON municipal generado en el Notebook 1.",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=Path("DATA/PROCESSED/ine_contexto_municipal.csv"),
        help="Ruta del CSV de salida.",
    )
    return parser


def main() -> None:
    parser = build_argparser()
    args = parser.parse_args()

    df = build_ine_context(args.input_dir, args.municipios_file)
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output_file, index=False)

    print("Salida generada en:", args.output_file)
    print("Shape:", df.shape)
    print("Municipios:", df["municipio"].nunique())
    print("Nulos por columna:")
    print(df.isna().sum())


if __name__ == "__main__":
    main()
