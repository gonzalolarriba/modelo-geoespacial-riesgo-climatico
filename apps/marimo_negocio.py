r"""Dashboard opcional para explorar la segmentacion municipal del TFG.

Uso:
    .\venv\Scripts\python.exe -m marimo run apps\marimo_negocio.py

Esta app no recalcula el pipeline de datos. Lee el dataset final generado por los
notebooks y sirve como capa interactiva para revisar clusters, prioridades y
municipios destacados desde una perspectiva de negocio asegurador.
"""

import marimo

__generated_with = "0.23.9"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md(r"""
    # Dashboard exploratorio de negocio asegurador

    Exploracion interactiva del dataset municipal segmentado de la Comunidad Valenciana.
    """)
    return


@app.cell
def _():
    from pathlib import Path
    import re
    import unicodedata

    import matplotlib.pyplot as plt
    import pandas as pd

    return Path, pd, plt, re, unicodedata


@app.cell
def _(Path, pd):
    root = Path(__file__).resolve().parents[1]
    business_data_path = root / "DATA" / "PROCESSED" / "dataset_cv_municipios_negocio.csv"
    segmented_data_path = root / "DATA" / "PROCESSED" / "dataset_cv_municipios_segmentado.csv"
    data_path = business_data_path if business_data_path.exists() else segmented_data_path
    rf_reading_path = root / "output" / "negocio" / "lectura_rf_negocio.csv"
    _dana_reference_path = (
        root / "DATA" / "PROCESSED" / "dana_2024_municipios_afectados_boe.csv"
    )
    df_segmentado = pd.read_csv(data_path)
    df_dana_boe = (
        pd.read_csv(_dana_reference_path)
        if _dana_reference_path.exists()
        else pd.DataFrame()
    )
    df_rf_reading = (
        pd.read_csv(rf_reading_path) if rf_reading_path.exists() else pd.DataFrame()
    )
    return data_path, df_dana_boe, df_rf_reading, df_segmentado


