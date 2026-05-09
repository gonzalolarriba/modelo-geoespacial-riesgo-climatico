from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

import requests


ATOM_URL = (
    "https://www.catastro.hacienda.gob.es/INSPIRE/buildings/ES.SDGC.BU.atom.xml"
)

# Piloto pequeno y editable: un municipio por provincia de la Comunitat Valenciana.
# El codigo corresponde al codigo municipal de 5 digitos usado por Catastro/INE.
MUNICIPALITIES = {
    "03002": "Agost",
    "12080": "Morella",
    "46181": "Oliva",
}

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "DATA" / "RAW" / "catastro" / "buildings"
RAW_DIR.mkdir(parents=True, exist_ok=True)

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
MAX_ATOM_FEEDS = 200


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


def discover_building_zip_links(codes: set[str]) -> dict[str, str]:
    pending = [ATOM_URL]
    visited: set[str] = set()
    found: dict[str, str] = {}

    while pending and codes - found.keys():
        atom_url = pending.pop(0)
        if atom_url in visited:
            continue
        if len(visited) >= MAX_ATOM_FEEDS:
            raise RuntimeError("Se alcanzo el limite de indices ATOM revisados.")

        visited.add(atom_url)
        feed = fetch_atom(atom_url)

        for link in iter_atom_links(feed, atom_url):
            if is_zip_link(link):
                code = extract_municipality_code(link["url"])
                if code in codes and code not in found:
                    found[code] = link["url"]
                    print(f"[FOUND] {code} -> {link['url']}")
                continue

            if is_atom_link(link) and link["url"] not in visited:
                pending.append(link["url"])

    return found


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
    pending_codes = {
        code
        for code in MUNICIPALITIES
        if not (RAW_DIR / f"A.ES.SDGC.BU.{code}.zip").exists()
    }

    if not pending_codes:
        print("[OK] Ya existen todos los ZIP del piloto.")
        return

    zip_links = discover_building_zip_links(pending_codes)

    for code, municipality in MUNICIPALITIES.items():
        out_path = RAW_DIR / f"A.ES.SDGC.BU.{code}.zip"

        if out_path.exists():
            print(f"[SKIP] Ya existe: {out_path}")
            continue

        url = zip_links.get(code)
        if not url:
            print(f"[WARN] No se encontro ZIP de edificios para {code} - {municipality}")
            continue

        print(f"[DOWNLOAD] Descargando Catastro BU {code} - {municipality} ...")
        download_file(url, out_path)
        print(f"[OK] Guardado en: {out_path}")

    print("\nProceso terminado.")


if __name__ == "__main__":
    main()
