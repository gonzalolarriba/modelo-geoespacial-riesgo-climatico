from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "DATA" / "PROCESSED"


class EngineeringOutputsTest(unittest.TestCase):
    def test_daily_dataset_contract(self) -> None:
        path = PROC / "dataset_cv_municipios.csv"
        self.assertTrue(path.exists(), f"No existe {path}")

        df = pd.read_csv(path, usecols=["municipio", "fecha"])
        self.assertEqual(len(df), 1_188_064)
        self.assertEqual(df["municipio"].nunique(), 542)
        self.assertEqual(df["fecha"].min(), "2019-01-01")
        self.assertEqual(df["fecha"].max(), "2024-12-31")
        self.assertEqual(df.duplicated(["municipio", "fecha"]).sum(), 0)

    def test_enriched_dataset_contract(self) -> None:
        path = PROC / "dataset_cv_municipios_enriched.csv"
        self.assertTrue(path.exists(), f"No existe {path}")

        df = pd.read_csv(
            path,
            usecols=[
                "municipio",
                "fecha",
                "cod_ine",
                "poblacion_total",
                "densidad_poblacion",
            ],
        )
        self.assertEqual(len(df), 1_188_064)
        self.assertEqual(df["municipio"].nunique(), 542)
        self.assertEqual(df["cod_ine"].nunique(), 542)
        self.assertEqual(df.duplicated(["municipio", "fecha"]).sum(), 0)
        self.assertEqual(int(df["poblacion_total"].isna().sum()), 0)
        self.assertEqual(int(df["densidad_poblacion"].isna().sum()), 0)

    def test_aemet_station_is_joined_to_real_municipality(self) -> None:
        path = PROC / "aemet_vs_era5_daily_comparison.csv"
        self.assertTrue(path.exists(), f"No existe {path}")

        df = pd.read_csv(path, dtype={"indicativo": "string"})
        stations = df[["indicativo", "nombre", "municipio"]].drop_duplicates()
        station_8501 = stations.loc[stations["indicativo"] == "8501"]

        self.assertEqual(len(station_8501), 1)
        self.assertEqual(
            station_8501["municipio"].iloc[0],
            "Castell\u00f3 de la Plana/Castell\u00f3n de la Plana",
        )
        self.assertNotIn("Onda", set(stations["municipio"]))

    def test_sqlite_row_counts(self) -> None:
        path = PROC / "tfg_ingenieria_dato.sqlite"
        self.assertTrue(path.exists(), f"No existe {path}")

        with sqlite3.connect(path) as conn:
            counts = {
                table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in [
                    "municipios_diario_enriched",
                    "ine_contexto_municipal",
                    "aemet_daily_comparison",
                    "aemet_metrics",
                ]
            }

        self.assertEqual(counts["municipios_diario_enriched"], 1_188_064)
        self.assertEqual(counts["ine_contexto_municipal"], 542)
        self.assertEqual(counts["aemet_daily_comparison"], 123)
        self.assertEqual(counts["aemet_metrics"], 1)


if __name__ == "__main__":
    unittest.main()