@app.cell
def _(df_dana_boe, df_segmentado, pd, re, unicodedata):
    cluster_labels = {
        0: "Areas urbanas o litorales con exposicion fisica e inundable elevada",
        1: "Interior rural de baja exposicion y mayor altitud",
        2: "Peligro climatico alto con exposicion moderada-baja",
        3: "Municipios calidos y secos con exposicion hidrologica moderada",
    }

    def normalizar_municipio(valor):
        texto = str(valor).lower().strip()
        texto = texto.replace("\u2019", "'").replace("`", "'").replace("´", "'")
        texto = unicodedata.normalize("NFKD", texto)
        texto = "".join(
            caracter for caracter in texto if not unicodedata.combining(caracter)
        )
        texto = texto.replace("/", " ")
        texto = re.sub(r"[^a-z0-9]+", " ", texto)
        texto = re.sub(r"\b(l|el|la|les|los|de|del|d)\b", " ", texto)
        return re.sub(r"\s+", " ", texto).strip()

    def asignar_prioridad_negocio(row, quantiles):
        riesgo = row["score_riesgo_exploratorio"]
        peligro = row["score_peligro_climatico_ampliado"]
        vulnerabilidad = row["score_vulnerabilidad"]
        exposicion = row["score_exposicion_fisica"]

        if riesgo >= quantiles["riesgo_p90"]:
            return "Muy alta"
        if (
            peligro >= quantiles["peligro_p75"]
            and (
                vulnerabilidad >= quantiles["vulnerabilidad_p75"]
                or exposicion >= quantiles["exposicion_p75"]
            )
        ):
            return "Muy alta"
        if riesgo >= quantiles["riesgo_p75"]:
            return "Alta"
        if riesgo >= quantiles["riesgo_p50"]:
            return "Media"
        return "Baja"

    order_fields = {
        "Riesgo exploratorio": "score_riesgo_exploratorio",
        "Peligro climatico ampliado": "score_peligro_climatico_ampliado",
        "Vulnerabilidad": "score_vulnerabilidad",
        "Exposicion fisica": "score_exposicion_fisica",
        "Exposicion inundable": "score_exposicion_inundacion",
        "Contexto climatico extendido": "score_contexto_climatico_extendido",
        "Error RF score": "rf_score_riesgo_error_abs",
    }
    priority_order = ["Muy alta", "Alta", "Media", "Baja"]
    map_color_modes = ["Prioridad", "Cluster", "DANA 2024"]
    priority_colors = {
        "Muy alta": "#c43c39",
        "Alta": "#f58518",
        "Media": "#4c78a8",
        "Baja": "#54a24b",
    }
    cluster_colors = {
        0: "#4c78a8",
        1: "#f58518",
        2: "#54a24b",
        3: "#b279a2",
    }

    df_negocio = df_segmentado.copy()
    df_negocio["cluster_descripcion"] = df_negocio.get(
        "perfil_negocio_kmeans",
        df_negocio["cluster_kmeans"].map(cluster_labels),
    )
    if "prioridad_negocio" not in df_negocio.columns:
        quantiles_prioridad = {
            "riesgo_p90": df_negocio["score_riesgo_exploratorio"].quantile(0.90),
            "riesgo_p75": df_negocio["score_riesgo_exploratorio"].quantile(0.75),
            "riesgo_p50": df_negocio["score_riesgo_exploratorio"].quantile(0.50),
            "peligro_p75": df_negocio["score_peligro_climatico_ampliado"].quantile(0.75),
            "vulnerabilidad_p75": df_negocio["score_vulnerabilidad"].quantile(0.75),
            "exposicion_p75": df_negocio["score_exposicion_fisica"].quantile(0.75),
        }
        df_negocio["prioridad_negocio"] = df_negocio.apply(
            asignar_prioridad_negocio,
            axis=1,
            quantiles=quantiles_prioridad,
        )
    df_negocio["municipio_singular_dbscan"] = df_negocio["cluster_dbscan"].eq(-1)
    df_negocio["prioridad_negocio"] = pd.Categorical(
        df_negocio["prioridad_negocio"],
        categories=priority_order,
        ordered=True,
    )
    if "rank_riesgo_exploratorio" not in df_negocio.columns:
        df_negocio["rank_riesgo_exploratorio"] = (
            df_negocio["score_riesgo_exploratorio"]
            .rank(method="min", ascending=False)
            .astype(int)
        )

    if "afectado_dana_2024_boe" in df_negocio.columns:
        if df_negocio["afectado_dana_2024_boe"].dtype == object:
            df_negocio["afectado_dana_2024_boe"] = (
                df_negocio["afectado_dana_2024_boe"]
                .astype(str)
                .str.lower()
                .isin(["true", "1", "si", "sí"])
            )
        dana_reference_available = True
    else:
        df_negocio["municipio_key_dana"] = df_negocio["municipio"].map(normalizar_municipio)
        dana_reference_available = not df_dana_boe.empty

    if "afectado_dana_2024_boe" not in df_negocio.columns and dana_reference_available:
        df_dana_cv = df_dana_boe[df_dana_boe["ambito_tfg_cv"].astype(bool)].copy()
        df_dana_cv["municipio_key_dana"] = df_dana_cv["municipio_boe"].map(
            normalizar_municipio
        )
        df_negocio = df_negocio.merge(
            df_dana_cv[
                [
                    "municipio_key_dana",
                    "municipio_boe",
                    "observacion_boe",
                    "periodo_evento",
                    "fuente_url",
                ]
            ],
            on="municipio_key_dana",
            how="left",
        )
        df_negocio["afectado_dana_2024_boe"] = df_negocio["municipio_boe"].notna()
    elif "afectado_dana_2024_boe" not in df_negocio.columns:
        df_negocio["municipio_boe"] = ""
        df_negocio["observacion_boe"] = ""
        df_negocio["periodo_evento"] = ""
        df_negocio["fuente_url"] = ""
        df_negocio["afectado_dana_2024_boe"] = False

    for col in ["municipio_boe", "observacion_boe", "periodo_evento", "fuente_url"]:
        if col not in df_negocio.columns:
            df_negocio[col] = ""
        df_negocio[col] = df_negocio[col].fillna("")

    order_fields = {
        label: column for label, column in order_fields.items() if column in df_negocio.columns
    }

    return (
        cluster_colors,
        cluster_labels,
        dana_reference_available,
        df_negocio,
        map_color_modes,
        order_fields,
        priority_colors,
        priority_order,
    )


