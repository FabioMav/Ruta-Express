"""
test_validador.py
Pruebas con archivos chicos e independientes de los lotes reales de la
practica. Incluye un caso valido y varios casos invalidos que prueban
reglas distintas del validador.
"""
import csv
import os
import shutil
import tempfile
import unittest

import validador

COLUMNAS = ["pedido_id", "fecha_lote", "lote", "zona", "distancia_km", "entrega_min", "importe_bs"]


def fila(pedido_id="RE-0001", fecha_lote="2026-10-05", lote="base", zona="centro",
         distancia_km="2.5", entrega_min="20.0", importe_bs="50.0"):
    return {
        "pedido_id": pedido_id, "fecha_lote": fecha_lote, "lote": lote, "zona": zona,
        "distancia_km": distancia_km, "entrega_min": entrega_min, "importe_bs": importe_bs,
    }


def escribir_csv(ruta, filas, columnas=COLUMNAS):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columnas)
        w.writeheader()
        w.writerows(filas)


class BaseConArchivosTemporales(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.ruta_referencia = os.path.join(self.tmpdir, "referencia.csv")
        self.ruta_actual = os.path.join(self.tmpdir, "actual.csv")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class TestCasoValido(BaseConArchivosTemporales):
    def test_dos_archivos_validos_pasan_sin_errores(self):
        """1. Un caso valido: referencia (lote base) y actual (lote control)
        con datos correctos deben pasar sin ningun error."""
        escribir_csv(self.ruta_referencia, [
            fila("RE-0001", "2026-10-05", "base", "centro"),
            fila("RE-0002", "2026-10-05", "base", "periferia"),
        ])
        escribir_csv(self.ruta_actual, [
            fila("RE-0101", "2026-10-12", "control", "centro"),
            fila("RE-0102", "2026-10-12", "control", "periferia"),
        ])
        filas_ref, filas_act = validador.validar(self.ruta_referencia, self.ruta_actual)
        self.assertEqual(len(filas_ref), 2)
        self.assertEqual(len(filas_act), 2)


class TestRechazoDeValorNoPositivo(BaseConArchivosTemporales):
    def test_entrega_min_negativo_se_rechaza(self):
        """2. entrega_min negativo (el escenario 3 de la consigna: error
        de captura) debe rechazar el archivo completo."""
        escribir_csv(self.ruta_referencia, [fila("RE-0001", "2026-10-05", "base", "centro")])
        escribir_csv(self.ruta_actual, [
            fila("RE-0101", "2026-10-12", "control", "centro", entrega_min="-15.0"),
        ])
        with self.assertRaises(validador.DatosInvalidos) as ctx:
            validador.validar(self.ruta_referencia, self.ruta_actual)
        mensaje = "\n".join(ctx.exception.errores)
        self.assertIn("entrega_min", mensaje)
        self.assertIn("mayor que 0", mensaje)
        self.assertIn("RE-0101", mensaje)

    def test_distancia_km_en_cero_se_rechaza(self):
        """2b. El limite es estrictamente mayor que 0 (0 no es valido)."""
        escribir_csv(self.ruta_referencia, [fila("RE-0001", "2026-10-05", "base", "centro")])
        escribir_csv(self.ruta_actual, [
            fila("RE-0101", "2026-10-12", "control", "centro", distancia_km="0"),
        ])
        with self.assertRaises(validador.DatosInvalidos) as ctx:
            validador.validar(self.ruta_referencia, self.ruta_actual)
        self.assertIn("distancia_km", "\n".join(ctx.exception.errores))


class TestRechazoDeIdDuplicado(BaseConArchivosTemporales):
    def test_id_duplicado_dentro_del_mismo_archivo_se_rechaza(self):
        """3. Dos filas con el mismo pedido_id en un mismo archivo deben
        rechazarse, citando ambas filas."""
        escribir_csv(self.ruta_referencia, [fila("RE-0001", "2026-10-05", "base", "centro")])
        escribir_csv(self.ruta_actual, [
            fila("RE-0101", "2026-10-12", "control", "centro"),
            fila("RE-0101", "2026-10-12", "control", "periferia"),
        ])
        with self.assertRaises(validador.DatosInvalidos) as ctx:
            validador.validar(self.ruta_referencia, self.ruta_actual)
        mensaje = "\n".join(ctx.exception.errores)
        self.assertIn("identificador duplicado", mensaje)
        self.assertIn("fila 3", mensaje)


class TestRechazoDeZonaInvalida(BaseConArchivosTemporales):
    def test_zona_desconocida_se_rechaza(self):
        """4. zona fuera de {centro, periferia} debe rechazarse."""
        escribir_csv(self.ruta_referencia, [fila("RE-0001", "2026-10-05", "base", "centro")])
        escribir_csv(self.ruta_actual, [
            fila("RE-0101", "2026-10-12", "control", zona="norte"),
        ])
        with self.assertRaises(validador.DatosInvalidos) as ctx:
            validador.validar(self.ruta_referencia, self.ruta_actual)
        mensaje = "\n".join(ctx.exception.errores)
        self.assertIn("zona", mensaje)
        self.assertIn("'norte'", mensaje)


class TestRechazoDeFechaInvalida(BaseConArchivosTemporales):
    def test_fecha_con_formato_incorrecto_se_rechaza(self):
        """5. fecha_lote que no cumple AAAA-MM-DD debe rechazarse."""
        escribir_csv(self.ruta_referencia, [fila("RE-0001", "2026-10-05", "base", "centro")])
        escribir_csv(self.ruta_actual, [
            fila("RE-0101", "05/10/2026", "control", "centro"),
        ])
        with self.assertRaises(validador.DatosInvalidos) as ctx:
            validador.validar(self.ruta_referencia, self.ruta_actual)
        self.assertIn("fecha_lote", "\n".join(ctx.exception.errores))


class TestRechazoDeLoteIncorrecto(BaseConArchivosTemporales):
    def test_referencia_con_lote_distinto_de_base_se_rechaza(self):
        """6. referencia.csv debe ser siempre el lote 'base'."""
        escribir_csv(self.ruta_referencia, [fila("RE-0001", "2026-10-05", "control", "centro")])
        escribir_csv(self.ruta_actual, [fila("RE-0101", "2026-10-12", "control", "centro")])
        with self.assertRaises(validador.DatosInvalidos) as ctx:
            validador.validar(self.ruta_referencia, self.ruta_actual)
        self.assertIn("'base'", "\n".join(ctx.exception.errores))

    def test_actual_con_lote_base_se_rechaza(self):
        """6b. actual.csv debe ser 'control' o 'expansion', nunca 'base'."""
        escribir_csv(self.ruta_referencia, [fila("RE-0001", "2026-10-05", "base", "centro")])
        escribir_csv(self.ruta_actual, [fila("RE-0101", "2026-10-12", "base", "centro")])
        with self.assertRaises(validador.DatosInvalidos) as ctx:
            validador.validar(self.ruta_referencia, self.ruta_actual)
        mensaje = "\n".join(ctx.exception.errores)
        self.assertIn(self.ruta_actual, mensaje)
        self.assertIn("'control', 'expansion'", mensaje)


class TestRechazoDeMultiplesLotesOFechas(BaseConArchivosTemporales):
    def test_dos_lotes_distintos_en_un_mismo_archivo_se_rechaza(self):
        """7. Un archivo con mas de un valor de 'lote' mezclado debe
        rechazarse (el archivo actual debe contener un solo lote)."""
        escribir_csv(self.ruta_referencia, [fila("RE-0001", "2026-10-05", "base", "centro")])
        escribir_csv(self.ruta_actual, [
            fila("RE-0101", "2026-10-12", "control", "centro"),
            fila("RE-0102", "2026-10-19", "expansion", "periferia"),
        ])
        with self.assertRaises(validador.DatosInvalidos) as ctx:
            validador.validar(self.ruta_referencia, self.ruta_actual)
        mensaje = "\n".join(ctx.exception.errores)
        self.assertIn("un solo lote", mensaje)


class TestRechazoDeEstructura(BaseConArchivosTemporales):
    def test_archivo_sin_filas_se_rechaza(self):
        """8. Un archivo con solo el encabezado (sin filas de datos) debe
        rechazarse."""
        escribir_csv(self.ruta_referencia, [fila("RE-0001", "2026-10-05", "base", "centro")])
        escribir_csv(self.ruta_actual, [])
        with self.assertRaises(validador.DatosInvalidos) as ctx:
            validador.validar(self.ruta_referencia, self.ruta_actual)
        self.assertIn("no tiene ninguna fila", "\n".join(ctx.exception.errores))

    def test_falta_una_columna_obligatoria_se_rechaza(self):
        """9. Si falta una columna obligatoria en el encabezado, se
        rechaza antes de mirar ninguna fila."""
        escribir_csv(self.ruta_referencia, [fila("RE-0001", "2026-10-05", "base", "centro")])
        columnas_incompletas = [c for c in COLUMNAS if c != "zona"]
        escribir_csv(self.ruta_actual, [
            {k: v for k, v in fila("RE-0101", "2026-10-12", "control").items() if k != "zona"}
        ], columnas=columnas_incompletas)
        with self.assertRaises(validador.DatosInvalidos) as ctx:
            validador.validar(self.ruta_referencia, self.ruta_actual)
        self.assertIn("faltan columnas obligatorias", "\n".join(ctx.exception.errores))

    def test_archivo_inexistente_se_rechaza(self):
        """10. Un archivo que no existe debe rechazarse con un mensaje claro."""
        escribir_csv(self.ruta_referencia, [fila("RE-0001", "2026-10-05", "base", "centro")])
        ruta_inexistente = os.path.join(self.tmpdir, "no_existe.csv")
        with self.assertRaises(validador.DatosInvalidos) as ctx:
            validador.validar(self.ruta_referencia, ruta_inexistente)
        self.assertIn("no se encontro el archivo", "\n".join(ctx.exception.errores))


if __name__ == "__main__":
    unittest.main()
