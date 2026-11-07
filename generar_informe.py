"""
generar_informe.py
Genera el informe de deriva (drift) de Evidently entre datos/referencia.csv
(lote base, fijo) y datos/actual.csv (el lote de esta ejecucion: control o
expansion), mas una portada (public/index.html) con un resumen que
operaciones pueda leer de un vistazo, con un enlace relativo al informe
completo de Evidently (public/informe.html).

Antes de generar nada, vuelve a correr la misma validacion que el paso de
CI (validador.py) por seguridad: si este script se ejecuta fuera de orden
(sin pasar primero por el validador), no debe producir un informe a partir
de datos invalidos.
"""
import html
import os
import sys
from datetime import datetime, timezone

import pandas as pd
from evidently import Report
from evidently.presets import DataDriftPreset

import validador

RUTA_REFERENCIA = validador.RUTA_REFERENCIA
RUTA_ACTUAL = validador.RUTA_ACTUAL
DIRECTORIO_SALIDA = "public"
ARCHIVO_INFORME = f"{DIRECTORIO_SALIDA}/informe.html"
ARCHIVO_PORTADA = f"{DIRECTORIO_SALIDA}/index.html"

COLUMNAS_COMPARADAS = ["distancia_km", "entrega_min", "importe_bs"]
NOMBRES_COLUMNAS = {
    "distancia_km": "Distancia (km)",
    "entrega_min": "Tiempo de entrega (min)",
    "importe_bs": "Importe (Bs)",
}
UMBRAL_DRIFT_COLUMNA = 0.05  # p-valor del test Kolmogorov-Smirnov
UMBRAL_DRIFT_CONJUNTO = 0.5  # fraccion de columnas con drift para marcar el lote

NOMBRE_ESTUDIANTE = "Fabio Mavric"


def resumen_lote(ruta):
    df = pd.read_csv(ruta, dtype=str)
    return {
        "lote": df["lote"].iloc[0],
        "fecha_lote": df["fecha_lote"].iloc[0],
        "total": len(df),
        "centro": int((df["zona"] == "centro").sum()),
        "periferia": int((df["zona"] == "periferia").sum()),
    }


def calcular_drift(ruta_referencia, ruta_actual):
    ref = pd.read_csv(ruta_referencia)[COLUMNAS_COMPARADAS]
    act = pd.read_csv(ruta_actual)[COLUMNAS_COMPARADAS]

    reporte = Report(metrics=[DataDriftPreset(
        columns=COLUMNAS_COMPARADAS,
        drift_share=UMBRAL_DRIFT_CONJUNTO,
        num_threshold=UMBRAL_DRIFT_COLUMNA,
    )])
    snapshot = reporte.run(current_data=act, reference_data=ref)
    snapshot.save_html(ARCHIVO_INFORME)

    datos = snapshot.dict()
    por_columna = []
    resumen_conjunto = {"count": 0, "share": 0.0}

    for metrica in datos["metrics"]:
        nombre = metrica["metric_name"]
        if nombre.startswith("DriftedColumnsCount"):
            resumen_conjunto = metrica["value"]
        elif nombre.startswith("ValueDrift"):
            columna = metrica["config"]["column"]
            umbral = metrica["config"].get("threshold", UMBRAL_DRIFT_COLUMNA)
            p_valor = metrica["value"]
            por_columna.append({
                "columna": columna,
                "p_valor": p_valor,
                "umbral": umbral,
                "con_drift": p_valor < umbral,
            })

    orden = {c: i for i, c in enumerate(COLUMNAS_COMPARADAS)}
    por_columna.sort(key=lambda d: orden.get(d["columna"], 99))

    return {
        "por_columna": por_columna,
        "columnas_con_drift": int(resumen_conjunto.get("count", 0)),
        "proporcion_con_drift": float(resumen_conjunto.get("share", 0.0)),
        "drift_en_el_conjunto": resumen_conjunto.get("share", 0.0) >= UMBRAL_DRIFT_CONJUNTO,
    }