@app.cell
def _(
    cluster_labels,
    dana_reference_available,
    df_negocio,
    map_color_modes,
    mo,
    order_fields,
    priority_order,
):
    cluster_options = ["Todos"] + [
        f"{cluster_id} - {cluster_labels[cluster_id]}"
        for cluster_id in sorted(cluster_labels)
    ]
    priority_options = ["Todas"] + priority_order
    order_options = list(order_fields)
    dana_options = ["Todos", "Afectados BOE", "No afectados BOE"]

    cluster_selector = mo.ui.dropdown(
        options=cluster_options,
        value="Todos",
        label="Cluster",
    )
    priority_selector = mo.ui.dropdown(
        options=priority_options,
        value="Todas",
        label="Prioridad",
    )
    order_selector = mo.ui.dropdown(
        options=order_options,
        value="Riesgo exploratorio",
        label="Ordenar por",
    )
    top_n_slider = mo.ui.slider(
        start=5,
        stop=min(50, len(df_negocio)),
        step=5,
        value=15,
        label="Municipios",
    )
    only_singular_checkbox = mo.ui.checkbox(
        value=False,
        label="Solo singulares DBSCAN",
    )
    map_color_selector = mo.ui.dropdown(
        options=map_color_modes,
        value="Prioridad",
        label="Colorear mapa por",
    )
    dana_selector = mo.ui.dropdown(
        options=dana_options,
        value="Todos",
        label="DANA 2024",
        disabled=not dana_reference_available,
    )

    mo.hstack(
        [
            mo.vstack([cluster_selector, order_selector, map_color_selector]),
            mo.vstack([top_n_slider]),
            mo.vstack([priority_selector, dana_selector, only_singular_checkbox]),
        ],
        align="start",
        widths=[0.45, 0.25, 0.30],
    )
    return (
        cluster_selector,
        dana_selector,
        map_color_selector,
        only_singular_checkbox,
        order_selector,
        priority_selector,
        top_n_slider,
    )


@app.cell
def _(
    cluster_selector,
    dana_selector,
    df_negocio,
    only_singular_checkbox,
    order_fields,
    order_selector,
    priority_selector,
    top_n_slider,
):
    df_filtrado = df_negocio.copy()

    if cluster_selector.value != "Todos":
        selected_cluster = int(cluster_selector.value.split(" - ", maxsplit=1)[0])
        df_filtrado = df_filtrado[df_filtrado["cluster_kmeans"].eq(selected_cluster)]

    if priority_selector.value != "Todas":
        df_filtrado = df_filtrado[
            df_filtrado["prioridad_negocio"].astype(str).eq(priority_selector.value)
        ]

    if dana_selector.value == "Afectados BOE":
        df_filtrado = df_filtrado[df_filtrado["afectado_dana_2024_boe"]]
    elif dana_selector.value == "No afectados BOE":
        df_filtrado = df_filtrado[~df_filtrado["afectado_dana_2024_boe"]]

    if only_singular_checkbox.value:
        df_filtrado = df_filtrado[df_filtrado["municipio_singular_dbscan"]]

    order_field = order_fields[order_selector.value]
    df_ranking = df_filtrado.sort_values(order_field, ascending=False).head(
        top_n_slider.value
    )
    return df_filtrado, df_ranking


