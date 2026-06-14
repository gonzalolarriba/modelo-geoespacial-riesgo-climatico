"""Construye la referencia oficial de municipios afectados por la DANA 2024.

Uso en el pipeline:
    Script operativo de Analisis de Negocio. Genera una tabla pequena y
    reproducible a partir del anexo del BOE usado como contraste externo.

Entradas:
    Lista transcrita del Real Decreto-ley 6/2024, BOE-A-2024-22928.

Salida:
    DATA/PROCESSED/dana_2024_municipios_afectados_boe.csv

Notas:
    La tabla identifica municipios damnificados, pero no contiene polizas,
    importes asegurados ni microdatos de siniestros.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "DATA" / "PROCESSED"

OUT_PATH = PROC / "dana_2024_municipios_afectados_boe.csv"
SOURCE_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-2024-22928"
SOURCE_NAME = "BOE-A-2024-22928, Real Decreto-ley 6/2024"
EVENT_PERIOD = "2024-10-28/2024-11-04"


AFFECTED_MUNICIPALITIES = [
    ("Alaquàs", "Valencia", "Comunitat Valenciana", ""),
    ("Albal", "Valencia", "Comunitat Valenciana", ""),
    ("Albalat de la Ribera", "Valencia", "Comunitat Valenciana", ""),
    ("Alborache", "Valencia", "Comunitat Valenciana", ""),
    ("Alcàsser", "Valencia", "Comunitat Valenciana", ""),
    ("Alcúdia, l'", "Valencia", "Comunitat Valenciana", ""),
    ("Aldaia", "Valencia", "Comunitat Valenciana", ""),
    ("Alfafar", "Valencia", "Comunitat Valenciana", ""),
    ("Alfarb", "Valencia", "Comunitat Valenciana", ""),
    ("Algemesí", "Valencia", "Comunitat Valenciana", ""),
    ("Alginet", "Valencia", "Comunitat Valenciana", ""),
    ("Alhaurín de la Torre", "Málaga", "Andalucía", ""),
    ("Almussafes", "Valencia", "Comunitat Valenciana", ""),
    ("Alzira", "Valencia", "Comunitat Valenciana", ""),
    ("Benetússer", "Valencia", "Comunitat Valenciana", ""),
    ("Benifaió", "Valencia", "Comunitat Valenciana", ""),
    ("Beniparrell", "Valencia", "Comunitat Valenciana", ""),
    ("Bétera", "Valencia", "Comunitat Valenciana", ""),
    ("Bugarra", "Valencia", "Comunitat Valenciana", ""),
    ("Buñol", "Valencia", "Comunitat Valenciana", ""),
    ("Calles", "Valencia", "Comunitat Valenciana", ""),
    ("Camporrobles", "Valencia", "Comunitat Valenciana", ""),
    ("Carlet", "Valencia", "Comunitat Valenciana", ""),
    ("Catadau", "Valencia", "Comunitat Valenciana", ""),
    ("Catarroja", "Valencia", "Comunitat Valenciana", ""),
    ("Caudete de las Fuentes", "Valencia", "Comunitat Valenciana", ""),
    ("Corbera", "Valencia", "Comunitat Valenciana", ""),
    ("Quart de Poblet", "Valencia", "Comunitat Valenciana", ""),
    ("Cullera", "Valencia", "Comunitat Valenciana", ""),
    ("Chera", "Valencia", "Comunitat Valenciana", ""),
    ("Cheste", "Valencia", "Comunitat Valenciana", ""),
    ("Xirivella", "Valencia", "Comunitat Valenciana", ""),
    ("Chiva", "Valencia", "Comunitat Valenciana", ""),
    ("Dos Aguas", "Valencia", "Comunitat Valenciana", ""),
    ("Favara", "Valencia", "Comunitat Valenciana", ""),
    ("Fortaleny", "Valencia", "Comunitat Valenciana", ""),
    ("Fuenterrobles", "Valencia", "Comunitat Valenciana", ""),
    ("Gestalgar", "Valencia", "Comunitat Valenciana", ""),
    ("Godelleta", "Valencia", "Comunitat Valenciana", ""),
    ("Guadassuar", "Valencia", "Comunitat Valenciana", ""),
    ("Letur", "Albacete", "Castilla-La Mancha", ""),
    ("Llíria", "Valencia", "Comunitat Valenciana", ""),
    ("Loriguilla", "Valencia", "Comunitat Valenciana", "Solo nucleo urbano junto a la A-3"),
    ("Llocnou de la Corona", "Valencia", "Comunitat Valenciana", ""),
    ("Llaurí", "Valencia", "Comunitat Valenciana", ""),
    ("Llombai", "Valencia", "Comunitat Valenciana", ""),
    ("Macastre", "Valencia", "Comunitat Valenciana", ""),
    ("Manises", "Valencia", "Comunitat Valenciana", ""),
    ("Massanassa", "Valencia", "Comunitat Valenciana", ""),
    ("Mira", "Cuenca", "Castilla-La Mancha", ""),
    ("Mislata", "Valencia", "Comunitat Valenciana", ""),
    ("Montserrat", "Valencia", "Comunitat Valenciana", ""),
    ("Montroi/Montroy", "Valencia", "Comunitat Valenciana", ""),
    ("Paiporta", "Valencia", "Comunitat Valenciana", ""),
    ("Paterna", "Valencia", "Comunitat Valenciana", ""),
    ("Pedralba", "Valencia", "Comunitat Valenciana", ""),
    ("Picanya", "Valencia", "Comunitat Valenciana", ""),
    ("Picassent", "Valencia", "Comunitat Valenciana", ""),
    ("Polinyà de Xúquer", "Valencia", "Comunitat Valenciana", ""),
    ("Real", "Valencia", "Comunitat Valenciana", ""),
    ("Requena", "Valencia", "Comunitat Valenciana", ""),
    ("Riba-roja de Túria", "Valencia", "Comunitat Valenciana", ""),
    ("Riola", "Valencia", "Comunitat Valenciana", ""),
    ("Sedaví", "Valencia", "Comunitat Valenciana", ""),
    ("Siete Aguas", "Valencia", "Comunitat Valenciana", ""),
    ("Silla", "Valencia", "Comunitat Valenciana", ""),
    ("Sinarcas", "Valencia", "Comunitat Valenciana", ""),
    ("Sollana", "Valencia", "Comunitat Valenciana", ""),
    ("Sot de Chera", "Valencia", "Comunitat Valenciana", ""),
    ("Sueca", "Valencia", "Comunitat Valenciana", ""),
    ("Tavernes de la Valldigna", "Valencia", "Comunitat Valenciana", ""),
    ("Torrent", "Valencia", "Comunitat Valenciana", ""),
    ("Turís", "Valencia", "Comunitat Valenciana", ""),
    ("Utiel", "Valencia", "Comunitat Valenciana", ""),
    ("València", "Valencia", "Comunitat Valenciana", "Pedanias sur"),
    ("Vilamarxant", "Valencia", "Comunitat Valenciana", ""),
    ("Yátova", "Valencia", "Comunitat Valenciana", ""),
    ("Benicull de Xúquer", "Valencia", "Comunitat Valenciana", ""),
]


def main() -> None:
    rows = [
        {
            "orden_boe": pos,
            "municipio_boe": municipio,
            "provincia": provincia,
            "comunidad_autonoma": comunidad,
            "observacion_boe": observacion,
            "afectado_dana_2024_boe": True,
            "periodo_evento": EVENT_PERIOD,
            "fuente": SOURCE_NAME,
            "fuente_url": SOURCE_URL,
            "ambito_tfg_cv": comunidad == "Comunitat Valenciana",
        }
        for pos, (municipio, provincia, comunidad, observacion) in enumerate(
            AFFECTED_MUNICIPALITIES,
            start=1,
        )
    ]

    df = pd.DataFrame(rows)
    PROC.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)

    print(f"[OK] Municipios BOE DANA 2024: {len(df)}")
    print(f"[OK] Dentro del ambito CV del TFG: {int(df['ambito_tfg_cv'].sum())}")
    print(f"[OK] Guardado en: {OUT_PATH}")


if __name__ == "__main__":
    main()
