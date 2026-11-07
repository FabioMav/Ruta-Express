# Ruta Expres · CI/CD con validacion y monitoreo de drift (Evidently)

Practica 4 (Unidad 5) · Fabio Mavric · UNIVALLE Cochabamba

Sistema que valida los lotes de pedidos de Ruta Expres, detecta cambios en
la distribucion de los datos (drift) con Evidently y publica automaticamente
un informe en GitHub Pages con GitHub Actions. Si el lote tiene datos
invalidos, el flujo se detiene antes de publicar y la pagina conserva la
ultima version correcta.

## El caso

Ruta Expres estima el tiempo de entrega de cada pedido. El piloto (lote
`base`) salio sobre todo hacia el centro. Despues se amplio a la periferia.
Este proyecto responde tres preguntas:

- **CI** · ¿se puede procesar el lote con confianza? (`validador.py` revisa
  estructura y reglas de cada fila)
- **Evidently** · ¿cambio el tipo de pedidos que se estan recibiendo?
  (`generar_informe.py` compara `distancia_km`, `entrega_min` e `importe_bs`
  entre el lote base y el lote actual)
- **CD** · ¿donde consulta operaciones el resultado? (GitHub Pages, publicado
  solo cuando el lote es valido)

## Preparacion de los datos

El archivo adjunto de la tarea (`datos/pedidos_ruta_express.csv`, 360
pedidos ficticios en tres lotes de 120) se dejo intacto en el repositorio y
se separo en cuatro archivos con un script de Python (sin usar hoja de
calculo), agrupando por el valor exacto de la columna `lote`:

| Archivo | Lote | Fecha | Filas | Centro | Periferia |
|---|---|---|---|---|---|
| `datos/referencia.csv` | `base` (piloto, fijo en las 4 ejecuciones) | 2026-10-05 | 120 | 115 | 5 |
| `datos/control.csv` | `control` (otra semana, antes de ampliar cobertura) | 2026-10-12 | 120 | 118 | 2 |
| `datos/expansion.csv` | `expansion` (primera semana con mas cobertura) | 2026-10-19 | 120 | 16 | 104 |
| `datos/actual.csv` | copia de `control.csv` (escenario 1, primera ejecucion) | 2026-10-12 | 120 | 118 | 2 |

Se comprobo programaticamente que cada grupo tiene exactamente 120 filas y
que no hay `pedido_id` repetidos dentro de cada archivo, antes de guardarlos.
`referencia.csv`, `control.csv` y `expansion.csv` se mantienen como copias
intactas durante toda la practica; el unico archivo que cambia entre
ejecuciones es `datos/actual.csv` (se sobreescribe localmente, antes de cada
push, con el contenido completo del lote que corresponda al escenario).

GitHub Actions siempre valida y compara `datos/referencia.csv` contra
`datos/actual.csv` — nunca lee `control.csv` ni `expansion.csv` directamente.

## Reglas del validador (`validador.py`)

Se aplican por igual a `referencia.csv` y a `actual.csv`:

| Regla | Detalle |
|---|---|
| Archivo legible | Debe existir y poder leerse como CSV |
| Encabezados | Deben estar las 7 columnas: `pedido_id, fecha_lote, lote, zona, distancia_km, entrega_min, importe_bs` |
| Al menos una fila | El archivo no puede tener solo el encabezado |
| `pedido_id` | Obligatorio (no vacio) y **unico** dentro del archivo |
| `fecha_lote` | Fecha valida en formato `AAAA-MM-DD` |
| `zona` | Unicamente `centro` o `periferia` |
| Un solo lote | Todas las filas del archivo deben compartir el mismo valor de `lote` |
| Una sola fecha | Todas las filas del archivo deben compartir la misma `fecha_lote` |
| `lote` de referencia | Debe ser exactamente `base` |
| `lote` de actual | Debe ser `control` o `expansion` (nunca `base`) |
| `distancia_km`, `entrega_min`, `importe_bs` | Numeros finitos **mayores que 0** (sin maximo: una entrega larga es un dato valido, es justamente lo que Evidently debe poder observar) |

Si una regla falla, el validador junta **todos** los errores encontrados
(no se detiene en el primero), identifica el archivo y, para errores de
fila, la fila y/o el `pedido_id` y la columna afectada. Termina con codigo
de salida distinto de cero, lo que detiene el job `ci` y hace que GitHub
Actions omita el job `cd` automaticamente.