@app.cell
def _(
    cluster_selector,
    dana_selector,
    df_filtrado,
    df_negocio,
    map_color_selector,
    mo,
    only_singular_checkbox,
    order_selector,
    priority_selector,
):
    singular_text = (
        "solo municipios singulares segun DBSCAN"
        if only_singular_checkbox.value
        else "todos los municipios del filtro"
    )
    cluster_text = (
        "todos los clusters"
        if cluster_selector.value == "Todos"
        else cluster_selector.value.split(" - ", maxsplit=1)[1]
    )
    priority_text = (
        "todas las prioridades"
        if priority_selector.value == "Todas"
        else f"prioridad {priority_selector.value.lower()}"
    )
    dana_text = {
        "Todos": "sin filtrar por DANA 2024",
        "Afectados BOE": "solo municipios afectados por DANA 2024 segun BOE",
        "No afectados BOE": "solo municipios no incluidos en el anexo BOE DANA 2024",
    }[dana_selector.value]
    selected_pct = len(df_filtrado) / len(df_negocio) * 100

    mo.md(
        f"""
        **Lectura del filtro actual:** estas viendo **{len(df_filtrado)} municipios**
        ({selected_pct:.1f}% del total), dentro de **{cluster_text}**, con
        **{priority_text}**, **{dana_text}** y considerando **{singular_text}**.
        El ranking se ordena por **{order_selector.value.lower()}** y el mapa se colorea por
        **{map_color_selector.value.lower()}**.
        """
    )
    return


