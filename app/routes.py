# ============================================================
#  Rutas y endpoints — Sistema de Monitoreo Energético
#
#  Endpoints disponibles:
#    GET  /api/health
#    GET  /api/resumen
#    GET  /api/dispositivos
#    GET  /api/lecturas?horas=24
#    GET  /api/alertas
#    GET  /api/costos?dias=7
#    GET  /api/perfil-horario
#    GET  /api/consumo-diario?dias=7
#    POST /api/generar-reporte
#    PUT  /api/alertas/<id>/resolver
#    GET  /api/simulacion-tiempo-real
# ============================================================

from flask import Blueprint, jsonify, request, render_template
from datetime import datetime, timedelta
import traceback

from app.database.db_conexion          import DatabaseManager
from app.services.generador            import generar_lecturas, DISPOSITIVOS
from app.services.motor_analisis       import AnalizadorConsumo
from app.services.calculador_costos    import CalculadorCostos
from app.services.detector_sobrecargas import DetectorSobrecargas

main = Blueprint("main", __name__, template_folder="../templates")

# Template para la ruta raíz (dashboard)
@main.route("/")
def index():
    return render_template("dashboard.html")

# ──────────────────────────────────────────────────────────
# UTILIDADES
# ──────────────────────────────────────────────────────────

def respuesta_ok(data, mensaje: str = "OK") -> tuple:
    """Envuelve datos en la estructura de respuesta estándar."""
    return jsonify({
        "status":    "success",
        "mensaje":   mensaje,
        "timestamp": datetime.now().isoformat(),
        "data":      data,
    }), 200


def respuesta_error(mensaje: str, codigo: int = 500) -> tuple:
    """Respuesta de error con formato consistente."""
    return jsonify({
        "status":    "error",
        "mensaje":   mensaje,
        "timestamp": datetime.now().isoformat(),
        "data":      None,
    }), codigo


def filas_a_lista(filas: list) -> list:
    """Convierte una lista de dicts de MySQL a JSON-safe."""
    import decimal
    resultado = []
    for fila in filas:
        fila_limpia = {}
        for k, v in fila.items():
            if isinstance(v, datetime):
                fila_limpia[k] = v.isoformat()
            elif isinstance(v, decimal.Decimal):
                fila_limpia[k] = float(v)
            elif isinstance(v, bytes):
                fila_limpia[k] = v.decode("utf-8")
            else:
                fila_limpia[k] = v
        resultado.append(fila_limpia)
    return resultado


# ──────────────────────────────────────────────────────────
# MANEJADORES GLOBALES DE ERROR
# ──────────────────────────────────────────────────────────

def manejar_error_global(e):
    """Captura cualquier excepción no controlada y devuelve JSON."""
    import logging
    logging.error(traceback.format_exc())
    return respuesta_error(f"Error interno: {str(e)}", 500)


def no_encontrado(e):
    return respuesta_error("Endpoint no encontrado", 404)


# ╔══════════════════════════════════════════════════════════╗
# ║  ENDPOINTS DE CONSULTA (GET)                             ║
# ╚══════════════════════════════════════════════════════════╝

# ── GET /api/health ────────────────────────────────────────
@main.route("/api/health", methods=["GET"])
def health_check():
    """
    Verifica que la API y la base de datos estén operativas.
    El dashboard lo llama cada 30s para mostrar el indicador
    de estado en el header.
    """
    try:
        with DatabaseManager() as db:
            stats = db.estadisticas_globales()
        return respuesta_ok({
            "api":      "online",
            "database": "online",
            "lecturas": int(stats["total_lecturas"] or 0),
        }, "Sistema operativo")
    except Exception as e:
        return respuesta_error(f"Base de datos no disponible: {e}", 503)


# ── GET /api/resumen ───────────────────────────────────────
@main.route("/api/resumen", methods=["GET"])
def get_resumen():
    """
    Resumen global para el header del dashboard:
    total kWh, costo, sobrecargas y proyección mensual.
    """
    try:
        with DatabaseManager() as db:
            stats   = db.estadisticas_globales()
            reporte = db.obtener_ultimo_reporte()

        import json
        datos_reporte = {}
        if reporte and reporte.get("datos_json"):
            raw = reporte["datos_json"]
            if isinstance(raw, str):
                datos_reporte = json.loads(raw)
            elif isinstance(raw, dict):
                datos_reporte = raw

        return respuesta_ok({
            "total_lecturas":         int(stats["total_lecturas"] or 0),
            "total_kwh":              float(stats["total_kwh"] or 0),
            "total_costo_cop":        float(stats["total_costo"] or 0),
            "total_sobrecargas":      int(stats["total_sobrecargas"] or 0),
            "desde":                  stats["desde"].isoformat() if stats["desde"] else None,
            "hasta":                  stats["hasta"].isoformat() if stats["hasta"] else None,
            "proyeccion_mensual":     datos_reporte.get("proyeccion_mensual", 0),
            "top_consumidores":       datos_reporte.get("top_consumidores", []),
            "riesgo_por_dispositivo": datos_reporte.get("riesgo_por_dispositivo", {}),
        })
    except Exception as e:
        return respuesta_error(str(e))


