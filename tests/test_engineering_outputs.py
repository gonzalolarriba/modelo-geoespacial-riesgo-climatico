from __future__ import annotations

import json
import py_compile
import sqlite3
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "DATA" / "PROCESSED"
ENGINEERING_OUT = ROOT / "output" / "ingenieria_dato"
MODEL_OUT = ROOT / "output" / "modelado"
BUSINESS_OUT = ROOT / "output" / "negocio"
MARIMO_APP = ROOT / "apps" / "marimo_negocio.py"
PIPELINE_MANIFEST = ROOT / "config" / "pipeline_manifest.json"


class EngineeringOutputsTest(unittest.TestCase):
    def test_pipeline_manifest_contract(self) -> None:
        self.assertTrue(PIPELINE_MANIFEST.exists(), f"No existe {PIPELINE_MANIFEST}")

        manifest = json.loads(PIPELINE_MANIFEST.read_text(encoding="utf-8"))
        steps = manifest["pipeline_steps"]
        scripts = manifest["scripts"]

        orders = [step["order"] for step in steps]
        self.assertEqual(orders, sorted(orders))
        self.assertEqual(orders, list(range(1, len(steps) + 1)))

        allowed_source_types = {"notebook", "script", "app"}
        declared_outputs = set()
        for step in steps:
            self.assertIn(step["source_type"], allowed_source_types)
            self.assertTrue((ROOT / step["source"]).exists(), f"No existe {step['source']}")
            self.assertTrue(step["validation_tests"], f"Paso sin test declarado: {step['source']}")

            if step["source_type"] != "app":
                self.assertTrue(step["primary_outputs"], f"Paso sin salida declarada: {step['source']}")
            for output_path in step["primary_outputs"]:
                declared_outputs.add(output_path)
                self.assertTrue((ROOT / output_path).exists(), f"No existe {output_path}")

        expected_key_outputs = {
            "DATA/PROCESSED/dataset_cv_municipios.csv",
            "DATA/PROCESSED/dataset_cv_municipios_enriched.csv",
            "DATA/PROCESSED/dataset_cv_municipios_analisis_municipal.csv",
            "DATA/PROCESSED/dataset_cv_municipios_segmentado.csv",
            "DATA/PROCESSED/dataset_cv_municipios_negocio.csv",
        }
        self.assertTrue(expected_key_outputs.issubset(declared_outputs))

        allowed_script_roles = {"operational", "auxiliary"}
        declared_scripts = {entry["path"] for entry in scripts}
        actual_scripts = {
            str(path.relative_to(ROOT)).replace("\\", "/")
            for path in (ROOT / "scripts").rglob("*.py")
            if path.name != "__init__.py"
        }
        self.assertEqual(declared_scripts, actual_scripts)

        for entry in scripts:
            self.assertIn(entry["role"], allowed_script_roles)
            script_path = ROOT / entry["path"]
            self.assertTrue(script_path.exists(), f"No existe {entry['path']}")
            py_compile.compile(str(script_path), doraise=True)

    def test_engineering_artifact_manifest_contract(self) -> None:
        manifest_path = ENGINEERING_OUT / "manifest_artefactos_ingenieria_dato.csv"
        traceability_path = ENGINEERING_OUT / "trazabilidad_transformaciones_ingenieria_dato.csv"
        self.assertTrue(manifest_path.exists(), f"No existe {manifest_path}")
        self.assertTrue(traceability_path.exists(), f"No existe {traceability_path}")

        manifest = pd.read_csv(manifest_path)
        self.assertEqual(
            set(manifest.columns),
            {
                "artefacto",
                "ruta",
                "fase",
                "granularidad",
                "contenido",
                "control_calidad",
                "uso_posterior",
                "existe",
                "tamano_mb",
            },
        )
        self.assertGreaterEqual(len(manifest), 10)
        expected_artifacts = {
            "dataset_cv_municipios.csv",
            "dataset_cv_municipios_enriched.csv",
            "dataset_cv_municipios_climate_extended.csv",
            "ine_contexto_municipal.csv",
            "aemet_vs_era5_daily_comparison.csv",
            "catastro_buildings_cv_summary.csv",
            "snczi_flood_exposure_municipal.csv",
            "dataset_cv_municipios_enriched_catastro_snczi.csv",
        }
        self.assertTrue(expected_artifacts.issubset(set(manifest["artefacto"])))
        self.assertTrue(manifest["existe"].astype(bool).all())
        for artifact_path in manifest["ruta"]:
            self.assertTrue((ROOT / artifact_path).exists(), f"No existe {artifact_path}")

        traceability = pd.read_csv(traceability_path)
        self.assertEqual(
            set(traceability.columns),
            {
                "bloque",
                "entrada",
                "transformacion",
                "salida",
                "antes",
                "despues",
                "decision_metodologica",
                "control_calidad",
            },
        )
        self.assertGreaterEqual(len(traceability), 7)
        required_blocks = {"ERA5-Land base", "INE municipal", "AEMET validacion", "Catastro", "SNCZI"}
        self.assertTrue(required_blocks.issubset(set(traceability["bloque"])))

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
        analysis_output_dir = ROOT / "output" / "analisis"
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

        expected_analysis_artifacts = [
            "trazabilidad_analisis_dato.csv",
            "auditoria_granularidad.csv",
            "catalogo_variables_analisis.csv",
            "diseno_scores.csv",
            "auditoria_variables_score.csv",
            "descomposicion_score_dimension_dominante.csv",
            "descomposicion_score_top_municipios.csv",
            "sensibilidad_score_spearman.csv",
            "sensibilidad_score_solape_top25.csv",
            "sensibilidad_score_top10.csv",
            "resumen_scores_analisis.csv",
            "manifest_artefactos_analisis.csv",
            "puente_analisis_modelado.csv",
        ]
        for artifact_name in expected_analysis_artifacts:
            artifact_path = analysis_output_dir / artifact_name
            self.assertTrue(artifact_path.exists(), f"No existe {artifact_path}")

        manifest = pd.read_csv(analysis_output_dir / "manifest_artefactos_analisis.csv")
        self.assertGreaterEqual(len(manifest), 8)
        self.assertEqual(
            set(manifest.columns),
            {"artefacto", "ruta", "contenido", "uso_posterior", "existe"},
        )
        self.assertIn("dataset_cv_municipios_analisis_municipal.csv", set(manifest["artefacto"]))
        self.assertIn("auditoria_variables_score.csv", set(manifest["artefacto"]))
        self.assertTrue(manifest["existe"].astype(bool).all())

        score_audit = pd.read_csv(analysis_output_dir / "auditoria_variables_score.csv")
        self.assertEqual(
            set(score_audit.columns),
            {
                "dimension",
                "variable_origen",
                "score_generado",
                "orientacion",
                "interpretacion_alta",
                "municipios",
                "nulos_originales",
                "pct_nulos_originales",
                "min_original",
                "mediana_original",
                "max_original",
                "normalizacion",
                "tratamiento_nulos",
            },
        )
        self.assertGreaterEqual(len(score_audit), 12)
        self.assertTrue(
            {
                "renta_media_hogar",
                "densidad_viviendas_catastro_km2",
                "snczi_inundacion_t100_pct_area_aprox",
            }.issubset(set(score_audit["variable_origen"]))
        )
        self.assertEqual(set(score_audit["normalizacion"]), {"min-max 0-1"})
        renta_row = score_audit.loc[score_audit["variable_origen"] == "renta_media_hogar"].iloc[0]
        self.assertEqual(renta_row["orientacion"], "inversa")
        self.assertGreaterEqual(int(renta_row["nulos_originales"]), 1)
        self.assertIn("mediana", renta_row["tratamiento_nulos"])

        handoff = pd.read_csv(analysis_output_dir / "puente_analisis_modelado.csv")
        self.assertEqual(len(handoff), 4)
        self.assertEqual(
            set(handoff.columns),
            {"bloque", "variables_clave", "uso_en_modelado", "precaucion"},
        )

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
                "rf_score_riesgo_pred",
                "rf_score_riesgo_residuo",
                "rf_score_riesgo_error_abs",
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
        self.assertTrue(segmented["rf_score_riesgo_pred"].between(0, 1).all())
        self.assertGreaterEqual(segmented["rf_score_riesgo_error_abs"].min(), 0)
        self.assertLess(segmented["rf_score_riesgo_error_abs"].mean(), 0.05)

        model_feature_catalog_path = MODEL_OUT / "model_feature_catalog.csv"
        model_feature_exclusions_path = MODEL_OUT / "model_feature_exclusions.csv"
        preprocessing_audit_path = MODEL_OUT / "model_preprocessing_audit.csv"
        rf_metrics_path = MODEL_OUT / "rf_score_metrics.csv"
        model_manifest_path = MODEL_OUT / "manifest_artefactos_modelado.csv"
        for path in [
            model_feature_catalog_path,
            model_feature_exclusions_path,
            preprocessing_audit_path,
            rf_metrics_path,
            model_manifest_path,
        ]:
            self.assertTrue(path.exists(), f"No existe {path}")

        model_feature_catalog = pd.read_csv(model_feature_catalog_path)
        self.assertEqual(
            set(model_feature_catalog.columns),
            {"bloque", "variable", "dimension", "origen", "motivo_inclusion", "limitacion"},
        )
        self.assertGreaterEqual(len(model_feature_catalog), 18)
        self.assertEqual(model_feature_catalog["variable"].nunique(), len(model_feature_catalog))
        self.assertNotIn("score_riesgo_exploratorio", set(model_feature_catalog["variable"]))
        self.assertTrue(
            {
                "precip_p99",
                "renta_media_hogar",
                "densidad_viviendas_catastro_km2",
                "snczi_inundacion_t500_pct_area_aprox",
            }.issubset(set(model_feature_catalog["variable"]))
        )

        model_feature_exclusions = pd.read_csv(model_feature_exclusions_path)
        self.assertGreaterEqual(len(model_feature_exclusions), 5)
        self.assertIn("Scores compuestos", set(model_feature_exclusions["tipo_variable"]))

        preprocessing_audit = pd.read_csv(preprocessing_audit_path)
        self.assertEqual(
            set(preprocessing_audit.columns),
            {
                "variable",
                "bloque",
                "nulos_originales",
                "pct_nulos_originales",
                "imputacion",
                "valor_imputacion",
                "transformacion",
                "media_tras_preprocesado",
                "std_tras_preprocesado",
            },
        )
        self.assertEqual(set(preprocessing_audit["variable"]), set(model_feature_catalog["variable"]))
        renta_preprocessing = preprocessing_audit.loc[
            preprocessing_audit["variable"] == "renta_media_hogar"
        ].iloc[0]
        self.assertGreaterEqual(int(renta_preprocessing["nulos_originales"]), 1)
        self.assertEqual(renta_preprocessing["imputacion"], "mediana municipal")
        self.assertIn(
            "log1p tras imputacion",
            set(preprocessing_audit.loc[
                preprocessing_audit["variable"] == "densidad_poblacion",
                "transformacion",
            ]),
        )

        rf_importance_path = MODEL_OUT / "rf_score_feature_importance.csv"
        self.assertTrue(rf_importance_path.exists(), f"No existe {rf_importance_path}")
        rf_importance = pd.read_csv(
            rf_importance_path,
            usecols=[
                "variable",
                "bloque",
                "importancia_rf",
                "importancia_permutacion_media",
            ],
        )
        self.assertGreaterEqual(len(rf_importance), 10)
        self.assertEqual(rf_importance["variable"].nunique(), len(rf_importance))
        self.assertGreater(rf_importance["importancia_rf"].sum(), 0)
        self.assertGreater(rf_importance["importancia_permutacion_media"].max(), 0)

        rf_metrics = pd.read_csv(rf_metrics_path)
        self.assertEqual(set(rf_metrics.columns), {"metrica", "valor"})
        self.assertTrue({"R2 test", "MAE test", "MAE total"}.issubset(set(rf_metrics["metrica"])))
        self.assertLess(
            float(rf_metrics.loc[rf_metrics["metrica"] == "MAE test", "valor"].iloc[0]),
            0.05,
        )

        model_comparison_path = MODEL_OUT / "model_comparison.csv"
        self.assertTrue(model_comparison_path.exists(), f"No existe {model_comparison_path}")
        model_comparison = pd.read_csv(
            model_comparison_path,
            usecols=[
                "modelo",
                "silhouette",
                "davies_bouldin",
                "calinski_harabasz",
                "clusters",
                "ruido_pct",
            ],
        )
        self.assertEqual(
            set(model_comparison["modelo"]),
            {"KMeans", "Agglomerative", "DBSCAN (core)"},
        )
        self.assertEqual(
            int(model_comparison.loc[model_comparison["modelo"] == "KMeans", "clusters"].iloc[0]),
            4,
        )
        self.assertGreaterEqual(
            float(model_comparison.loc[model_comparison["modelo"] == "DBSCAN (core)", "ruido_pct"].iloc[0]),
            0,
        )

        model_manifest = pd.read_csv(model_manifest_path)
        self.assertGreaterEqual(len(model_manifest), 8)
        self.assertIn("dataset_cv_municipios_segmentado.csv", set(model_manifest["artefacto"]))
        self.assertIn("rf_score_feature_importance.csv", set(model_manifest["artefacto"]))
        self.assertTrue(model_manifest["existe"].astype(bool).all())

    def test_dana_2024_reference_and_business_outputs_contract(self) -> None:
        reference_path = PROC / "dana_2024_municipios_afectados_boe.csv"
        business_dataset_path = PROC / "dataset_cv_municipios_negocio.csv"
        business_artifact_path = BUSINESS_OUT / "dataset_municipal_negocio.csv"
        business_manifest_path = BUSINESS_OUT / "manifest_artefactos_negocio.csv"
        business_quality_path = BUSINESS_OUT / "auditoria_calidad_negocio.csv"
        recommendations_path = BUSINESS_OUT / "recomendaciones_ejecutivas_negocio.csv"
        action_matrix_path = BUSINESS_OUT / "matriz_accion_prioridad.csv"
        insurance_matrix_path = BUSINESS_OUT / "matriz_usos_aseguradores.csv"
        validation_path = BUSINESS_OUT / "dana_2024_validacion_municipal.csv"
        priority_path = BUSINESS_OUT / "dana_2024_resumen_prioridad.csv"
        cluster_path = BUSINESS_OUT / "dana_2024_resumen_cluster.csv"
        metrics_path = BUSINESS_OUT / "dana_2024_metricas_contraste.csv"

        for path in [
            reference_path,
            business_dataset_path,
            business_artifact_path,
            business_manifest_path,
            business_quality_path,
            recommendations_path,
            action_matrix_path,
            insurance_matrix_path,
            validation_path,
            priority_path,
            cluster_path,
            metrics_path,
        ]:
            self.assertTrue(path.exists(), f"No existe {path}")

        reference = pd.read_csv(reference_path)
        self.assertEqual(len(reference), 78)
        self.assertEqual(reference["municipio_boe"].nunique(), 78)
        self.assertEqual(int(reference["ambito_tfg_cv"].sum()), 75)
        self.assertTrue(reference["afectado_dana_2024_boe"].all())

        validation = pd.read_csv(
            validation_path,
            usecols=[
                "municipio",
                "afectado_dana_2024_boe",
                "prioridad_negocio",
                "cluster_kmeans",
                "rank_riesgo_exploratorio",
                "score_riesgo_exploratorio",
            ],
        )
        self.assertEqual(len(validation), 542)
        self.assertEqual(validation["municipio"].nunique(), 542)
        self.assertEqual(int(validation["afectado_dana_2024_boe"].sum()), 75)
        self.assertEqual(int(validation.isna().sum().sum()), 0)
        self.assertTrue(validation["score_riesgo_exploratorio"].between(0, 1).all())
        self.assertEqual(int(validation["rank_riesgo_exploratorio"].min()), 1)
        self.assertEqual(int(validation["rank_riesgo_exploratorio"].max()), 542)

        business = pd.read_csv(
            business_dataset_path,
            usecols=[
                "municipio",
                "provincia",
                "prioridad_negocio",
                "perfil_negocio_kmeans",
                "afectado_dana_2024_boe",
                "municipio_boe",
                "observacion_boe",
                "periodo_evento",
                "fuente",
                "fuente_url",
                "rank_riesgo_exploratorio",
                "score_riesgo_exploratorio",
                "score_contexto_climatico_extendido",
                "rf_score_riesgo_pred",
                "rf_score_riesgo_error_abs",
            ],
        )
        self.assertEqual(len(business), 542)
        self.assertEqual(business["municipio"].nunique(), 542)
        self.assertEqual(int(business.isna().sum().sum()), 0)
        self.assertEqual(set(business["provincia"]), {"Alicante", "Castellon", "Valencia"})
        self.assertEqual(int(business["afectado_dana_2024_boe"].sum()), 75)
        self.assertEqual(set(business["prioridad_negocio"]), {"Muy alta", "Alta", "Media", "Baja"})
        self.assertEqual(int(business["rank_riesgo_exploratorio"].min()), 1)
        self.assertEqual(int(business["rank_riesgo_exploratorio"].max()), 542)
        self.assertTrue(business["score_riesgo_exploratorio"].between(0, 1).all())
        self.assertTrue(business["rf_score_riesgo_pred"].between(0, 1).all())
        self.assertGreaterEqual(business["rf_score_riesgo_error_abs"].min(), 0)

        business_artifact = pd.read_csv(business_artifact_path)
        self.assertEqual(len(business_artifact), 542)

        business_manifest = pd.read_csv(business_manifest_path)
        self.assertGreaterEqual(len(business_manifest), 17)
        self.assertEqual(
            set(business_manifest.columns),
            {"artefacto", "ruta", "contenido", "uso", "existe"},
        )
        self.assertIn("dataset_cv_municipios_negocio.csv", set(business_manifest["artefacto"]))
        self.assertIn("auditoria_calidad_negocio.csv", set(business_manifest["artefacto"]))
        self.assertIn("recomendaciones_ejecutivas_negocio.csv", set(business_manifest["artefacto"]))
        self.assertTrue(business_manifest["existe"].astype(bool).all())

        quality = pd.read_csv(business_quality_path)
        self.assertEqual(set(quality.columns), {"control", "valor", "esperado", "resultado"})
        self.assertTrue(quality["resultado"].astype(bool).all())
        self.assertIn("provincia_informada", set(quality["control"]))

        recommendations = pd.read_csv(recommendations_path)
        self.assertGreaterEqual(len(recommendations), 5)
        self.assertIn("accion_recomendada", set(recommendations.columns))

        priority = pd.read_csv(priority_path)
        cluster = pd.read_csv(cluster_path)
        metrics = pd.read_csv(metrics_path)
        self.assertEqual(int(priority["municipios_dana"].sum()), 75)
        self.assertEqual(int(cluster["municipios_dana"].sum()), 75)
        self.assertGreater(int(priority["municipios_dana"].max()), 0)
        self.assertGreater(int(cluster["municipios_dana"].max()), 0)
        self.assertIn("Municipios BOE en ambito CV", set(metrics["metrica"]))

    def test_marimo_dashboard_compiles_and_uses_business_dataset(self) -> None:
        self.assertTrue(MARIMO_APP.exists(), f"No existe {MARIMO_APP}")
        py_compile.compile(str(MARIMO_APP), doraise=True)

        app_source = MARIMO_APP.read_text(encoding="utf-8")
        self.assertIn("dataset_cv_municipios_negocio.csv", app_source)
        self.assertIn("dataset_cv_municipios_segmentado.csv", app_source)

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