@app.cell
def _(dana_reference_available, data_path, df_filtrado, df_negocio, mo):
    municipios = len(df_filtrado)
    total_municipios = len(df_negocio)
    riesgo_medio = df_filtrado["score_riesgo_exploratorio"].mean()
    peligro_medio = df_filtrado["score_peligro_climatico_ampliado"].mean()
    vulnerabilidad_media = df_filtrado["score_vulnerabilidad"].mean()
    exposicion_media = df_filtrado["score_exposicion_fisica"].mean()
    _rf_error_medio = (
        df_filtrado["rf_score_riesgo_error_abs"].mean()
        if "rf_score_riesgo_error_abs" in df_filtrado.columns
        else None
    )
    _dana_municipios = int(df_filtrado["afectado_dana_2024_boe"].sum())
    _dana_pct = _dana_municipios / municipios * 100 if municipios else 0

    if municipios == 0:
        resumen_metricas = "No hay municipios para la combinacion de filtros seleccionada."
    else:
        _dana_label = (
            f"{_dana_municipios} ({_dana_pct:.1f}%)"
            if dana_reference_available
            else "Referencia no disponible"
        )
        _metric_rows = [
            "| Metrica | Valor medio |",
            "|---|---:|",
            f"| Riesgo exploratorio | {riesgo_medio:.3f} |",
            f"| Peligro climatico ampliado | {peligro_medio:.3f} |",
            f"| Vulnerabilidad | {vulnerabilidad_media:.3f} |",
            f"| Exposicion fisica | {exposicion_media:.3f} |",
        ]
        if _rf_error_medio is not None:
            _metric_rows.append(f"| Error medio RF score | {_rf_error_medio:.3f} |")
        _metric_rows.append(f"| Afectados DANA 2024 BOE | {_dana_label} |")
        resumen_metricas = (
            f"**Dataset:** `{data_path.name}`\n\n"
            f"**Municipios seleccionados:** {municipios} de {total_municipios}\n\n"
            + "\n".join(_metric_rows)
        )
    mo.md(resumen_metricas)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Lectura explicativa RF
    """)
    return


@app.cell
def _(df_filtrado, df_rf_reading, mo, plt):
    rf_required_cols = {
        "municipio",
        "score_riesgo_exploratorio",
        "rf_score_riesgo_pred",
        "rf_score_riesgo_residuo",
        "rf_score_riesgo_error_abs",
        "rf_score_split",
    }
    if df_filtrado.empty:
        rf_panel = mo.md("No hay municipios para calcular la lectura RF con los filtros seleccionados.")
    elif not rf_required_cols.issubset(df_filtrado.columns):
        rf_panel = mo.md(
            "Lectura RF no disponible en el dataset cargado. Ejecuta antes los notebooks 4 y 5."
        )
    else:
        _rf_error_medio = df_filtrado["rf_score_riesgo_error_abs"].mean()
        _rf_error_max = df_filtrado["rf_score_riesgo_error_abs"].max()
        _test_count = int(df_filtrado["rf_score_split"].astype(str).eq("test").sum())
        _train_count = int(df_filtrado["rf_score_split"].astype(str).eq("train").sum())

        _summary_rows = []
        if not df_rf_reading.empty and {"aspecto", "valor"}.issubset(df_rf_reading.columns):
            for _, row in df_rf_reading.iterrows():
                if row["aspecto"] in {
                    "rendimiento_test",
                    "bloque_dominante",
                    "variables_mas_influyentes",
                    "estado_shap",
                }:
                    _summary_rows.append(f"| {row['aspecto']} | {row['valor']} |")
        summary_table = "\n".join(_summary_rows)
        summary_text = (
            "El Random Forest es auxiliar: reproduce el score exploratorio y ayuda a "
            "interpretar que variables lo explican mejor. No predice siniestros reales.\n\n"
            "| Metrica RF en la seleccion | Valor |\n"
            "|---|---:|\n"
            f"| Error absoluto medio | {_rf_error_medio:.3f} |\n"
            f"| Error absoluto maximo | {_rf_error_max:.3f} |\n"
            f"| Municipios train/test | {_train_count}/{_test_count} |"
            + (
                "\n\n| Sintesis global RF | Valor |\n"
                "|---|---|\n"
                f"{summary_table}"
                if summary_table
                else ""
            )
        )

        rf_top_errors = (
            df_filtrado.sort_values("rf_score_riesgo_error_abs", ascending=False)
            .head(10)
            .copy()
        )
        fig_rf_error, ax_rf_error = plt.subplots(figsize=(7.5, 3.6))
        _plot_data = rf_top_errors.sort_values("rf_score_riesgo_error_abs")
        ax_rf_error.barh(
            _plot_data["municipio"],
            _plot_data["rf_score_riesgo_error_abs"],
            color="#6f6f6f",
        )
        ax_rf_error.set_title("Municipios con mayor error RF del score")
        ax_rf_error.set_xlabel("Error absoluto")
        ax_rf_error.set_ylabel("")
        fig_rf_error.tight_layout()

        rf_table_cols = [
            "municipio",
            "score_riesgo_exploratorio",
            "rf_score_riesgo_pred",
            "rf_score_riesgo_residuo",
            "rf_score_riesgo_error_abs",
            "rf_score_split",
        ]
        rf_table_labels = {
            "municipio": "Municipio",
            "score_riesgo_exploratorio": "Score",
            "rf_score_riesgo_pred": "Prediccion RF",
            "rf_score_riesgo_residuo": "Residuo RF",
            "rf_score_riesgo_error_abs": "Error RF",
            "rf_score_split": "Particion",
        }
        rf_table = (
            rf_top_errors[rf_table_cols]
            .rename(columns=rf_table_labels)
            .reset_index(drop=True)
            .round(3)
        )

        rf_panel = mo.vstack(
            [
                mo.md(summary_text),
                fig_rf_error,
                mo.ui.table(rf_table, page_size=10),
            ]
        )

    rf_panel
    return


@app.cell
def _(mo):
    mo.md("""
    ## Contraste externo DANA 2024
    """)
    return


@app.cell
def _(
    cluster_colors,
    dana_reference_available,
    df_filtrado,
    mo,
    plt,
    priority_colors,
    priority_order,
):
    if not dana_reference_available:
        dana_panel = mo.md(
            "Referencia DANA 2024 no disponible. Ejecuta antes el script BOE del bloque de negocio."
        )
    else:
        _dana_total = int(df_filtrado["afectado_dana_2024_boe"].sum())
        _dana_pct = _dana_total / len(df_filtrado) * 100 if len(df_filtrado) else 0
        rank_mediano = (
            df_filtrado.loc[
                df_filtrado["afectado_dana_2024_boe"],
                "rank_riesgo_exploratorio",
            ].median()
            if _dana_total
            else None
        )
        rank_text = (
            "sin municipios afectados en la seleccion"
            if rank_mediano is None
            else f"{rank_mediano:.0f}"
        )

        dana_summary = mo.md(
            f"""
            Este bloque no representa siniestralidad real: contrasta el ranking exploratorio con los municipios incluidos en el anexo oficial del BOE tras la DANA 2024.

            **Municipios DANA 2024 en la seleccion:** {_dana_total} ({_dana_pct:.1f}%).

            **Mediana del ranking de riesgo entre afectados:** {rank_text}.
            """
        )

        prioridad_dana = (
            df_filtrado[df_filtrado["afectado_dana_2024_boe"]]
            ["prioridad_negocio"]
            .value_counts(sort=False)
            .reindex(priority_order, fill_value=0)
        )
        fig_dana_prioridad, ax_dana_prioridad = plt.subplots(figsize=(6.5, 3.4))
        prioridad_dana.plot(
            kind="bar",
            ax=ax_dana_prioridad,
            color=[priority_colors[priority] for priority in prioridad_dana.index],
        )
        ax_dana_prioridad.set_title("Municipios DANA por prioridad")
        ax_dana_prioridad.set_xlabel("")
        ax_dana_prioridad.set_ylabel("Municipios")
        ax_dana_prioridad.tick_params(axis="x", rotation=0)
        fig_dana_prioridad.tight_layout()

        cluster_dana = (
            df_filtrado[df_filtrado["afectado_dana_2024_boe"]]
            .groupby(["cluster_kmeans", "cluster_descripcion"], observed=True)
            .size()
            .reset_index(name="municipios")
            .sort_values("municipios")
        )
        fig_dana_cluster, ax_dana_cluster = plt.subplots(figsize=(8.2, 3.4))
        if cluster_dana.empty:
            ax_dana_cluster.text(
                0.5,
                0.5,
                "Sin municipios afectados",
                ha="center",
                va="center",
                transform=ax_dana_cluster.transAxes,
            )
            ax_dana_cluster.set_axis_off()
        else:
            ax_dana_cluster.barh(
                cluster_dana["cluster_descripcion"],
                cluster_dana["municipios"],
                color=[
                    cluster_colors[int(cluster)]
                    for cluster in cluster_dana["cluster_kmeans"]
                ],
            )
            ax_dana_cluster.set_title("Municipios DANA por cluster")
            ax_dana_cluster.set_xlabel("Municipios")
            ax_dana_cluster.set_ylabel("")
            ax_dana_cluster.tick_params(axis="y", labelsize=8)
        fig_dana_cluster.tight_layout()

        dana_panel = mo.vstack(
            [
                dana_summary,
                mo.hstack(
                    [fig_dana_prioridad, fig_dana_cluster],
                    align="center",
                    widths="equal",
                ),
            ]
        )

    dana_panel
    return


@app.cell
def _(mo):
    mo.md("""
    ## Vista territorial
    """)
    return


@app.cell
def _(
    cluster_colors,
    df_filtrado,
    df_negocio,
    map_color_selector,
    plt,
    priority_colors,
    priority_order,
):
    fig_mapa, ax_mapa = plt.subplots(figsize=(10, 7))
    resto_municipios = df_negocio.drop(index=df_filtrado.index, errors="ignore")
    if not resto_municipios.empty:
        ax_mapa.scatter(
            resto_municipios["lon"],
            resto_municipios["lat"],
            s=14,
            color="#d6dae2",
            alpha=0.55,
            linewidths=0,
            label="Resto de municipios",
        )

    if df_filtrado.empty:
        ax_mapa.text(
            0.5,
            0.5,
            "Sin municipios para los filtros seleccionados",
            ha="center",
            va="center",
            transform=ax_mapa.transAxes,
        )
    elif map_color_selector.value == "Prioridad":
        for priority in priority_order:
            subset = df_filtrado[
                df_filtrado["prioridad_negocio"].astype(str).eq(priority)
            ]
            if subset.empty:
                continue
            ax_mapa.scatter(
                subset["lon"],
                subset["lat"],
                s=46,
                color=priority_colors[priority],
                edgecolors="white",
                linewidths=0.5,
                label=priority,
            )
    elif map_color_selector.value == "DANA 2024":
        for label, value, color in [
            ("Afectados BOE", True, "#c43c39"),
            ("No afectados BOE", False, "#4c78a8"),
        ]:
            subset = df_filtrado[df_filtrado["afectado_dana_2024_boe"].eq(value)]
            if subset.empty:
                continue
            ax_mapa.scatter(
                subset["lon"],
                subset["lat"],
                s=46 if value else 34,
                color=color,
                alpha=0.95 if value else 0.60,
                edgecolors="white",
                linewidths=0.5,
                label=label,
            )
    else:
        for cluster_id, subset in df_filtrado.groupby("cluster_kmeans"):
            cluster_id = int(cluster_id)
            ax_mapa.scatter(
                subset["lon"],
                subset["lat"],
                s=46,
                color=cluster_colors[cluster_id],
                edgecolors="white",
                linewidths=0.5,
                label=f"Cluster {cluster_id}",
            )

    ax_mapa.set_title(f"Municipios filtrados por {map_color_selector.value.lower()}")
    ax_mapa.set_xlabel("Longitud")
    ax_mapa.set_ylabel("Latitud")
    ax_mapa.set_aspect("equal", adjustable="box")
    ax_mapa.grid(alpha=0.2)
    ax_mapa.legend(
        loc="upper left",
        bbox_to_anchor=(1.02, 1),
        borderaxespad=0,
        fontsize=8,
        frameon=True,
    )
    fig_mapa.tight_layout()
    fig_mapa
    return


@app.cell
def _(mo):
    mo.md("""
    ## Distribucion de la seleccion
    """)
    return


@app.cell
def _(
    cluster_colors,
    df_filtrado,
    mo,
    plt,
    priority_colors,
    priority_order,
):
    prioridad_counts = (
        df_filtrado["prioridad_negocio"].value_counts(sort=False).sort_index()
    )
    prioridad_counts = prioridad_counts.reindex(priority_order, fill_value=0)
    fig_prioridad, ax_prioridad = plt.subplots(figsize=(6.5, 3.4))
    prioridad_counts.plot(
        kind="bar",
        ax=ax_prioridad,
        color=[priority_colors[priority] for priority in prioridad_counts.index],
    )
    ax_prioridad.set_title("Distribucion por prioridad de negocio")
    ax_prioridad.set_xlabel("")
    ax_prioridad.set_ylabel("Municipios")
    ax_prioridad.tick_params(axis="x", rotation=0)
    fig_prioridad.tight_layout()
    cluster_counts = (
        df_filtrado.groupby(["cluster_kmeans", "cluster_descripcion"], observed=True)
        .size()
        .reset_index(name="municipios")
        .sort_values("municipios")
    )
    fig_cluster, ax_cluster = plt.subplots(figsize=(6.5, 3.4))
    ax_cluster.barh(
        cluster_counts["cluster_descripcion"],
        cluster_counts["municipios"],
        color=[
            cluster_colors[int(cluster)]
            for cluster in cluster_counts["cluster_kmeans"]
        ],
    )
    ax_cluster.set_title("Distribucion por cluster KMeans")
    ax_cluster.set_xlabel("Municipios")
    ax_cluster.set_ylabel("")
    fig_cluster.tight_layout()
    mo.hstack([fig_prioridad, fig_cluster], align="center", widths="equal")
    return


@app.cell
def _(mo):
    mo.md("""
    ## Ranking de municipios
    """)
    return


@app.cell
def _(df_ranking, mo):
    ranking_columns = [
        "municipio",
        "prioridad_negocio",
        "cluster_descripcion",
        "afectado_dana_2024_boe",
        "municipio_singular_dbscan",
        "rank_riesgo_exploratorio",
        "score_riesgo_exploratorio",
        "score_peligro_climatico_ampliado",
        "score_vulnerabilidad",
        "score_exposicion_inundacion",
        "score_exposicion_fisica",
        "score_contexto_climatico_extendido",
        "rf_score_riesgo_error_abs",
        "rf_score_split",
        "poblacion_total",
        "densidad_poblacion",
        "densidad_edificios_km2",
        "ratio_huella_edificada_pct",
    ]
    column_labels = {
        "municipio": "Municipio",
        "prioridad_negocio": "Prioridad",
        "cluster_descripcion": "Cluster",
        "afectado_dana_2024_boe": "DANA 2024 BOE",
        "municipio_singular_dbscan": "Singular DBSCAN",
        "rank_riesgo_exploratorio": "Rank riesgo",
        "score_riesgo_exploratorio": "Riesgo",
        "score_peligro_climatico_ampliado": "Peligro climatico",
        "score_vulnerabilidad": "Vulnerabilidad",
        "score_exposicion_inundacion": "Exposicion inundable",
        "score_exposicion_fisica": "Exposicion fisica",
        "score_contexto_climatico_extendido": "Contexto climatico",
        "rf_score_riesgo_error_abs": "Error RF",
        "rf_score_split": "Particion RF",
        "poblacion_total": "Poblacion",
        "densidad_poblacion": "Densidad poblacion",
        "densidad_edificios_km2": "Densidad edificios",
        "ratio_huella_edificada_pct": "Huella edificada (%)",
    }
    ranking_columns = [col for col in ranking_columns if col in df_ranking.columns]
    df_tabla_ranking = (
        df_ranking[ranking_columns]
        .rename(columns=column_labels)
        .reset_index(drop=True)
        .round(3)
    )
    mo.ui.table(df_tabla_ranking, page_size=15)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Resumen de clusters
    """)
    return


