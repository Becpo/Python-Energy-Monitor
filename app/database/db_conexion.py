# ============================================================
#  MÓDULO: db_conexion.py
#  Gestiona la conexión a MySQL y expone métodos para
#  insertar y consultar datos del sistema energético.
#
#  Patrón usado: Repository
#  → La clase DatabaseManager centraliza TODO el acceso
#    a la base de datos. Ningún otro módulo escribe SQL.
# ============================================================

import mysql.connector
from mysql.connector import Error
from mysql.connector.cursor_cext import CMySQLCursor
from datetime import datetime
import json
import os
from dotenv import load_dotenv
from typing import Optional

# Carga las variables del archivo .env al entorno de Python.
# A partir de aquí, os.getenv() las encuentra como si fueran
# variables del sistema operativo — sin tocar el código.
load_dotenv()

# ──────────────────────────────────────────────────────────
# Configuración de conexión
# Todas las credenciales vienen del archivo .env
# En producción NUNCA hardcodees contraseñas aquí
# ──────────────────────────────────────────────────────────
DB_CONFIG = {
    "host":       os.getenv("DB_HOST"),
    "port":       os.getenv("DB_PORT"),
    "user":       os.getenv("DB_USER"),
    "password":   os.getenv("DB_PASSWORD"),
    "database":   os.getenv("DB_NAME"),
    "charset":    "utf8mb4",
    "autocommit": False,
}