## El informe de Evidently (`generar_informe.py`)

Antes de generar nada, el script vuelve a correr la misma validacion que el
paso de CI (por seguridad, para no depender del orden de ejecucion).
Despues:

- Compara `distancia_km`, `entrega_min` e `importe_bs` entre
  `datos/referencia.csv` (lote base) y `datos/actual.csv` (lote vigente),
  con un `DataDriftPreset` de Evidently.
- Metodo: test de **Kolmogorov-Smirnov** por variable numerica. Umbral por
  variable: **p-valor < 0.05** (se considera que esa variable cambio de
  distribucion). Umbral del conjunto: si el **50% o mas** de las variables
  comparadas tienen drift, el lote completo se marca con drift. Se usa el
  mismo metodo y los mismos umbrales en las cuatro ejecuciones.
- Genera `public/informe.html` (el informe completo de Evidently, con
  histogramas y estadisticas por variable).
- Genera `public/index.html`, la portada: nombres y fechas de ambos lotes,
  cantidad de filas de cada uno, conteos por `zona` (centro/periferia) de
  cada archivo, el identificador del commit (`GITHUB_SHA` cuando corre en
  Actions, `local` en tu computadora), un resumen de drift con el chip
  "Con drift"/"Sin drift" por variable, y un enlace relativo a
  `informe.html`.

## Estructura del proyecto

```
datos/
  pedidos_ruta_express.csv   # original de la tarea, intacto
  referencia.csv             # lote base (fijo)
  control.csv                # lote control (copia intacta)
  expansion.csv              # lote expansion (copia intacta)
  actual.csv                 # el lote vigente en cada ejecucion (cambia)
validador.py                 # reglas de validacion
generar_informe.py           # informe de Evidently + portada
test_validador.py            # 12 pruebas automatizadas
requirements.txt
.gitignore                   # excluye .venv/ y public/ (se genera en cada corrida)
.github/workflows/ruta-expres.yml
githooks/post-commit         # comodidad local opcional (push automatico)
README.md
```

## Como ejecutarlo en tu computadora

1. Python 3.12 en un entorno virtual:

   ```
   python3.12 -m venv .venv
   ```

   Activa el entorno (en VS Code, selecciona el interprete `.venv`) y, en
   una terminal nueva, comprueba:

   ```
   python --version        # debe mostrar 3.12.x
   ```

2. Instalar dependencias (version exacta usada y probada en este proyecto:
   `pandas==3.0.5`, `evidently==0.7.23`):

   ```
   pip install -r requirements.txt
   ```

3. Ejecutar las pruebas automaticas:

   ```
   python -m unittest discover -v
   ```

4. Validar los archivos de trabajo:

   ```
   python validador.py
   ```

5. Generar el informe y la portada localmente:

   ```
   python generar_informe.py
   ```

   Abre `public/index.html` y `public/informe.html` en el navegador y
   comprueba el enlace entre ambos y que se vean las tres variables.

## Push automatico al hacer commit (opcional, solo comodidad local)

Este repositorio incluye el mismo hook de `post-commit` usado en las
practicas anteriores: configuralo una vez por clon si queres que "Commit"
en GitHub Desktop haga tambien el push:

```
git config core.hooksPath githooks
```

En Mac/Linux, ademas: `chmod +x githooks/post-commit`.

## Pasos para crear y publicar el proyecto

1. Crea un repositorio **publico** en GitHub (por ejemplo `ruta-expres-cicd`)
   y clonalo con GitHub Desktop en una carpeta vacia.
2. Copia todo el contenido de este proyecto dentro de esa carpeta (incluye
   los archivos ocultos `.gitignore` y `.github/`).