@app.cell
def _(df_negocio, mo):
    cluster_summary = (
        df_negocio.groupby(["cluster_kmeans", "cluster_descripcion"], observed=True)
        .agg(
            municipios=("municipio", "count"),
            riesgo_medio=("score_riesgo_exploratorio", "mean"),
            peligro_medio=("score_peligro_climatico_ampliado", "mean"),
            vulnerabilidad_media=("score_vulnerabilidad", "mean"),
            exposicion_media=("score_exposicion_fisica", "mean"),
            municipios_dana=("afectado_dana_2024_boe", "sum"),
            singulares_dbscan=("municipio_singular_dbscan", "sum"),
        )
        .reset_index()
        .sort_values("riesgo_medio", ascending=False)
    )
    cluster_summary["pct_dana"] = (
        cluster_summary["municipios_dana"] / cluster_summary["municipios"] * 100
    )
    cluster_summary = cluster_summary.rename(
        columns={
            "cluster_kmeans": "Cluster",
            "cluster_descripcion": "Descripcion",
            "municipios": "Municipios",
            "riesgo_medio": "Riesgo medio",
            "peligro_medio": "Peligro medio",
            "vulnerabilidad_media": "Vulnerabilidad media",
            "exposicion_media": "Exposicion media",
            "municipios_dana": "Municipios DANA",
            "pct_dana": "% DANA",
            "singulares_dbscan": "Singulares DBSCAN",
        }
    ).round(3)
    mo.ui.table(cluster_summary, page_size=10)
    return


if __name__ == "__main__":
    app.run()
