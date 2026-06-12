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

    def test_extended_climate_dataset_contract(self) -> None:
        path = PROC / "dataset_cv_municipios_climate_extended.csv"
        self.assertTrue(path.exists(), f"No existe {path}")

        df = pd.read_csv(
            path,
            usecols=[
                "municipio",
                "fecha",
                "dewpoint_media_dia",
                "runoff_superficial_total_dia_mm",
                "humedad_suelo_capa1_media_m3_m3",
                "radiacion_solar_total_dia_mj_m2",
            ],
        )
        self.assertEqual(len(df), 1_188_064)
        self.assertEqual(df["municipio"].nunique(), 542)
        self.assertEqual(df.duplicated(["municipio", "fecha"]).sum(), 0)
        self.assertEqual(int(df.isna().sum().sum()), 0)

    def test_catastro_outputs_contract(self) -> None:
        summary_path = PROC / "catastro_buildings_cv_summary.csv"
        enriched_path = PROC / "dataset_cv_municipios_enriched_catastro.csv"
        self.assertTrue(summary_path.exists(), f"No existe {summary_path}")
        self.assertTrue(enriched_path.exists(), f"No existe {enriched_path}")

        summary = pd.read_csv(
            summary_path,
            usecols=[
                "cod_ine",
                "num_edificios_catastro",
                "num_viviendas_catastro",
                "huella_edificada_m2",
                "densidad_viviendas_catastro_km2",
                "ratio_huella_edificada_pct",
            ],
        )
        self.assertEqual(len(summary), 542)
        self.assertEqual(summary["cod_ine"].nunique(), 542)
        self.assertEqual(summary.duplicated(["cod_ine"]).sum(), 0)
        self.assertEqual(int(summary.isna().sum().sum()), 0)

        enriched = pd.read_csv(
            enriched_path,
            usecols=[
                "municipio",
                "fecha",
                "cod_ine",
                "num_edificios_catastro",
                "densidad_viviendas_catastro_km2",
                "ratio_huella_edificada_pct",
            ],
        )
        self.assertEqual(len(enriched), 1_188_064)
        self.assertEqual(enriched["municipio"].nunique(), 542)
        self.assertEqual(enriched["cod_ine"].nunique(), 542)
        self.assertEqual(enriched.duplicated(["municipio", "fecha"]).sum(), 0)
        self.assertEqual(int(enriched.isna().sum().sum()), 0)

    def test_snczi_outputs_contract(self) -> None:
        summary_path = PROC / "snczi_flood_exposure_municipal.csv"
        enriched_path = PROC / "dataset_cv_municipios_enriched_catastro_snczi.csv"
        self.assertTrue(summary_path.exists(), f"No existe {summary_path}")
        self.assertTrue(enriched_path.exists(), f"No existe {enriched_path}")

        pct_cols = [
            "snczi_inundacion_t100_pct_area_aprox",
            "snczi_inundacion_t500_pct_area_aprox",
        ]
        bool_cols = [
            "snczi_inundacion_t100_tiene_zona_inundable",
            "snczi_inundacion_t500_tiene_zona_inundable",
        ]

        summary = pd.read_csv(
            summary_path,
            usecols=[
                "municipio",
                "CODNUT2",
                "CODNUT3",
                "snczi_resolucion_px",
                *pct_cols,
                *bool_cols,
            ],
        )
        self.assertEqual(len(summary), 542)
        self.assertEqual(summary["municipio"].nunique(), 542)
        self.assertEqual(summary.duplicated(["municipio", "CODNUT2", "CODNUT3"]).sum(), 0)
        self.assertEqual(int(summary.isna().sum().sum()), 0)
        self.assertEqual(int(summary["snczi_resolucion_px"].min()), 4096)
        self.assertEqual(int(summary["snczi_resolucion_px"].max()), 4096)
        self.assertTrue(((summary[pct_cols] >= 0) & (summary[pct_cols] <= 1)).all().all())
        self.assertGreaterEqual(
            summary["snczi_inundacion_t500_pct_area_aprox"].mean(),
            summary["snczi_inundacion_t100_pct_area_aprox"].mean(),
        )
        self.assertGreater(int(summary["snczi_inundacion_t100_tiene_zona_inundable"].sum()), 0)
        self.assertGreater(int(summary["snczi_inundacion_t500_tiene_zona_inundable"].sum()), 0)

        enriched = pd.read_csv(
            enriched_path,
            usecols=[
                "municipio",
                "fecha",
                "CODNUT2",
                "CODNUT3",
                *pct_cols,
                *bool_cols,
            ],
        )
        self.assertEqual(len(enriched), 1_188_064)
        self.assertEqual(enriched["municipio"].nunique(), 542)
        self.assertEqual(enriched.duplicated(["municipio", "fecha"]).sum(), 0)
        self.assertEqual(int(enriched.isna().sum().sum()), 0)
        self.assertTrue(((enriched[pct_cols] >= 0) & (enriched[pct_cols] <= 1)).all().all())

    def test_analysis_and_modeling_outputs_contract(self) -> None:
        analysis_path = PROC / "dataset_cv_municipios_analisis_municipal.csv"
        segmented_path = PROC / "dataset_cv_municipios_segmentado.csv"
        self.assertTrue(analysis_path.exists(), f"No existe {analysis_path}")
        self.assertTrue(segmented_path.exists(), f"No existe {segmented_path}")

        analysis = pd.read_csv(
            analysis_path,
            usecols=[
                "municipio",
                "CODNUT2",
                "CODNUT3",
                "score_peligro_climatico_ampliado",
                "score_exposicion_fisica",
                "score_exposicion_construida",
                "score_exposicion_inundacion",
                "score_riesgo_exploratorio",
                "snczi_inundacion_t100_pct_area_aprox",
                "snczi_inundacion_t500_pct_area_aprox",
                "contrib_peligro_climatico",
                "contrib_vulnerabilidad",
                "contrib_exposicion_fisica",
                "dimension_dominante_score",
            ],
        )
        self.assertEqual(len(analysis), 542)
        self.assertEqual(analysis["municipio"].nunique(), 542)
        self.assertEqual(analysis.duplicated(["municipio", "CODNUT2", "CODNUT3"]).sum(), 0)
        self.assertEqual(int(analysis.isna().sum().sum()), 0)
        contribution_cols = [
            "contrib_peligro_climatico",
            "contrib_vulnerabilidad",
            "contrib_exposicion_fisica",
        ]
        max_score_delta = (
            analysis[contribution_cols].sum(axis=1)
            - analysis["score_riesgo_exploratorio"]
        ).abs().max()
        self.assertLess(max_score_delta, 1e-10)
        self.assertTrue(
            set(analysis["dimension_dominante_score"]).issubset(
                {"peligro climatico", "vulnerabilidad", "exposicion fisica"}
            )
        )
        score_range_cols = [
            "score_exposicion_construida",
            "score_exposicion_inundacion",
            "score_exposicion_fisica",
            "snczi_inundacion_t100_pct_area_aprox",
            "snczi_inundacion_t500_pct_area_aprox",
        ]
        self.assertTrue(((analysis[score_range_cols] >= 0) & (analysis[score_range_cols] <= 1)).all().all())

        segmented = pd.read_csv(
            segmented_path,
            usecols=[
                "municipio",
                "CODNUT2",
                "CODNUT3",
                "cluster_kmeans",
                "cluster_agg",
                "cluster_dbscan",
                "score_riesgo_exploratorio",
                "score_exposicion_construida",
                "score_exposicion_inundacion",
                "contrib_peligro_climatico",
                "contrib_vulnerabilidad",
                "contrib_exposicion_fisica",
                "dimension_dominante_score",
            ],
        )
        self.assertEqual(len(segmented), 542)
        self.assertEqual(segmented["municipio"].nunique(), 542)
        self.assertEqual(segmented.duplicated(["municipio", "CODNUT2", "CODNUT3"]).sum(), 0)
        self.assertEqual(int(segmented.isna().sum().sum()), 0)
        self.assertEqual(segmented["cluster_kmeans"].nunique(), 4)
        self.assertEqual(segmented["cluster_agg"].nunique(), 4)
        self.assertGreaterEqual(len(set(segmented["cluster_dbscan"]) - {-1}), 2)
        self.assertGreater(int((segmented["cluster_dbscan"] == -1).sum()), 0)
        segmented_score_delta = (
            segmented[contribution_cols].sum(axis=1)
            - segmented["score_riesgo_exploratorio"]
        ).abs().max()
        self.assertLess(segmented_score_delta, 1e-10)

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
