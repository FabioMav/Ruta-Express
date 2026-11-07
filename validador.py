"""
validador.py
Valida datos/referencia.csv y datos/actual.csv antes de generar el informe.
No corrige ni descarta nada en silencio: junta TODOS los errores que
encuentra (con el archivo, la fila/pedido y la columna cuando corresponde)
y termina con codigo de salida distinto de cero si hay al menos uno.

Reglas, segun la consigna:
  - Cada archivo debe poder leerse, tener los 7 encabezados obligatorios
    y al menos una fila de datos.
  - pedido_id: obligatorio (no vacio) y unico dentro de cada archivo.
  - fecha_lote: fecha valida en formato AAAA-MM-DD.
  - zona: unicamente "centro" o "periferia".
  - Cada archivo debe tener un solo valor de "lote" y una sola fecha_lote.
  - referencia.csv debe ser el lote "base".
  - actual.csv debe ser el lote "control" o "expansion".
  - distancia_km, entrega_min e importe_bs: numeros finitos > 0 (sin
    maximo; una entrega larga es un dato valido, es justamente lo que
    Evidently debe poder detectar como cambio de distribucion).
"""
import csv
import sys
from datetime import datetime

RUTA_REFERENCIA = "datos/referencia.csv"
RUTA_ACTUAL = "datos/actual.csv"

COLUMNAS_OBLIGATORIAS = {
    "pedido_id", "fecha_lote", "lote", "zona",
    "distancia_km", "entrega_min", "importe_bs",
}
ZONAS_VALIDAS = {"centro", "periferia"}
COLUMNAS_NUMERICAS = ["distancia_km", "entrega_min", "importe_bs"]


class DatosInvalidos(Exception):
    """Junta uno o mas errores de validacion."""

    def __init__(self, errores):
        self.errores = list(errores)
        super().__init__("\n".join(self.errores))


def _leer_filas(ruta, errores):
    """Devuelve (fieldnames, filas) o None si el archivo no se pudo leer
    o le faltan encabezados/filas (y agrega el error correspondiente)."""
    try:
        with open(ruta, newline="", encoding="utf-8") as f:
            lector = csv.DictReader(f, restkey="__campos_de_mas__")
            fieldnames = lector.fieldnames or []
            filas = list(lector)
    except FileNotFoundError:
        errores.append(f"{ruta}: no se encontro el archivo")
        return None
    except OSError as exc:
        errores.append(f"{ruta}: no se pudo leer ({exc})")
        return None

    faltantes = COLUMNAS_OBLIGATORIAS - set(fieldnames)
    if faltantes:
        errores.append(
            f"{ruta}: faltan columnas obligatorias: {sorted(faltantes)}"
        )
        return None

    if not filas:
        errores.append(f"{ruta}: no tiene ninguna fila de datos (solo encabezado)")
        return None

    return fieldnames, filas


