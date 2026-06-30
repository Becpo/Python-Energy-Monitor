# ============================================================
#  MÓDULO: db_poblador.py
#  Orquesta la carga inicial de datos simulados en MySQL.
#  Conecta la Fase 1 (generador) + Fase 2 (motor) + Fase 3 (DB).
#  Ejecutar UNA vez para poblar la base de datos:
#      python db_poblador.py
# ============================================================

import sys
from datetime import datetime

from app.services.generador            import generar_lecturas
from app.services.motor_analisis       import AnalizadorConsumo
from app.services.calculador_costos    import CalculadorCostos
from app.services.detector_sobrecargas import DetectorSobrecargas
from .db_conexion import DatabaseManager


def poblar_base_de_datos(dias: int = 30, intervalo_min: int = 15):
    """
    Pipeline completo de carga:
      1. Genera el DataFrame simulado
      2. Analiza y detecta alertas
      3. Inserta lecturas en lotes
      4. Inserta alertas detectadas
      5. Agrega costos diarios
      6. Guarda el reporte global
    """
    SEP = "=" * 55
    print(SEP)
    print("  POBLADOR DE BASE DE DATOS")
    print("  Sistema de Monitoreo Energético")
    print(SEP)

    # ── Paso 1: Generar datos ──────────────────────────────
    print(f"\n  [1/5] Generando {dias} dias de lecturas...")
    t0 = datetime.now()
    df = generar_lecturas(dias=dias, intervalo_minutos=intervalo_min)
    print(f"        {len(df):,} registros generados en "
          f"{(datetime.now()-t0).seconds}s")

    # ── Paso 2: Analizar ───────────────────────────────────
    print("\n  [2/5] Ejecutando motor de análisis...")
    analizador  = AnalizadorConsumo(df)
    calculador  = CalculadorCostos(df)
    detector    = DetectorSobrecargas(df)
    reporte     = analizador.generar_reporte()
    sostenidas  = detector.detectar_sobrecargas_sostenidas()
    print(f"        Reporte generado — "
          f"{reporte['total_sobrecargas'] if 'total_sobrecargas' in reporte else 0} "
          f"sobrecargas detectadas")

    # ── Paso 3–6: Insertar en MySQL ────────────────────────
    print("\n  [3/5] Conectando a MySQL e insertando datos...")
    try:
        with DatabaseManager() as db:

            # — Lecturas —
            print("        Insertando lecturas en lotes...", end=" ", flush=True)
            t0 = datetime.now()
            n = db.insertar_lecturas(df, batch_size=1000)
            print(f"{n:,} filas en {(datetime.now()-t0).seconds}s")

            # — Alertas —
            print("  [4/5] Insertando alertas...", end=" ", flush=True)
            alertas_insertadas = 0
            for evento in sostenidas:
                db.insertar_alerta(
                    dispositivo   = evento["dispositivo"],
                    tipo          = "SOSTENIDA",
                    potencia_pico = evento["pico_w"],
                    duracion_min  = evento["duracion_min"],
                    ts_inicio     = evento["inicio"],
                    ts_fin        = evento["fin"],
                )
                alertas_insertadas += 1

            # Inserta también los picos aislados
            picos = detector.detectar_picos()
            for _, pico in picos.iterrows():
                try:
                    db.insertar_alerta(
                        dispositivo   = pico["dispositivo"],
                        tipo          = "PICO",
                        potencia_pico = pico["potencia_w"],
                        duracion_min  = 0,
                        ts_inicio     = pico["timestamp"].to_pydatetime(),
                        ts_fin        = pico["timestamp"].to_pydatetime(),
                    )
                    alertas_insertadas += 1
                except Exception:
                    pass  # Picos con dispositivo desconocido: se omiten

            print(f"{alertas_insertadas} alertas registradas")

            # — Costos diarios —
            print("  [5/5] Agregando costos diarios...", end=" ", flush=True)
            n = db.insertar_costos_diarios(calculador)
            print(f"{n} registros de costo diario")

            # — Reporte global —
            rid = db.guardar_reporte(reporte)
            print(f"\n        Reporte global guardado con id={rid}")

            # — Verificación final —
            stats = db.estadisticas_globales()
            print(f"\n{SEP}")
            print("  VERIFICACIÓN FINAL")
            print(f"{SEP}")
            print(f"  Lecturas en DB      : {stats['total_lecturas']:,}")
            print(f"  Energía total       : {float(stats['total_kwh'] or 0):.3f} kWh")
            print(f"  Costo total         : ${float(stats['total_costo'] or 0):,.0f} COP")
            print(f"  Sobrecargas totales : {stats['total_sobrecargas'] or 0}")
            print(f"  Periodo             : {stats['desde']}  →  {stats['hasta']}")

    except ConnectionError as e:
        print(f"\n  [ERROR] {e}")
        print("\n  Asegúrate de:")
        print("  1. Tener MySQL corriendo")
        print("  2. Haber ejecutado: mysql -u root -p < schema.sql")
        print("  3. Configurar DB_PASSWORD en db_conexion.py o como variable de entorno")
        sys.exit(1)

    print(f"\n{SEP}")
    print("  Base de datos poblada exitosamente.")
    print(SEP)


if __name__ == "__main__":
    # Puedes cambiar los parámetros aquí
    poblar_base_de_datos(dias=30, intervalo_min=15)