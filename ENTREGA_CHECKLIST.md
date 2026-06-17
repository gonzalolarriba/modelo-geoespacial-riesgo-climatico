# Checklist final de entrega

Este archivo resume que debe revisarse antes de entregar o subir el repositorio
del TFG. No sustituye a la memoria final; sirve como guia rapida para no olvidar
ningun punto tecnico.

## 1. Estado del repositorio

Antes de entregar:

```powershell
git status --short
git log -1 --oneline
```

Resultado esperado:

- `git status --short` no debe mostrar cambios.
- El ultimo commit debe corresponder a la version final que se quiere entregar.
- El README debe estar en la raiz como `README.md`.
- No deben aparecer carpetas locales de documentacion, datos, outputs o entorno.

## 2. Que incluye GitHub

El repositorio tecnico debe incluir:

- `README.md`
- `requirements.txt`
- `config/pipeline_manifest.json`
- `notebooks/notebook_1_ing_dato.ipynb`
- `notebooks/notebook_2_ing_fuentes_complementarias.ipynb`
- `notebooks/notebook_3_analisis_dato.ipynb`
- `notebooks/notebook_4_modelado_segmentacion.ipynb`
- `notebooks/notebook_5_an_negocio.ipynb`
- `scripts/`
- `apps/marimo_negocio.py`
- `tests/test_engineering_outputs.py`
- `ENTREGA_CHECKLIST.md`

## 3. Que no incluye GitHub

Estas carpetas se mantienen fuera del repo por tamano, privacidad o porque son
artefactos generados:

- `DATA/`
- `output/`
- `outputs/`
- `venv/`
- `tmp/`
- `docs/`
- `documentacion_ufv/`

Importante: `documentacion_ufv/` se conserva localmente para preparar memoria y
defensa, pero no forma parte del repo de entrega.

## 4. Artefactos que conviene conservar aparte

Si el evaluador necesita revisar resultados sin regenerar todo el pipeline,
conviene tener una copia aparte de:

- `output/ingenieria_dato/`
- `output/analisis/`
- `output/modelado/`
- `output/negocio/`
- `DATA/PROCESSED/dataset_cv_municipios_analisis_municipal.csv`
- `DATA/PROCESSED/dataset_cv_municipios_segmentado.csv`
- `DATA/PROCESSED/dataset_cv_municipios_negocio.csv`

No subir `DATA/` completo salvo que la entrega lo pida expresamente: pesa mucho
y contiene artefactos intermedios grandes.

## 5. Validacion rapida

Ejecutar desde la raiz del proyecto:

```powershell
venv\Scripts\python.exe -m unittest tests.test_engineering_outputs
```

Resultado esperado:

```text
Ran 12 tests
OK
```

Comprobar scripts:

```powershell
Get-ChildItem -Path scripts -Recurse -Filter *.py | ForEach-Object {
    venv\Scripts\python.exe -m py_compile $_.FullName
}
```

Comprobar Marimo:

```powershell
venv\Scripts\python.exe -m marimo check apps\marimo_negocio.py
```

Puede aparecer un warning local de configuracion en Windows; lo importante es
que el comando termine con codigo correcto.

## 6. Dashboard Marimo

Para abrir el dashboard:

```powershell
venv\Scripts\activate
python -m marimo run apps\marimo_negocio.py --port 2718 --headless --no-token
```

Abrir:

```text
http://localhost:2718
```

El dashboard usa el dataset final de negocio cuando esta disponible:

- `DATA/PROCESSED/dataset_cv_municipios_negocio.csv`
- `DATA/PROCESSED/dataset_cv_municipios_segmentado.csv`

## 7. Pipeline de notebooks

Orden recomendado:

1. `notebook_1_ing_dato.ipynb`
2. `notebook_2_ing_fuentes_complementarias.ipynb`
3. `notebook_3_analisis_dato.ipynb`
4. `notebook_4_modelado_segmentacion.ipynb`
5. `notebook_5_an_negocio.ipynb`

El orden tambien queda declarado en:

```text
config/pipeline_manifest.json
```

## 8. Mensaje clave de alcance

Frase recomendable para memoria o defensa:

> El TFG no pretende construir un modelo actuarial ni predecir siniestros reales
> de hogar, porque no existe una base publica completa de siniestralidad
> municipal. El trabajo construye una base geoespacial reproducible con open
> data para priorizar territorios, segmentar municipios, explicar un indice
> exploratorio y preparar una futura calibracion con datos internos.

## 9. Puntos fuertes para defender

- Integracion de varias fuentes oficiales y abiertas: ERA5-Land, INE, AEMET,
  Catastro, SNCZI, geometria municipal y BOE DANA 2024.
- Pipeline completo desde ingenieria del dato hasta negocio.
- Trazabilidad mediante manifests y tests.
- Score exploratorio descompuesto en peligro climatico, vulnerabilidad y
  exposicion fisica.
- Segmentacion territorial con KMeans, contraste Agglomerative y lectura
  auxiliar DBSCAN.
- Random Forest y SHAP como explicabilidad del score, no como prediccion de
  siniestros.
- DANA 2024 como contraste externo post-evento, no como validacion actuarial.
- Dashboard Marimo y paquete de tablas para Power BI/Excel.

## 10. Cautelas que conviene decir claramente

- El score es exploratorio y no equivale a prima, frecuencia ni coste esperado.
- RF/SHAP explican un indice construido, no causalidad ni siniestralidad real.
- DANA 2024 aporta contraste externo parcial, no validacion predictiva fuerte.
- AEMET se usa como validacion puntual, no como sustituto completo de ERA5-Land.
- Para uso real harian falta polizas, capitales asegurados, cartera y siniestros
  historicos geocodificados o agregados.

