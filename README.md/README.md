# TFG — Análisis Climático, Riesgo Asegurador y GeoAnalytics
**Comunidad Valenciana — ERA5 + IGN + Machine Learning + Mapas GIS**

Este repositorio contiene el desarrollo completo del pipeline de datos, ingeniería de variables, modelado e inteligencia geoespacial realizado en el Trabajo Fin de Grado.

---

## 📌 Estructura del proyecto
.
├── data/
│   ├── raw/                → Datos originales (ERA5, AEMET opcional)
│   ├── geo/                → Geometrías IGN (municipios CV)
│   ├── processed/          → Datos generados por Notebooks 1–3
│   └── outputs/            → Resultados finales (mapas, geojson, métricas)
├── notebook_1_ing_dato.ipynb
├── notebook_2_feature_engineering.ipynb
├── notebook_3_modelado.ipynb
└── notebook_4_mapas.ipynb

---

## 🧱 **Pipeline (de principio a fin)**

### **Notebook 1 — Ingeniería del dato**
- Carga de geometría municipal (IGN)
- Descarga/lectura de ERA5 (NetCDF → DataFrame)
- Asignación ERA5 → Municipios
- Agregados base por municipio
- **Salida:** `data/processed/dataset_cv_municipios.csv`

### **Notebook 2 — Feature Engineering Climático + Geoespacial + Scoring**
- Conversión de unidades ERA5, precipitación, temperatura, viento
- Acumulados móviles 24/48/72h
- Percentiles extremos (P95/P99)
- Distancia a costa y capital provincial
- Índice Compuesto de Riesgo Climático (ICRC 0–100)
- **Salida:** `data/processed/dataset_cv_municipios_features.csv`

### **Notebook 3 — Modelado predictivo**
- Preparación del conjunto de modelado
- Comparación de modelos: RandomForest, HGB, Linear Regression, XGBoost*, LightGBM*, MLP
- Interpretabilidad con SHAP
- Detección de anomalías con Isolation Forest
- PCA para visualización
- **Salidas:**  
  - `comparativa_modelos.csv`  
  - `anomalias_isolation_forest.csv`  
  - `pca_proyeccion.csv`

### **Notebook 4 — Mapas (GIS)**
- Carga de municipios + dataset enriquecido
- Clustering municipal (K‑Means y DBSCAN)
- Mapas estáticos (GeoPandas + Contextily)
- Mapas interactivos (Folium)
- Ranking de anomalías climáticas
- **Salidas:**  
  - `municipios_clu_anom.geojson`  
  - `mapa_municipios_interactivo.html`

---

## 🧰 **Requisitos de software**

Las dependencias están en `requirements.txt`.

### Recomendación:  
Crear un entorno virtual:

```bash
python -m venv .venv
source .venv/bin/activate      # Linux/Mac
.venv\Scripts\activate         # Windows
Instalar dependencias:
Shellpip install -r requirements.txtMostrar más líneas

🔍 Reproducción del proyecto
Ejecutar los notebooks en este orden:

notebook_1_ing_dato.ipynb
notebook_2_feature_engineering.ipynb
notebook_3_modelado.ipynb
notebook_4_mapas.ipynb



✒️ Autor
Gonzalo Larriba Delicado
Trabajo Fin de Grado – Comunidad Valenciana