class DatabaseManager:
    """
    Repositorio central de acceso a MySQL.

    Uso básico:
        with DatabaseManager() as db:
            db.insertar_lecturas(df)
            datos = db.obtener_lecturas_recientes(horas=24)
    """
    cursor: Optional[CMySQLCursor] = None

    def __init__(self, config: dict | None = None):
        self.config     = config or DB_CONFIG
        self.connection = None
        self.cursor     = None

    # ── Gestión de conexión (context manager) ──────────────
    def __enter__(self):
        self.conectar()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Si hubo excepción, hace rollback; si no, commit
        if exc_type:
            if self.connection:
                self.connection.rollback()
        else:
            if self.connection:
                self.connection.commit()
        self.desconectar()
        # Retorna False para que las excepciones se propaguen
        return False

    def conectar(self):
        """Abre la conexión y el cursor."""
        try:
            self.connection = mysql.connector.connect(**self.config)
            self.cursor     = self.connection.cursor(dictionary=True) # type: ignore
            print(f"  [DB] Conectado a MySQL en {self.config['host']}:{self.config['port']}")
        except Error as e:
            raise ConnectionError(f"No se pudo conectar a MySQL: {e}")

    def desconectar(self):
        """Cierra cursor y conexión limpiamente."""
        if self.cursor:
            self.cursor.close()
        if self.connection and self.connection.is_connected():
            self.connection.close()
            print("  [DB] Conexión cerrada")

    # ── ESCRITURA ──────────────────────────────────────────

    def _sincronizar_dispositivos(self, df) -> dict:
        """
        Garantiza que todos los dispositivos del DataFrame existan
        en la tabla `dispositivos`. Si la tabla está vacía (como ocurre
        tras un flask db upgrade en instalación nueva), los inserta
        automáticamente usando los datos del DataFrame.
        Retorna el mapa nombre → id.
        """
        from app.services.generador import DISPOSITIVOS as CONFIG_DISPOSITIVOS

        # Insertar los que falten usando los metadatos del generador
        for nombre, config in CONFIG_DISPOSITIVOS.items():
            assert self.cursor is not None
            self.cursor.execute(
                "SELECT id FROM dispositivos WHERE nombre = %s", (nombre,)
            )
            if not self.cursor.fetchone():
                self.cursor.execute(
                    """INSERT INTO dispositivos
                           (nombre, potencia_base, limite_seguro, activo)
                       VALUES (%s, %s, %s, 1)""",
                    (nombre, config["potencia_base"], config["limite_seguro"]),
                )

        # Devolver el mapa actualizado
        assert self.cursor is not None
        self.cursor.execute("SELECT id, nombre FROM dispositivos")
        return {row["nombre"]: row["id"] for row in self.cursor.fetchall()} # type: ignore

    def insertar_lecturas(self, df, batch_size: int = 1000) -> int:
        """
        Inserta un DataFrame de lecturas en la tabla lecturas.

        Usa INSERT en lotes (batches) para eficiencia:
        insertar 17.000 filas de una en una tomaría ~17 segundos,
        en lotes de 1000 toma ~0.5 segundos.

        Retorna el número de filas insertadas.
        """
        # Sincroniza dispositivos antes de insertar lecturas.
        # Si la tabla está vacía (instalación nueva con flask db upgrade),
        # los registra automáticamente desde la configuración del generador.
        mapa = self._sincronizar_dispositivos(df)

        sql = """
            INSERT INTO lecturas
                (dispositivo_id, timestamp, potencia_w,
                 energia_kwh, costo_cop, es_sobrecarga)
            VALUES
                (%s, %s, %s, %s, %s, %s)
        """

        total_insertadas = 0
        lote             = []

        for _, fila in df.iterrows():
            disp_id = mapa.get(fila["dispositivo"])
            if disp_id is None:
                continue  # Dispositivo no registrado: se omite

            lote.append((
                disp_id,
                fila["timestamp"].to_pydatetime(),
                float(fila["potencia_w"]),
                float(fila["energia_kwh"]),
                float(fila["costo_cop"]),
                bool(fila["es_sobrecarga"]),
            ))

            # Cuando el lote está lleno, ejecutamos e insertamos
            if len(lote) >= batch_size:
                self.cursor.executemany(sql, lote) # type: ignore
                total_insertadas += len(lote)
                lote = []

        # Insertar el lote final (puede ser menor que batch_size)
        if lote:
            self.cursor.executemany(sql, lote) # type: ignore
            total_insertadas += len(lote)

        return total_insertadas

    def insertar_alerta(self, dispositivo: str, tipo: str,
                        potencia_pico: float, duracion_min: int,
                        ts_inicio: datetime, ts_fin: datetime) -> int:
        """Registra un evento de alerta. Retorna el id generado."""
        assert self.cursor is not None
        self.cursor.execute(
            "SELECT id FROM dispositivos WHERE nombre = %s", (dispositivo,)
        )
        row = self.cursor.fetchone() # type: ignore
        if not row:
            raise ValueError(f"Dispositivo '{dispositivo}' no encontrado")

        self.cursor.execute("""
            INSERT INTO alertas
                (dispositivo_id, tipo, potencia_pico,
                 duracion_min, timestamp_inicio, timestamp_fin, resuelta)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (row["id"], tipo, potencia_pico, duracion_min, ts_inicio, ts_fin, 0)) # type: ignore

        return self.cursor.lastrowid # type: ignore

    def insertar_costos_diarios(self, calculador) -> int:
        """
        Agrega costos diarios desde el CalculadorCostos.
        Usa INSERT ... ON DUPLICATE KEY UPDATE para ser idempotente
        (si ya existe el día, actualiza en lugar de duplicar).
        """
        df = calculador.df.copy()
        df["fecha"] = df["timestamp"].dt.date

        assert self.cursor is not None
        self.cursor.execute("SELECT id, nombre FROM dispositivos")
        mapa = {r["nombre"]: r["id"] for r in self.cursor.fetchall()} # type: ignore

        sql = """
            INSERT INTO costos_diarios
                (dispositivo_id, fecha, energia_kwh, costo_cop,
                 franja_valle, franja_normal, franja_punta)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                energia_kwh   = VALUES(energia_kwh),
                costo_cop     = VALUES(costo_cop),
                franja_valle  = VALUES(franja_valle),
                franja_normal = VALUES(franja_normal),
                franja_punta  = VALUES(franja_punta)
        """

        total = 0
        for (fecha, disp), grupo in df.groupby(["fecha", "dispositivo"]):
            disp_id = mapa.get(disp)
            if not disp_id:
                continue

            energia    = float(grupo["energia_kwh"].sum())
            costo      = float(grupo["costo_real_cop"].sum())
            fr_valle   = float(grupo[grupo["franja"] == "valle"]["costo_real_cop"].sum())
            fr_normal  = float(grupo[grupo["franja"] == "normal"]["costo_real_cop"].sum())
            fr_punta   = float(grupo[grupo["franja"] == "punta"]["costo_real_cop"].sum())

            self.cursor.execute(sql, ( # type: ignore
                disp_id, fecha, energia, costo,
                fr_valle, fr_normal, fr_punta
            ))
            total += 1

        return total

    def guardar_reporte(self, reporte: dict) -> int:
        """Persiste el reporte generado por AnalizadorConsumo."""
        assert self.cursor is not None
        self.cursor.execute("""
            INSERT INTO reportes
                (periodo_inicio, periodo_fin, total_lecturas,
                 total_energia_kwh, total_costo_cop,
                 proyeccion_mensual, total_sobrecargas,
                 dispositivo_top, datos_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            reporte["periodo_inicio"],
            reporte["periodo_fin"],
            reporte["total_lecturas"],
            reporte["total_energia_kwh"],
            reporte["total_costo_cop"],
            reporte["proyeccion_mensual"],
            reporte["sobrecargas"]["total_picos"],
            reporte["dispositivo_mas_costoso"],
            json.dumps(reporte, ensure_ascii=False, default=str),
        ))

        return self.cursor.lastrowid # type: ignore

    # ── CONSULTAS ──────────────────────────────────────────

    def obtener_lecturas_recientes(self, horas: int = 24) -> list[dict]:
        """Últimas N horas de lecturas con nombre de dispositivo."""
        assert self.cursor is not None
        self.cursor.execute("""
            SELECT
                l.timestamp,
                d.nombre      AS dispositivo,
                l.potencia_w,
                l.energia_kwh,
                l.costo_cop,
                l.es_sobrecarga
            FROM lecturas l
            JOIN dispositivos d ON d.id = l.dispositivo_id
            WHERE l.timestamp >= NOW() - INTERVAL %s HOUR
            ORDER BY l.timestamp DESC
        """, (horas,))
        return self.cursor.fetchall() # type: ignore

    def obtener_consumo_por_dispositivo(self, dias: int = 7) -> list[dict]:
        """Energía y costo total por dispositivo en los últimos N días."""
        assert self.cursor is not None
        self.cursor.execute("""
            SELECT
                d.nombre                    AS dispositivo,
                SUM(l.energia_kwh)          AS total_kwh,
                SUM(l.costo_cop)            AS total_cop,
                COUNT(*)                    AS lecturas,
                SUM(l.es_sobrecarga)        AS sobrecargas
            FROM lecturas l
            JOIN dispositivos d ON d.id = l.dispositivo_id
            WHERE l.timestamp >= NOW() - INTERVAL %s DAY
            GROUP BY d.id, d.nombre
            ORDER BY total_kwh DESC
        """, (dias,))
        return self.cursor.fetchall() # type: ignore

    def obtener_alertas_activas(self) -> list[dict]:
        """Alertas no resueltas, más recientes primero."""
        assert self.cursor is not None
        self.cursor.execute("""
            SELECT
                a.id,
                d.nombre            AS dispositivo,
                a.tipo,
                a.potencia_pico,
                a.duracion_min,
                a.timestamp_inicio,
                a.timestamp_fin
            FROM alertas a
            JOIN dispositivos d ON d.id = a.dispositivo_id
            WHERE a.resuelta = 0
            ORDER BY a.timestamp_inicio DESC
        """)
        return self.cursor.fetchall() # type: ignore

    def obtener_costos_diarios_por_rango(
        self, fecha_inicio: str, fecha_fin: str
    ) -> list[dict]:
        """Costos diarios entre dos fechas (formato YYYY-MM-DD)."""
        assert self.cursor is not None
        self.cursor.execute("""
            SELECT
                c.fecha,
                d.nombre        AS dispositivo,
                c.energia_kwh,
                c.costo_cop,
                c.franja_valle,
                c.franja_normal,
                c.franja_punta
            FROM costos_diarios c
            JOIN dispositivos d ON d.id = c.dispositivo_id
            WHERE c.fecha BETWEEN %s AND %s
            ORDER BY c.fecha, d.nombre
        """, (fecha_inicio, fecha_fin))
        return self.cursor.fetchall() # type: ignore

    def obtener_ultimo_reporte(self) -> dict | None:
        """Retorna el reporte más reciente."""
        assert self.cursor is not None
        self.cursor.execute("""
            SELECT *
            FROM reportes
            ORDER BY fecha_generacion DESC
            LIMIT 1
        """)
        return self.cursor.fetchone() # type: ignore

    def estadisticas_globales(self) -> dict:
        """Resumen rápido para el header del dashboard."""
        assert self.cursor is not None
        self.cursor.execute("""
            SELECT
                COUNT(*)                AS total_lecturas,
                SUM(energia_kwh)        AS total_kwh,
                SUM(costo_cop)          AS total_costo,
                SUM(es_sobrecarga)      AS total_sobrecargas,
                MIN(timestamp)          AS desde,
                MAX(timestamp)          AS hasta
            FROM lecturas
        """)
        return self.cursor.fetchone() # type: ignore


# ──────────────────────────────────────────────────────────
# Prueba rápida — python db_conexion.py
# (Requiere MySQL corriendo con el schema.sql ejecutado)
# ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== Prueba: DatabaseManager ===\n")
    print("  Este archivo requiere MySQL en ejecución.")
    print("  Pasos previos:")
    print("  1. mysql -u root -p < energy_monitor.sql")
    print("  2. Configura DB_PASSWORD en DB_CONFIG o como variable de entorno")
    print("  3. Vuelve a ejecutar este script\n")

    try:
        with DatabaseManager() as db:
            stats = db.estadisticas_globales()
            print(f"  Conexión exitosa")
            print(f"  Lecturas en DB : {stats['total_lecturas'] or 0:,}")
            print(f"  Energía total  : {stats['total_kwh'] or 0:.3f} kWh")

    except ConnectionError as e:
        print(f"  [ERROR] {e}")
        print("\n  Verifica que MySQL esté corriendo y la contraseña sea correcta.")