import unittest
from datetime import datetime
from app.database.db_conexion import DatabaseManager


class AlertasDbTests(unittest.TestCase):
    def test_insertar_alerta_debe_aceptar_resuelta_por_defecto(self):
        with DatabaseManager() as db:
            
            assert db.cursor is not None

            db.cursor.execute("SELECT id FROM dispositivos WHERE nombre = %s", ("nevera",))
            row = db.cursor.fetchone()
            self.assertIsNotNone(row)

            ts_inicio = datetime(2026, 1, 1, 0, 0, 0)
            ts_fin = datetime(2026, 1, 1, 0, 15, 0)

            alerta_id = db.insertar_alerta(
                dispositivo="nevera",
                tipo="PICO",
                potencia_pico=501.0,
                duracion_min=15,
                ts_inicio=ts_inicio,
                ts_fin=ts_fin,
            )

            self.assertGreater(alerta_id, 0)
            db.cursor.execute("DELETE FROM alertas WHERE id = %s", (alerta_id,))


if __name__ == "__main__":
    unittest.main()
