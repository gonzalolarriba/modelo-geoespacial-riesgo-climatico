# Modelo geoespacial exploratorio de riesgo climatico para seguros de hogar

Autor: Gonzalo Larriba Delicado

Trabajo Fin de Grado orientado a construir una base analitica municipal para
estudiar riesgo climatico en seguros de hogar en la Comunidad Valenciana a
partir de datos abiertos.

El proyecto integra informacion climatica, territorial, socioeconomica,
catastral e hidrologica para generar indicadores municipales, segmentar
territorios y traducir los resultados a una lectura de negocio asegurador.

## Resumen del alcance

El anteproyecto original planteaba un enfoque cercano a la prediccion de
siniestralidad. Durante el desarrollo se reformula el alcance de forma
metodologicamente honesta: no existe una base publica completa y util de
siniestros de hogar a escala municipal, por lo que el trabajo no predice
siniestros reales ni calcula primas.

El resultado final es un modelo exploratorio geoespacial basado en open data.
Su objetivo es priorizar territorios, identificar patrones municipales,
explicar que variables influyen en un indice de riesgo construido y preparar
una base que podria calibrarse en el futuro con datos internos de una
aseguradora o del Consorcio de Compensacion de Seguros.

## Que hace el proyecto

- Construye una base diaria municipio-clima para 542 municipios de la Comunidad
  Valenciana.
- Integra variables climaticas de ERA5-Land y variables extendidas de contexto
  fisico.
- Enriquece la base con INE, Catastro, SNCZI, altitud y geometria municipal.
- Contrasta ERA5-Land con AEMET de forma exploratoria.
- Crea indicadores municipales de peligro climatico, vulnerabilidad y
  exposicion.
- Segmenta municipios con KMeans, Agglomerative Clustering y DBSCAN.
- Explica el score exploratorio mediante Random Forest, permutation importance
  y SHAP.
- Incorpora la DANA 2024 como contraste externo post-evento.
- Genera salidas de negocio, dashboard Marimo y tablas preparadas para Power BI
  o Excel.

## Que no hace el proyecto

- No predice siniestros reales de hogar.
- No calcula primas ni tarifas actuariales.
- No sustituye un modelo interno de una aseguradora.
- No interpreta DANA 2024 como validacion actuarial.
- No afirma causalidad; las relaciones son exploratorias y dependen de los
  indicadores construidos.

## Fuentes de datos

| Fuente | Uso principal |
|---|---|
| ERA5-Land | Variables climaticas historicas y extendidas |
| IGN / lineas limite | Geometria municipal |
| INE | Poblacion, densidad, edad y renta |
| AEMET OpenData | Contraste externo puntual frente a ERA5-Land |
| Catastro | Edificacion, viviendas, huella edificada y densidad constructiva |
| SNCZI / IDEE | Exposicion territorial aproximada a zonas inundables |
| Open-Meteo / IGN | Altitud municipal aproximada |
| BOE DANA 2024 | Contraste externo post-evento |

## Pipeline de notebooks

Los notebooks deben ejecutarse en orden.

| Notebook | Fase | Salida principal |
|---|---|---|
| `notebook_1_ing_dato.ipynb` | Ingenieria del dato base | `DATA/PROCESSED/dataset_cv_municipios.csv` |
| `notebook_2_ing_fuentes_complementarias.ipynb` | Fuentes complementarias | `DATA/PROCESSED/dataset_cv_municipios_enriched_catastro_snczi.csv` |
| `notebook_3_analisis_dato.ipynb` | Analisis del dato | `DATA/PROCESSED/dataset_cv_municipios_analisis_municipal.csv` |
| `notebook_4_modelado_segmentacion.ipynb` | Modelado y segmentacion | `DATA/PROCESSED/dataset_cv_municipios_segmentado.csv` |
| `notebook_5_an_negocio.ipynb` | Analisis de negocio | `DATA/PROCESSED/dataset_cv_municipios_negocio.csv` |

## Modelos y tecnicas

- **KMeans**: modelo principal de segmentacion territorial.
- **Agglomerative Clustering**: contraste metodologico de estabilidad.
- **DBSCAN**: lectura auxiliar de densidad espacial y municipios singulares.
- **Random Forest Regressor**: modelo auxiliar para explicar
  `score_riesgo_exploratorio`.