# ── GET /api/dispositivos ──────────────────────────────────
@main.route("/api/dispositivos", methods=["GET"])
def get_dispositivos():
    """
    Lista todos los dispositivos con su consumo
    en los últimos N días (parámetro ?dias=7).
    """
    dias = request.args.get("dias", 7, type=int)
    try:
        with DatabaseManager() as db:
            datos = db.obtener_consumo_por_dispositivo(dias=dias)
        return respuesta_ok(filas_a_lista(datos))
    except Exception as e:
        return respuesta_error(str(e))


# ── GET /api/lecturas ──────────────────────────────────────
@main.route("/api/lecturas", methods=["GET"])
def get_lecturas():
    """
    Últimas N horas de lecturas.
    Parámetros opcionales:
      ?horas=24           (default: 24)
      ?dispositivo=nevera (filtra por dispositivo)
    """
    horas       = request.args.get("horas", 24, type=int)
    dispositivo = request.args.get("dispositivo", None)

    try:
        with DatabaseManager() as db:
            datos = db.obtener_lecturas_recientes(horas=horas)

        if dispositivo:
            datos = [d for d in datos if d["dispositivo"] == dispositivo]

        return respuesta_ok({
            "total":    len(datos),
            "horas":    horas,
            "lecturas": filas_a_lista(datos),
        })
    except Exception as e:
        return respuesta_error(str(e))


# ── GET /api/alertas ───────────────────────────────────────
@main.route("/api/alertas", methods=["GET"])
def get_alertas():
    """
    Alertas activas (no resueltas).
    Parámetro opcional: ?todas=1 para incluir resueltas.
    """
    try:
        with DatabaseManager() as db:
            datos = db.obtener_alertas_activas()
        return respuesta_ok({
            "total":   len(datos),
            "alertas": filas_a_lista(datos),
        })
    except Exception as e:
        return respuesta_error(str(e))


# ── GET /api/costos ────────────────────────────────────────
@main.route("/api/costos", methods=["GET"])
def get_costos():
    """
    Costos diarios por dispositivo y franja horaria.
    Parámetro: ?dias=7 (últimos N días)
    """
    dias         = request.args.get("dias", 7, type=int)
    fecha_fin    = datetime.now().date()
    fecha_inicio = (datetime.now() - timedelta(days=dias)).date()

    try:
        with DatabaseManager() as db:
            datos = db.obtener_costos_diarios_por_rango(
                str(fecha_inicio), str(fecha_fin)
            )
        return respuesta_ok({
            "periodo_inicio": str(fecha_inicio),
            "periodo_fin":    str(fecha_fin),
            "costos":         filas_a_lista(datos),
        })
    except Exception as e:
        return respuesta_error(str(e))


# ── GET /api/perfil-horario ────────────────────────────────
@main.route("/api/perfil-horario", methods=["GET"])
def get_perfil_horario():
    """
    Consumo promedio por hora del día (0-23).
    Usado por la gráfica de curva de carga en el dashboard.
    Parámetro: ?dias=7
    """
    dias = request.args.get("dias", 7, type=int)
    try:
        with DatabaseManager() as db:
            datos = db.obtener_lecturas_recientes(horas=dias * 24)

        if not datos:
            return respuesta_ok({"perfil": []})

        import pandas as pd
        df = pd.DataFrame(filas_a_lista(datos))
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        analizador = AnalizadorConsumo(df)
        perfil_df  = analizador.perfil_por_hora()

        return respuesta_ok({
            "perfil": perfil_df.to_dict(orient="records")
        })
    except Exception as e:
        return respuesta_error(str(e))


# ── GET /api/consumo-diario ────────────────────────────────
@main.route("/api/consumo-diario", methods=["GET"])
def get_consumo_diario():
    """
    Energía total por día y dispositivo.
    Usado por la gráfica de barras apiladas.
    Parámetro: ?dias=14
    """
    dias = request.args.get("dias", 14, type=int)
    try:
        with DatabaseManager() as db:
            datos = db.obtener_lecturas_recientes(horas=dias * 24)

        if not datos:
            return respuesta_ok({"consumo": []})

        import pandas as pd
        df = pd.DataFrame(filas_a_lista(datos))
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        analizador  = AnalizadorConsumo(df)
        consumo_df  = analizador.consumo_diario()
        consumo_df["fecha"] = consumo_df["fecha"].astype(str)

        return respuesta_ok({
            "consumo": consumo_df.to_dict(orient="records")
        })
    except Exception as e:
        return respuesta_error(str(e))


