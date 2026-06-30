# ============================================================
#  MÓDULO: probar_api.py
#  Prueba todos los endpoints de la API REST.
#  Requiere que run.py esté corriendo en otra terminal:
#      python run.py
#  Luego ejecutar:
#      python probar_api.py
# ============================================================

import requests
import json
from datetime import datetime

BASE = "http://127.0.0.1:5000"            # "http://localhost:5000"
SEP  = "─" * 52


def titulo(texto: str):
    print(f"\n{'='*52}")
    print(f"  {texto}")
    print(f"{'='*52}")


def probar(metodo: str, ruta: str, body: dict = None, # type: ignore
           descripcion: str = ""):
    """Ejecuta una petición y muestra el resultado formateado."""
    url = f"{BASE}{ruta}"
    print(f"\n  {metodo:<4} {ruta}")
    if descripcion:
        print(f"  → {descripcion}")

    try:
        if metodo == "GET":
            r = requests.get(url, timeout=10)
        elif metodo == "POST":
            r = requests.post(url, json=body, timeout=30)
        elif metodo == "PUT":
            r = requests.put(url, timeout=10)
        else:
            return

        data = r.json()
        estado = "✓" if data.get("status") == "success" else "✗"
        print(f"  {estado} HTTP {r.status_code} — {data.get('mensaje', '')}")

        # Muestra un extracto del data según el endpoint
        d = data.get("data", {})
        if isinstance(d, dict):
            for k, v in list(d.items())[:4]:
                if isinstance(v, list):
                    print(f"      {k}: [{len(v)} items]")
                elif isinstance(v, float):
                    print(f"      {k}: {v:,.2f}")
                elif v is not None:
                    print(f"      {k}: {v}")

    except requests.exceptions.ConnectionError:
        print("  ✗ No se pudo conectar. ¿Está corriendo run.py?")
    except Exception as e:
        print(f"  ✗ Error: {e}")

    print(f"  {SEP}")


# ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n  Probando API REST — {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"  Servidor objetivo: {BASE}")

    titulo("ENDPOINTS DE ESTADO Y SALUD")
    probar("GET",  "/api/health",
           descripcion="Verifica conexión con MySQL")

    titulo("ENDPOINTS DE CONSULTA")
    probar("GET",  "/api/resumen",
           descripcion="KPIs globales para el header")
    probar("GET",  "/api/dispositivos?dias=7",
           descripcion="Consumo por dispositivo últimos 7 días")
    probar("GET",  "/api/lecturas?horas=6",
           descripcion="Lecturas de las últimas 6 horas")
    probar("GET",  "/api/lecturas?horas=24&dispositivo=nevera",
           descripcion="Lecturas filtradas por dispositivo")
    probar("GET",  "/api/alertas",
           descripcion="Alertas activas sin resolver")
    probar("GET",  "/api/costos?dias=7",
           descripcion="Costos diarios por franja")
    probar("GET",  "/api/perfil-horario?dias=7",
           descripcion="Curva de carga promedio 0-23h")
    probar("GET",  "/api/consumo-diario?dias=14",
           descripcion="Energía por día (para barras apiladas)")

    titulo("TIEMPO REAL (sin escritura en DB)")
    probar("GET",  "/api/simulacion-tiempo-real",
           descripcion="Lectura instantánea de todos los dispositivos")

    titulo("ENDPOINTS DE ESCRITURA")
    probar("POST", "/api/generar-reporte",
           body={"dias": 3, "intervalo_min": 15},
           descripcion="Genera 3 días de datos nuevos y los persiste")

    titulo("RESUMEN FINAL")
    print("\n  Si todos los endpoints muestran ✓ la API está lista.")