- **Permutation importance**: ranking de variables influyentes en el Random
  Forest.
- **SHAP**: explicabilidad adicional del Random Forest auxiliar.
- **PCA**: diagnostico visual de la estructura de variables.

El Random Forest no predice siniestralidad real. Explica un indice exploratorio
construido a partir de datos abiertos.

## Estructura local esperada

```text
apps/
  marimo_negocio.py                         Dashboard exploratorio

DATA/
  RAW/                                      Datos brutos locales
  EXTERNAL/                                 Fuentes externas auxiliares
  PROCESSED/                                Datasets generados por el pipeline

notebooks/
  notebook_1_ing_dato.ipynb                 Ingenieria del dato base
  notebook_2_ing_fuentes_complementarias.ipynb
  notebook_3_analisis_dato.ipynb
  notebook_4_modelado_segmentacion.ipynb
  notebook_5_an_negocio.ipynb

scripts/
  ing_dato/                                 Descargas, lecturas y validaciones
  analisis_dato/                            Apoyos al analisis
  an_negocio/                               Referencia DANA 2024

output/
  ingenieria_dato/                          Manifests y trazabilidad
  analisis/                                 Auditorias y diseno de scores
  modelado/                                 Comparacion de modelos, RF y SHAP
  negocio/                                  Salidas de negocio y export BI

tests/
  test_engineering_outputs.py               Controles automaticos principales
```

Nota: `DATA/`, `output/`, `outputs/`, `venv/` y `tmp/` estan ignorados por Git
por su tamano o por ser artefactos generados localmente.

## Contenido de la entrega

La entrega del repositorio incluye codigo, notebooks, configuracion, pruebas y
descripcion tecnica del proyecto:

- `README.md`
- `requirements.txt`
- `config/pipeline_manifest.json`
- `notebooks/`
- `scripts/`
- `apps/`
- `tests/`

No se versionan datos pesados, entornos virtuales ni artefactos generados:
`DATA/`, `output/`, `outputs/`, `venv/`, `tmp/` y caches locales.

## Instalacion

En Windows, desde la raiz del proyecto:

