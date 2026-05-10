from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

import pandas as pd
import requests


PROVINCE_ATOM_URL_TEMPLATE = (
    "http://www.catastro.hacienda.gob.es/INSPIRE/buildings/"
    "{province_code}/ES.SDGC.bu.atom_{province_code}.xml"
)

ROOT = Path(__file__).resolve().parents[2]
PROC_DIR = ROOT / "DATA" / "PROCESSED"
RAW_DIR = ROOT / "DATA" / "RAW" / "catastro" / "buildings"
RAW_DIR.mkdir(parents=True, exist_ok=True)

INE_FILE = PROC_DIR / "ine_contexto_municipal.csv"
STATUS_FILE = PROC_DIR / "catastro_buildings_cv_download_status.csv"

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
MAX_ATOM_FEEDS = 50
MANUAL_CATASTRO_CODE_OVERRIDES = {
    "03014": "03900",  # Alacant/Alicante
    "03901": "03126",  # els Poblets
    "03902": "03142",  # Pilar de la Horadada
    "03903": "03141",  # Los Montesinos
    "03904": "03143",  # San Isidro
    "12040": "12900",  # Castello de la Plana
    "12901": "12143",  # les Alqueries/Alquerias del Nino Perdido
    "12902": "12144",  # Sant Joan de Moro
    "46178": "46180",  # Naquera
    "46180": "46182",  # Novetle
    "46205": "46207",  # Pucol
    "46250": "46900",  # Valencia
}