def generar_portada(resumen_ref, resumen_act, drift, hora_generacion_utc, commit_sha):
    chip_conjunto = (
        '<span class="chip alerta">Posible deriva (drift)</span>' if drift["drift_en_el_conjunto"]
        else '<span class="chip ok">Sin deriva significativa</span>'
    )

    def _chip_drift(con_drift):
        return '<span class="chip alerta">Con drift</span>' if con_drift else '<span class="chip ok">Sin drift</span>'

    filas_drift = "\n".join(
        f'<tr><td>{html.escape(NOMBRES_COLUMNAS.get(d["columna"], d["columna"]))}</td>'
        f'<td class="num">{d["p_valor"]:.4g}</td>'
        f'<td class="num">{d["umbral"]:.2f}</td>'
        f'<td>{_chip_drift(d["con_drift"])}</td></tr>'
        for d in drift["por_columna"]
    )

    def fila_zona(etiqueta, resumen):
        return (
            f'<tr><td>{html.escape(etiqueta)}</td>'
            f'<td class="num">{resumen["total"]}</td>'
            f'<td class="num">{resumen["centro"]}</td>'
            f'<td class="num">{resumen["periferia"]}</td></tr>'
        )

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ruta Expres &middot; Monitoreo de entregas</title>
<style>
  :root {{
    color-scheme: light;
    --page: #f9f9f7; --surface: #fcfcfb; --ink: #0b0b0b; --ink-2: #52514e; --ink-muted: #898781;
    --border: rgba(11,11,11,0.10); --grid: #e1e0d9;
    --series-1: #2a78d6; --series-3: #1baf7a;
    --tint-1: rgba(42,120,214,0.08); --tint-3: rgba(27,175,122,0.10);
    --good: #0ca30c; --good-tint: rgba(12,163,12,0.12);
    --warn: #c98500; --warn-tint: rgba(237,161,0,0.16);
    --shadow: 0 1px 2px rgba(11,11,11,0.04), 0 8px 24px -16px rgba(11,11,11,0.18);
  }}
  :root:where(:not([data-theme="light"])) {{
    @media (prefers-color-scheme: dark) {{
      color-scheme: dark;
      --page: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink-2: #c3c2b7; --ink-muted: #898781;
      --border: rgba(255,255,255,0.10); --grid: #2c2c2a;
      --series-1: #3987e5; --series-3: #199e70;
      --tint-1: rgba(57,135,229,0.12); --tint-3: rgba(25,158,112,0.14);
      --good: #0ca30c; --good-tint: rgba(12,163,12,0.16);
      --warn: #eda100; --warn-tint: rgba(201,133,0,0.20);
      --shadow: 0 1px 2px rgba(0,0,0,0.3), 0 8px 24px -16px rgba(0,0,0,0.5);
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; margin: 0;
          padding: 2.5rem 1rem 4rem; background: var(--page); color: var(--ink); line-height: 1.55; font-size: 16px; }}
  main {{ max-width: 960px; margin: 0 auto; background: var(--surface); border: 1px solid var(--border);
          border-radius: 16px; box-shadow: var(--shadow); padding: 2.2rem clamp(1.2rem, 4vw, 2.8rem) 2.6rem; }}
  h1 {{ margin: 0 0 0.3rem; font-size: 1.6rem; font-weight: 800; letter-spacing: -0.01em; }}
  h2 {{ font-size: 1.1rem; font-weight: 700; margin: 2.2rem 0 0.8rem; padding-top: 1.4rem; border-top: 1px solid var(--grid); }}
  .subtitulo {{ color: var(--ink-2); margin: 0 0 1.1rem; font-size: 0.95rem; }}
  a {{ color: var(--series-1); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .meta {{ display: flex; flex-wrap: wrap; gap: 0.5rem 1rem; align-items: center; font-size: 0.82rem;
           color: var(--ink-muted); margin: 0 0 1.6rem; }}
  .meta code {{ background: var(--tint-1); color: var(--ink-2); border-radius: 5px; padding: 0.1rem 0.4rem; font-size: 0.82em; }}

  .boton {{ display: inline-flex; align-items: center; gap: 0.4rem; background: var(--series-1); color: #fff;
            font-weight: 700; font-size: 0.92rem; padding: 0.65rem 1.1rem; border-radius: 10px; margin: 0.4rem 0 0.2rem; }}
  .boton:hover {{ text-decoration: none; opacity: 0.92; }}

  .indicadores {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 0.9rem; margin: 0 0 0.4rem; }}
  .indicador {{ background: var(--tint-1); border: 1px solid var(--border); border-radius: 12px; padding: 0.9rem 1.05rem; }}
  .indicador .valor {{ font-size: 1.4rem; font-weight: 800; font-variant-numeric: tabular-nums; letter-spacing: -0.01em; }}
  .indicador .etiqueta {{ font-size: 0.76rem; color: var(--ink-2); text-transform: uppercase; letter-spacing: 0.03em; margin-top: 0.15rem; }}

  .banner {{ border-radius: 12px; padding: 1rem 1.2rem; margin: 0.4rem 0 0.2rem; display: flex;
             align-items: center; gap: 0.6rem; font-weight: 600; }}
  .banner.alerta {{ background: var(--warn-tint); color: var(--ink); }}
  .banner.ok {{ background: var(--good-tint); color: var(--ink); }}

  .chip {{ display: inline-flex; align-items: center; gap: 0.35rem; font-size: 0.78rem; font-weight: 700;
           padding: 0.15rem 0.55rem; border-radius: 999px; white-space: nowrap; }}
  .chip.ok {{ background: var(--good-tint); color: var(--good); }}
  .chip.alerta {{ background: var(--warn-tint); color: var(--warn); }}

  .tabla-scroll {{ overflow-x: auto; border: 1px solid var(--border); border-radius: 10px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.86rem; min-width: 420px; }}
  th, td {{ padding: 0.55rem 0.7rem; text-align: left; border-bottom: 1px solid var(--grid); }}
  td.num, th.num {{ font-variant-numeric: tabular-nums; text-align: right; }}
  thead th {{ background: var(--tint-1); color: var(--ink-2); font-size: 0.74rem; text-transform: uppercase;
              letter-spacing: 0.03em; font-weight: 700; }}
  tbody tr:last-child td {{ border-bottom: none; }}

  footer {{ margin-top: 2.4rem; padding-top: 1.2rem; border-top: 1px solid var(--grid); font-size: 0.8rem; color: var(--ink-muted); }}
  footer p {{ margin: 0.3rem 0; }}
</style>
</head>
<body>
<main>
  <h1>Ruta Expres &middot; Monitoreo de entregas</h1>
  <p class="subtitulo">{html.escape(NOMBRE_ESTUDIANTE)} &middot; comparacion del lote actual contra el piloto (lote base) con Evidently</p>
  <p class="meta">Generado <strong>{hora_generacion_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC</strong>
    &middot; commit <code>{html.escape(commit_sha)}</code></p>

  <a class="boton" href="informe.html">Ver el informe completo de Evidently &rarr;</a>

  <h2>Lotes comparados</h2>
  <div class="tabla-scroll">
  <table>
    <thead><tr><th>Archivo</th><th>Lote</th><th>Fecha</th><th class="num">Pedidos</th>
      <th class="num">Centro</th><th class="num">Periferia</th></tr></thead>
    <tbody>
      <tr><td>referencia.csv (piloto)</td><td>{html.escape(resumen_ref["lote"])}</td>
        <td>{html.escape(resumen_ref["fecha_lote"])}</td><td class="num">{resumen_ref["total"]}</td>
        <td class="num">{resumen_ref["centro"]}</td><td class="num">{resumen_ref["periferia"]}</td></tr>
      <tr><td>actual.csv (este lote)</td><td>{html.escape(resumen_act["lote"])}</td>
        <td>{html.escape(resumen_act["fecha_lote"])}</td><td class="num">{resumen_act["total"]}</td>
        <td class="num">{resumen_act["centro"]}</td><td class="num">{resumen_act["periferia"]}</td></tr>
    </tbody>
  </table>
  </div>

  <h2>Resumen de deriva (drift)</h2>
  <div class="banner {'alerta' if drift['drift_en_el_conjunto'] else 'ok'}">
    {chip_conjunto}
    <span>{drift["columnas_con_drift"]} de {len(COLUMNAS_COMPARADAS)} variables con drift
      ({drift["proporcion_con_drift"]*100:.0f}%, umbral del conjunto: {UMBRAL_DRIFT_CONJUNTO*100:.0f}%)</span>
  </div>
  <div class="indicadores">
    <div class="indicador"><div class="valor">{drift["columnas_con_drift"]}</div><div class="etiqueta">Variables con drift</div></div>
    <div class="indicador"><div class="valor">{UMBRAL_DRIFT_COLUMNA:.2f}</div><div class="etiqueta">Umbral por variable (p-valor K-S)</div></div>
    <div class="indicador"><div class="valor">{UMBRAL_DRIFT_CONJUNTO*100:.0f}%</div><div class="etiqueta">Umbral del conjunto</div></div>
  </div>
  <div class="tabla-scroll">
  <table>
    <thead><tr><th>Variable</th><th class="num">p-valor (K-S)</th><th class="num">Umbral</th><th>Resultado</th></tr></thead>
    <tbody>
    {filas_drift}
    </tbody>
  </table>
  </div>
  <p class="meta">Metodo: Kolmogorov-Smirnov por variable numerica (DataDriftPreset de Evidently).
    Un p-valor por debajo del umbral indica que la distribucion de esa variable en el lote actual
    es significativamente distinta a la del piloto. El detalle completo (histogramas y estadisticas)
    esta en el <a href="informe.html">informe de Evidently</a>.</p>

  <footer>
    <p>Datos: pedidos_ruta_express.csv (simulado para esta practica). Esta pagina compara
      siempre datos/referencia.csv (lote base, fijo) contra datos/actual.csv (el lote vigente
      en este commit).</p>
    <p>Generado automaticamente por GitHub Actions a partir de los CSV del repositorio,
      en cada push a <code>main</code> que pase la validacion.</p>
  </footer>
</main>
</body>
</html>
"""


def main():
    try:
        validador.validar(RUTA_REFERENCIA, RUTA_ACTUAL)
    except validador.DatosInvalidos as exc:
        print("ERROR: datos invalidos; no se genera el informe.", file=sys.stderr)
        for mensaje in exc.errores:
            print(f"  - {mensaje}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(DIRECTORIO_SALIDA, exist_ok=True)

    resumen_ref = resumen_lote(RUTA_REFERENCIA)
    resumen_act = resumen_lote(RUTA_ACTUAL)
    drift = calcular_drift(RUTA_REFERENCIA, RUTA_ACTUAL)

    hora_generacion_utc = datetime.now(timezone.utc)
    commit_sha = os.environ.get("GITHUB_SHA") or "local"

    portada = generar_portada(resumen_ref, resumen_act, drift, hora_generacion_utc, commit_sha)
    with open(ARCHIVO_PORTADA, "w", encoding="utf-8") as f:
        f.write(portada)

    print(
        f"OK: {ARCHIVO_INFORME} y {ARCHIVO_PORTADA} generados. "
        f"Lote actual: {resumen_act['lote']} ({resumen_act['total']} pedidos). "
        f"Variables con drift: {drift['columnas_con_drift']}/{len(COLUMNAS_COMPARADAS)}."
    )


if __name__ == "__main__":
    main()