def _validar_fecha(texto):
    try:
        datetime.strptime(texto, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False


def validar_archivo(ruta, lotes_permitidos, errores):
    """Valida un archivo (referencia.csv o actual.csv) por completo.
    lotes_permitidos: conjunto de valores validos para la columna 'lote'
    en ESTE archivo (p.ej. {'base'} para referencia, {'control','expansion'}
    para actual). Agrega todos los errores encontrados a 'errores' (no
    lanza excepcion); devuelve la lista de filas validas segun id/zona/
    numeros, aunque el archivo termine siendo invalido por otra regla."""
    resultado = _leer_filas(ruta, errores)
    if resultado is None:
        return []
    fieldnames, filas = resultado

    n_columnas_esperadas = len(fieldnames)
    ids_vistos = {}
    lotes_vistos = set()
    fechas_vistas = set()
    filas_validas = []

    for indice, fila in enumerate(filas):
        numero_fila = indice + 2  # la fila 1 es el encabezado
        pedido_id = (fila.get("pedido_id") or "").strip()
        etiqueta = pedido_id if pedido_id else f"sin id, fila {numero_fila}"

        if "__campos_de_mas__" in fila or any(fila.get(c) is None for c in fieldnames):
            errores.append(
                f"{ruta}, fila {numero_fila}: no tiene los {n_columnas_esperadas} "
                f"campos esperados segun el encabezado"
            )
            continue

        if not pedido_id:
            errores.append(f"{ruta}, fila {numero_fila}, columna 'pedido_id': identificador vacio")
        elif pedido_id in ids_vistos:
            errores.append(
                f"{ruta}, fila {numero_fila} (pedido {pedido_id}), columna 'pedido_id': "
                f"identificador duplicado (ya aparece en la fila {ids_vistos[pedido_id]})"
            )
        else:
            ids_vistos[pedido_id] = numero_fila

        fecha_lote = (fila.get("fecha_lote") or "").strip()
        if not _validar_fecha(fecha_lote):
            errores.append(
                f"{ruta}, fila {numero_fila} (pedido {etiqueta}), columna 'fecha_lote': "
                f"debe ser una fecha valida en formato AAAA-MM-DD (se encontro {fecha_lote!r})"
            )
        else:
            fechas_vistas.add(fecha_lote)

        lote = (fila.get("lote") or "").strip()
        lotes_vistos.add(lote)

        zona = (fila.get("zona") or "").strip()
        if zona not in ZONAS_VALIDAS:
            errores.append(
                f"{ruta}, fila {numero_fila} (pedido {etiqueta}), columna 'zona': "
                f"debe ser 'centro' o 'periferia' (se encontro {zona!r})"
            )

        valores_ok = True
        for columna in COLUMNAS_NUMERICAS:
            texto = (fila.get(columna) or "").strip()
            try:
                numero = float(texto)
            except ValueError:
                errores.append(
                    f"{ruta}, fila {numero_fila} (pedido {etiqueta}), columna '{columna}': "
                    f"valor no numerico (se encontro {texto!r})"
                )
                valores_ok = False
                continue
            if numero != numero or numero in (float("inf"), float("-inf")):
                errores.append(
                    f"{ruta}, fila {numero_fila} (pedido {etiqueta}), columna '{columna}': "
                    f"debe ser un numero finito (se encontro {texto!r})"
                )
                valores_ok = False
            elif numero <= 0:
                errores.append(
                    f"{ruta}, fila {numero_fila} (pedido {etiqueta}), columna '{columna}': "
                    f"debe ser mayor que 0 (se encontro {texto!r})"
                )
                valores_ok = False

        if pedido_id and zona in ZONAS_VALIDAS and valores_ok:
            filas_validas.append(fila)

    if len(lotes_vistos) > 1:
        errores.append(
            f"{ruta}: debe contener un solo lote, se encontraron varios: {sorted(lotes_vistos)}"
        )
    elif lotes_vistos and next(iter(lotes_vistos)) not in lotes_permitidos:
        (lote_encontrado,) = lotes_vistos
        errores.append(
            f"{ruta}: la columna 'lote' debe ser {sorted(lotes_permitidos)} "
            f"(se encontro {lote_encontrado!r})"
        )

    if len(fechas_vistas) > 1:
        errores.append(
            f"{ruta}: debe tener una sola fecha_lote, se encontraron varias: {sorted(fechas_vistas)}"
        )

    return filas_validas


def validar(ruta_referencia=RUTA_REFERENCIA, ruta_actual=RUTA_ACTUAL):
    """Valida ambos archivos y devuelve (filas_referencia, filas_actual).
    Lanza DatosInvalidos (con todos los errores juntos) si alguno falla."""
    errores = []
    filas_referencia = validar_archivo(ruta_referencia, {"base"}, errores)
    filas_actual = validar_archivo(ruta_actual, {"control", "expansion"}, errores)
    if errores:
        raise DatosInvalidos(errores)
    return filas_referencia, filas_actual


def main():
    try:
        filas_referencia, filas_actual = validar()
    except DatosInvalidos as exc:
        print("ERROR: se encontraron datos invalidos; no se genera el informe.", file=sys.stderr)
        for mensaje in exc.errores:
            print(f"  - {mensaje}", file=sys.stderr)
        sys.exit(1)

    print(
        f"OK: {RUTA_REFERENCIA} ({len(filas_referencia)} pedidos validos) y "
        f"{RUTA_ACTUAL} ({len(filas_actual)} pedidos validos) pasaron la validacion."
    )


if __name__ == "__main__":
    main()
