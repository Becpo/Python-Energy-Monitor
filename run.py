# ============================================================
#  Punto de entrada — Sistema de Monitoreo Energético
#  Ejecutar: python run.py
#  Servidor: http://localhost:5000
# ============================================================

import os
import socket

from app import create_app

app = create_app()


def obtener_puerto_disponible(port: int, host: str = "127.0.0.1") -> int:
    """Devuelve un puerto libre; si el solicitado está ocupado, prueba con el siguiente."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return port
        except OSError:
            for puerto_siguiente in range(port + 1, port + 20):
                try:
                    sock.bind((host, puerto_siguiente))
                    return puerto_siguiente
                except OSError:
                    continue
            raise RuntimeError(f"No hay puertos libres disponibles entre {port} y {port + 19}")


if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    puerto_solicitado = int(os.getenv("PORT", "5000"))
    puerto_final = obtener_puerto_disponible(puerto_solicitado, host)

    print("=" * 50)
    print("  API REST — Sistema de Monitoreo Energético")
    print("=" * 50)
    print(f"  Servidor : http://{host}:{puerto_final}")
    print("  Endpoints:")
    print("    GET  /api/health")
    print("    GET  /api/resumen")
    print("    GET  /api/dispositivos")
    print("    GET  /api/lecturas?horas=24")
    print("    GET  /api/alertas")
    print("    GET  /api/costos?dias=7")
    print("    GET  /api/perfil-horario")
    print("    GET  /api/consumo-diario?dias=14")
    print("    GET  /api/simulacion-tiempo-real")
    print("    POST /api/generar-reporte")
    print("    PUT  /api/alertas/<id>/resolver")
    print("=" * 50)
    if puerto_final != puerto_solicitado:
        print(f"  [WARN] Puerto {puerto_solicitado} ocupado. Usando {puerto_final}.")
    app.run(
        host=host,
        port=puerto_final,
        debug=True,   #Colocar en False si falla
        use_reloader=True,  # Colocar en False si falla la recarga automática
        threaded=True,
    )