def normalize_text(value: object) -> str:
    text = str(value).strip().lower()
    text = "".join(
        ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn"
    )
    text = text.replace("/", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def name_keys(value: object) -> set[str]:
    normalized = normalize_text(value)
    tokens = normalized.split()
    keys = {normalized, " ".join(sorted(tokens))}

    if "/" in str(value):
        parts = [normalize_text(part) for part in str(value).split("/") if part.strip()]
        if parts:
            keys.add(" ".join(parts))
            keys.add(" ".join(reversed(parts)))
            keys.add(" ".join(sorted(" ".join(parts).split())))

    return {key for key in keys if key}


def load_cv_municipalities() -> pd.DataFrame:
    df = pd.read_csv(INE_FILE, dtype={"cod_ine": "string"})
    df["cod_ine"] = df["cod_ine"].str.zfill(5)
    df = df[["cod_ine", "municipio"]].drop_duplicates().sort_values("cod_ine")
    df["province_code"] = df["cod_ine"].str[:2]
    return df.reset_index(drop=True)


def fetch_atom(url: str) -> ET.Element:
    print(f"[ATOM] Leyendo indice: {url}")
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return ET.fromstring(response.content)


def iter_atom_links(feed: ET.Element, base_url: str):
    for entry in feed.findall("atom:entry", ATOM_NS):
        title = entry.findtext("atom:title", default="", namespaces=ATOM_NS)
        for link in entry.findall("atom:link", ATOM_NS):
            href = link.attrib.get("href", "").strip()
            if not href:
                continue

            yield {
                "title": title,
                "url": urljoin(base_url, href),
                "type": link.attrib.get("type", "").lower(),
                "rel": link.attrib.get("rel", "").lower(),
            }


def is_atom_link(link: dict[str, str]) -> bool:
    url_path = urlparse(link["url"]).path.lower()
    return "atom+xml" in link["type"] or url_path.endswith(".atom.xml")


def is_zip_link(link: dict[str, str]) -> bool:
    url_path = urlparse(link["url"]).path.lower()
    return "zip" in link["type"] or url_path.endswith(".zip")


def extract_municipality_code(url: str) -> str | None:
    filename = Path(urlparse(url).path).name
    match = re.search(r"\.BU\.(\d{5})\.zip$", filename, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def parse_catalog_title(title: str) -> tuple[str | None, str]:
    text = str(title).replace(" buildings", "").replace(" Buildings", "").strip()
    match = re.match(r"^(?P<code>\d{5})-(?P<name>.+)$", text)
    if not match:
        return None, text
    return match.group("code"), match.group("name").strip()


def build_catalog(province_codes: set[str]) -> pd.DataFrame:
    pending = [
        PROVINCE_ATOM_URL_TEMPLATE.format(province_code=province_code)
        for province_code in sorted(province_codes)
    ]
    visited: set[str] = set()
    rows = []

    while pending:
        atom_url = pending.pop(0)
        if atom_url in visited:
            continue
        if len(visited) >= MAX_ATOM_FEEDS:
            raise RuntimeError("Se alcanzo el limite de indices ATOM revisados.")

        visited.add(atom_url)
        feed = fetch_atom(atom_url)

        for link in iter_atom_links(feed, atom_url):
            if is_zip_link(link):
                catastro_code = extract_municipality_code(link["url"])
                title_code, title_name = parse_catalog_title(link["title"])
                if catastro_code is None:
                    catastro_code = title_code
                if catastro_code is None:
                    continue

                rows.append(
                    {
                        "catastro_code": catastro_code,
                        "province_code": catastro_code[:2],
                        "catastro_name": title_name,
                        "catastro_title": link["title"],
                        "url": link["url"],
                        "keys": name_keys(title_name),
                    }
                )
                continue

            if is_atom_link(link) and link["url"] not in visited:
                pending.append(link["url"])

    return pd.DataFrame(rows)


def match_catalog_row(
    municipality_row: pd.Series,
    catalog: pd.DataFrame,
) -> tuple[pd.Series | None, str]:
    cod_ine = str(municipality_row["cod_ine"])
    province_code = str(municipality_row["province_code"])
    candidates = catalog[catalog["province_code"] == province_code].copy()

    override_code = MANUAL_CATASTRO_CODE_OVERRIDES.get(cod_ine)
    if override_code:
        match = catalog[catalog["catastro_code"] == override_code]
        if not match.empty:
            return match.iloc[0], "manual_override"

    municipality_keys = name_keys(municipality_row["municipio"])
    for _, candidate in candidates.iterrows():
        if municipality_keys & candidate["keys"]:
            return candidate, "name_match"

    code_match = candidates[candidates["catastro_code"] == cod_ine]
    if not code_match.empty:
        return code_match.iloc[0], "code_match"

    return None, "missing_link"


def download_file(url: str, out_path: Path) -> None:
    tmp_path = out_path.with_name(out_path.name + ".part")
    response = requests.get(url, stream=True, timeout=180)
    response.raise_for_status()

    with tmp_path.open("wb") as file:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                file.write(chunk)

    tmp_path.replace(out_path)


def main() -> None:
    municipalities = load_cv_municipalities()
    print(f"Municipios CV esperados: {len(municipalities)}")
    catalog = build_catalog(set(municipalities["province_code"]))
    print(f"Entradas ATOM de Catastro revisadas en provincias CV: {len(catalog)}")

    rows = []
    for idx, row in municipalities.iterrows():
        code = str(row["cod_ine"])
        municipality = str(row["municipio"])
        catalog_row, match_method = match_catalog_row(row, catalog)

        if catalog_row is None:
            print(f"[WARN] {idx + 1:03d}/{len(municipalities)} Sin enlace: {code} - {municipality}")
            rows.append(
                {
                    "cod_ine": code,
                    "municipio": municipality,
                    "catastro_code": "",
                    "catastro_name": "",
                    "status": "missing_link",
                    "match_method": match_method,
                    "url": "",
                    "path": "",
                    "exists_after": False,
                    "size_bytes": 0,
                }
            )
            continue

        catastro_code = str(catalog_row["catastro_code"])
        catastro_name = str(catalog_row["catastro_name"])
        url = str(catalog_row["url"])
        out_path = RAW_DIR / f"A.ES.SDGC.BU.{catastro_code}.zip"
        status = "exists" if out_path.exists() else "pending"

        if out_path.exists():
            print(
                f"[SKIP] {idx + 1:03d}/{len(municipalities)} "
                f"{code}->{catastro_code} Ya existe"
            )
        else:
            print(
                f"[DOWNLOAD] {idx + 1:03d}/{len(municipalities)} "
                f"{code}->{catastro_code} {municipality}"
            )
            download_file(url, out_path)
            status = "downloaded"
            print(f"[OK] Guardado en: {out_path}")

        rows.append(
            {
                "cod_ine": code,
                "municipio": municipality,
                "catastro_code": catastro_code,
                "catastro_name": catastro_name,
                "status": status,
                "match_method": match_method,
                "url": url,
                "path": str(out_path),
                "exists_after": out_path.exists(),
                "size_bytes": out_path.stat().st_size if out_path.exists() else 0,
            }
        )

    df_status = pd.DataFrame(rows)
    df_status.to_csv(STATUS_FILE, index=False)

    print("\nResumen descarga Catastro BU CV:")
    print(df_status["status"].value_counts(dropna=False))
    print(f"\n[OK] Estado guardado en: {STATUS_FILE}")
    print("\nProceso terminado.")


if __name__ == "__main__":
    main()