# ╔══════════════════════════════════════════════════════════╗
# ║  ENDPOINTS DE ESCRITURA (POST / PUT)                     ║
# ╚══════════════════════════════════════════════════════════╝

# ── POST /api/generar-reporte ──────────────────────────────
@main.route("/api/generar-reporte", methods=["POST"])
def post_generar_reporte():
    """
    Genera un nuevo ciclo de simulación:
      1. Genera datos frescos
      2. Analiza y detecta alertas
      3. Persiste todo en MySQL
      4. Retorna el reporte generado

    Body JSON opcional:
      { "dias": 30, "intervalo_min": 15 }
    """
    body      = request.get_json(silent=True) or {}
    dias      = body.get("dias", 7)
    intervalo = body.get("intervalo_min", 15)

    try:
        df         = generar_lecturas(dias=dias, intervalo_minutos=intervalo)
        analizador = AnalizadorConsumo(df)
        calculador = CalculadorCostos(df)
        detector   = DetectorSobrecargas(df)
        reporte    = analizador.generar_reporte()
        sostenidas = detector.detectar_sobrecargas_sostenidas()

        with DatabaseManager() as db:
            n_lecturas = db.insertar_lecturas(df, batch_size=1000)
            for evento in sostenidas:
                db.insertar_alerta(
                    dispositivo   = evento["dispositivo"],
                    tipo          = "SOSTENIDA",
                    potencia_pico = evento["pico_w"],
                    duracion_min  = evento["duracion_min"],
                    ts_inicio     = evento["inicio"],
                    ts_fin        = evento["fin"],
                )
            db.insertar_costos_diarios(calculador)
            rid = db.guardar_reporte(reporte)

        return respuesta_ok({
            "reporte_id":      rid,
            "lecturas_nuevas": n_lecturas,
            "resumen":         reporte,
        }, f"Reporte generado: {n_lecturas:,} lecturas insertadas")

    except Exception as e:
        return respuesta_error(str(e))


# ── PUT /api/alertas/<id>/resolver ─────────────────────────
@main.route("/api/alertas/<int:alerta_id>/resolver", methods=["PUT"])
def put_resolver_alerta(alerta_id: int):
    """
    Marca una alerta como resuelta.
    El dashboard llama este endpoint cuando el usuario
    hace clic en 'Resolver' en la tabla de alertas.
    """
    try:
        with DatabaseManager() as db:
            db.cursor.execute( # type: ignore
                "UPDATE alertas SET resuelta = 1 WHERE id = %s",
                (alerta_id,)
            )
            if db.cursor.rowcount == 0: # type: ignore
                return respuesta_error(
                    f"Alerta {alerta_id} no encontrada", 404
                )

        return respuesta_ok(
            {"alerta_id": alerta_id, "resuelta": True},
            f"Alerta {alerta_id} marcada como resuelta"
        )
    except Exception as e:
        return respuesta_error(str(e))


# ── GET /api/simulacion-tiempo-real ───────────────────────
@main.route("/api/simulacion-tiempo-real", methods=["GET"])
def get_simulacion_tiempo_real():
    """
    Genera UNA lectura instantánea simulada para cada dispositivo.
    El dashboard lo llama cada 5 segundos para el panel
    'Consumo en tiempo real' sin escribir en la DB.
    """
    import numpy as np

    hora_actual = datetime.now().hour
    lecturas    = []

    for nombre, config in DISPOSITIVOS.items():
        factor   = config["perfil"][hora_actual]
        ruido    = np.random.normal(0, 0.05)
        factor   = max(0.0, min(1.2, factor + ruido))
        potencia = round(config["potencia_base"] * factor, 1)

        lecturas.append({
            "dispositivo": nombre,
            "potencia_w":  potencia,
            "limite_w":    config["limite_seguro"],
            "porcentaje":  round(potencia / config["limite_seguro"] * 100, 1),
            "estado":      "SOBRECARGA"  if potencia > config["limite_seguro"]
                           else "ADVERTENCIA" if potencia > config["limite_seguro"] * 0.85
                           else "NORMAL",
            "timestamp":   datetime.now().isoformat(),
        })

    total_w = sum(l["potencia_w"] for l in lecturas)

    return respuesta_ok({
        "lecturas":  lecturas,
        "total_w":   round(total_w, 1),
        "total_kw":  round(total_w / 1000, 3),
        "timestamp": datetime.now().isoformat(),
    })