```powershell
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

El proyecto se ha validado con `shap==0.52.0` para la explicabilidad del Random
Forest.

## Ejecucion recomendada

1. Activar el entorno virtual.
2. Asegurar que las fuentes necesarias estan disponibles en `DATA/`.
3. Ejecutar los notebooks en orden: 1, 2, 3, 4 y 5.
4. Revisar los manifests generados en `output/`.
5. Abrir el dashboard Marimo si se quiere explorar el resultado final.

Comandos reproducibles desde la raiz del proyecto:

```powershell
venv\Scripts\jupyter.exe nbconvert --to notebook --execute notebooks\notebook_1_ing_dato.ipynb --output notebook_1_ing_dato_executed.ipynb --output-dir tmp --ExecutePreprocessor.startup_timeout=180 --ExecutePreprocessor.timeout=2400
venv\Scripts\jupyter.exe nbconvert --to notebook --execute notebooks\notebook_2_ing_fuentes_complementarias.ipynb --output notebook_2_ing_fuentes_complementarias_executed.ipynb --output-dir tmp --ExecutePreprocessor.startup_timeout=180 --ExecutePreprocessor.timeout=1200
venv\Scripts\jupyter.exe nbconvert --to notebook --execute notebooks\notebook_3_analisis_dato.ipynb --output notebook_3_analisis_dato_executed.ipynb --output-dir tmp --ExecutePreprocessor.startup_timeout=180 --ExecutePreprocessor.timeout=1200
venv\Scripts\jupyter.exe nbconvert --to notebook --execute notebooks\notebook_4_modelado_segmentacion.ipynb --output notebook_4_modelado_segmentacion_executed.ipynb --output-dir tmp --ExecutePreprocessor.startup_timeout=180 --ExecutePreprocessor.timeout=1200
venv\Scripts\jupyter.exe nbconvert --to notebook --execute notebooks\notebook_5_an_negocio.ipynb --output notebook_5_an_negocio_executed.ipynb --output-dir tmp --ExecutePreprocessor.startup_timeout=180 --ExecutePreprocessor.timeout=1200
```

La salida ejecutada se escribe en `tmp/` para mantener los notebooks originales
sin outputs versionados.

### Dashboard Marimo

```powershell
venv\Scripts\activate
python -m marimo run apps\marimo_negocio.py --port 2718 --headless --no-token
```

Abrir en el navegador:

```text
http://localhost:2718
```

El dashboard permite filtrar municipios por cluster, prioridad, DANA 2024,
singularidad DBSCAN y ordenar rankings por distintas metricas, incluido el
error del Random Forest.

## Salidas principales

Las siguientes salidas se generan localmente al ejecutar el pipeline. No se
versionan en Git por tamano y porque son artefactos reproducibles.

### Datasets municipales

- `DATA/PROCESSED/dataset_cv_municipios.csv`
- `DATA/PROCESSED/dataset_cv_municipios_enriched_catastro_snczi.csv`
- `DATA/PROCESSED/dataset_cv_municipios_analisis_municipal.csv`
- `DATA/PROCESSED/dataset_cv_municipios_segmentado.csv`
- `DATA/PROCESSED/dataset_cv_municipios_negocio.csv`

### Artefactos de modelado

- `output/modelado/model_comparison.csv`
- `output/modelado/model_selection_summary.csv`
- `output/modelado/rf_score_metrics.csv`
- `output/modelado/rf_score_feature_importance.csv`
- `output/modelado/rf_score_block_importance.csv`
- `output/modelado/rf_score_shap_importance.csv`
- `output/modelado/rf_score_predictions.csv`
- `output/modelado/manifest_artefactos_modelado.csv`

### Artefactos de negocio

- `output/negocio/lectura_rf_negocio.csv`
- `output/negocio/dana_2024_metricas_contraste.csv`
- `output/negocio/municipios_prioritarios_negocio.csv`
- `output/negocio/recomendaciones_ejecutivas_negocio.csv`
- `output/negocio/cierre_ejecutivo_negocio.csv`
- `output/negocio/manifest_artefactos_negocio.csv`

### Exportacion BI

El Notebook 5 genera un paquete de tablas planas para Power BI o Excel:

```text
output/negocio/powerbi_export/
```

Incluye:

- `municipios_negocio_powerbi.csv`
- `resumen_prioridad_powerbi.csv`
- `dana_resumen_prioridad_powerbi.csv`
- `rf_importancia_shap_powerbi.csv`
- `rf_importancia_permutacion_powerbi.csv`
- `diccionario_campos_powerbi.csv`
- `manifest_powerbi_export.csv`

## Validacion

Comprobar scripts Python:

```powershell
Get-ChildItem -Path scripts -Recurse -Filter *.py | ForEach-Object {
    venv\Scripts\python.exe -m py_compile $_.FullName
}
```

Ejecutar tests:

```powershell
venv\Scripts\python.exe -m unittest tests.test_engineering_outputs
```

Validar Marimo:

```powershell
venv\Scripts\python.exe -m marimo check apps\marimo_negocio.py
```

Exportar una version HTML del dashboard:

```powershell
venv\Scripts\python.exe -m marimo export html apps\marimo_negocio.py -o tmp\marimo_negocio_check.html --no-include-code -f
```

## Decisiones metodologicas clave

1. **Ausencia de siniestros reales**
   El proyecto no fuerza un modelo predictivo sin variable objetivo real. El
   resultado es exploratorio y se basa en indicadores transparentes.

2. **Score de riesgo exploratorio**
   El score combina peligro climatico, vulnerabilidad y exposicion. Sus pesos
   son explicitos y revisables.

3. **Random Forest y SHAP**
   El Random Forest explica el score construido, no siniestralidad real. SHAP se
   usa para reforzar la interpretabilidad del indice.

4. **DANA 2024**
   La DANA 2024 se usa como contraste externo post-evento. No es validacion
   actuarial ni prueba de prediccion de siniestros.

5. **Dashboard**
   Marimo se usa como herramienta reproducible de exploracion. El proyecto
   tambien deja tablas listas para Power BI o Excel.

## Alcance metodologico

Este TFG no pretende cerrar un modelo actuarial de siniestralidad, sino
construir una base geoespacial trazable y explicable para priorizar territorios
climaticamente sensibles con datos abiertos. La base queda preparada para una
calibracion futura si se dispone de datos internos de cartera, polizas,
capitales asegurados o siniestros reales.