3. En GitHub Desktop: Commit (mensaje, por ejemplo, "Version inicial:
   validacion, Evidently y workflow de CI/CD") y Push origin.
4. En GitHub, ve a **Settings → Pages → Source** y selecciona
   **"GitHub Actions"**.
5. Entra a la pestana **Actions** y espera a que termine la ejecucion
   disparada por tu push. Si `ci` y `cd` quedan en verde, la portada ya
   esta publicada.

## Demostracion en 4 ejecuciones

Antes de empezar, confirma que Pages ya este configurado (paso 4 de
arriba). Para cada escenario: cambia solo lo que se indica, haz commit y
push, espera a que termine Actions, y revisa Pages antes de pasar al
siguiente. Guarda el enlace a cada ejecucion para tu informe.

### 1. Semana de control

`datos/actual.csv` ya es una copia de `control.csv` desde la preparacion
inicial (no hay que tocar nada). Con el primer push del proyecto:

- Esperado: `ci` y `cd` en verde. La portada muestra el lote `control`
  (120 pedidos, 118 centro / 2 periferia) contra `base` (120 pedidos, 115
  centro / 5 periferia).
- Evidently (comprobado localmente antes de entregar): **sin drift** en
  ninguna variable (p-valores: distancia_km 0.588, entrega_min 0.484,
  importe_bs 0.801 — los tres muy por encima de 0.05). Es razonable: ambos
  son lotes de la zona centro, antes de la expansion.

### 2. Semana de expansion

Reemplaza el contenido completo de `datos/actual.csv` por el de
`datos/expansion.csv` (por ejemplo: `cp datos/expansion.csv datos/actual.csv`
o copialo manualmente) y push.

- Esperado: `ci` acepta el lote (sigue siendo valido), la portada muestra
  `expansion` (120 pedidos, pero ahora 16 centro / 104 periferia — el giro
  hacia la periferia se ve directamente en los conteos).
- Evidently (comprobado localmente): **drift detectado** — 2 de 3
  variables (67%, por encima del umbral del 50%). `distancia_km` y
  `entrega_min` cambian de distribucion de forma muy marcada (p-valor
  practicamente 0, consistente con recorridos mas largos hacia la
  periferia); `importe_bs` **no** tiene drift (p-valor 0.237): el monto
  cobrado no cambio de forma significativa aunque la distancia si.

### 3. Error de captura

En una fila de `datos/actual.csv` (que en este punto es una copia de
`expansion.csv`), anota el valor original de `entrega_min` y cambialo a
negativo. Por ejemplo, la primera fila (`RE-0241`) tiene `entrega_min=43.9`;
cambiala a `-43.9`. Push.

- Esperado (comprobado localmente contra el mensaje real del validador):
  `ci` falla en el paso "Validar datos/referencia.csv y datos/actual.csv"
  con un mensaje como:

  ```
  ERROR: se encontraron datos invalidos; no se genera el informe.
    - datos/actual.csv, fila 2 (pedido RE-0241), columna 'entrega_min': debe ser mayor que 0 (se encontro '-43.9')
  ```

  `cd` queda **omitido** (no se ejecuta, por el `needs: ci`). En GitHub
  Pages, la portada sigue mostrando el commit de la ultima publicacion
  exitosa (el del escenario 2), no el dato invalido.

### 4. Recuperacion

Restaura `entrega_min` a su valor original (`43.9` en el ejemplo de
arriba) en `datos/actual.csv` y vuelve a hacer push.

- Esperado: `ci` y `cd` vuelven a quedar en verde, la portada muestra el
  nuevo commit. Como el contenido de `actual.csv` vuelve a ser identico al
  del escenario 2 (expansion), es esperable que el resultado de drift
  coincida exactamente con el de ese escenario.

## Demostracion en clase

Para la demostracion en vivo (incorporar un pedido invalido y otro valido,
hacer commit y push, y explicar el bloqueo o la actualizacion del sitio),
se puede repetir una version corta de los escenarios 3 y 4 sobre
`datos/actual.csv`: agregar o editar una fila con un valor invalido
(`entrega_min`, `distancia_km` o `importe_bs` en 0 o negativo, o una `zona`
que no sea `centro`/`periferia`) para mostrar el bloqueo, y despues
corregirla para mostrar la recuperacion.

## Entrega

- Enlace al repositorio publico de GitHub (codigo, datos, pruebas,
  workflow y este README).
- Enlace a la portada publicada en GitHub Pages
  (`https://<usuario>.github.io/<repositorio>/`).
- Informe en PDF con la preparacion de los datos, la organizacion del
  proyecto, las etapas de CI/CD, los resultados de las pruebas y capturas
  de las 4 ejecuciones.
