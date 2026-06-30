# ============================================================
#  MÓDULO: limpiar_db.py
#  Limpia todos los datos de la base de datos para empezar
#  desde cero. Útil durante desarrollo y pruebas.
#
#  Ubicación : tests/limpiar_db.py
#  Ejecutar  : python3 -m tests.limpiar_db
#
#  ADVERTENCIA: Esta operación es irreversible.
#  Borra TODOS los registros de lecturas, alertas,
#  costos_diarios y reportes. Los dispositivos se conservan.
# ============================================================

import sys
from app.database.db_conexion import DatabaseManager


def limpiar_base_de_datos():
    SEP = "=" * 50

    print(SEP)
    print("  LIMPIEZA DE BASE DE DATOS")
    print("  Sistema de Monitoreo Energético")
    print(SEP)

    # ── Confirmación del usuario ───────────────────────────
    print("\n  ⚠  Esta acción borrará TODOS los datos:")
    print("     - Lecturas de consumo")
    print("     - Alertas registradas")
    print("     - Costos diarios")
    print("     - Reportes generados")
    print("     (Los dispositivos del catálogo se conservan)\n")

    confirmacion = input("  ¿Confirmas la limpieza? Escribe SI para continuar: ")
    if confirmacion.strip().upper() != "SI":
        print("\n  Operación cancelada. No se borró ningún dato.")
        sys.exit(0)

    # ── Limpieza ───────────────────────────────────────────
    try:
        with DatabaseManager() as db:

            # Consultamos cuántos registros hay antes de borrar
            db.cursor.execute("SELECT COUNT(*) AS total FROM lecturas") # type: ignore
            total_lecturas = db.cursor.fetchone()["total"] # type: ignore

            db.cursor.execute("SELECT COUNT(*) AS total FROM alertas") # type: ignore
            total_alertas = db.cursor.fetchone()["total"] # type: ignore

            db.cursor.execute("SELECT COUNT(*) AS total FROM costos_diarios") # type: ignore
            total_costos = db.cursor.fetchone()["total"] # type: ignore

            db.cursor.execute("SELECT COUNT(*) AS total FROM reportes") # type: ignore
            total_reportes = db.cursor.fetchone()["total"] # type: ignore

            print(f"\n  Registros encontrados:")
            print(f"    Lecturas      : {total_lecturas:,}")
            print(f"    Alertas       : {total_alertas:,}")
            print(f"    Costos diarios: {total_costos:,}")
            print(f"    Reportes      : {total_reportes:,}")
            print()

            # Desactivamos temporalmente las foreign keys para
            # poder borrar en cualquier orden sin errores de
            # integridad referencial
            db.cursor.execute("SET FOREIGN_KEY_CHECKS = 0") # type: ignore

            print("  Limpiando tablas...", end=" ", flush=True)
            db.cursor.execute("TRUNCATE TABLE alertas") # type: ignore
            db.cursor.execute("TRUNCATE TABLE costos_diarios") # type: ignore
            db.cursor.execute("TRUNCATE TABLE reportes") # type: ignore
            db.cursor.execute("TRUNCATE TABLE lecturas") # type: ignore

            # Reactivamos las foreign keys
            db.cursor.execute("SET FOREIGN_KEY_CHECKS = 1") # type: ignore
            print("listo")

            # Verificación final
            db.cursor.execute("SELECT COUNT(*) AS total FROM lecturas") # type: ignore
            restantes = db.cursor.fetchone()["total"] # type: ignore

        print(f"\n{SEP}")
        print("  RESULTADO")
        print(f"{SEP}")
        print(f"  Lecturas borradas      : {total_lecturas:,}")
        print(f"  Alertas borradas       : {total_alertas:,}")
        print(f"  Costos diarios borrados: {total_costos:,}")
        print(f"  Reportes borrados      : {total_reportes:,}")
        print(f"  Registros restantes    : {restantes}")
        print(f"\n  Base de datos limpia ✓")
        print(f"  Ejecuta db_poblador para cargar datos nuevos:")
        print(f"  py -m app.database.db_poblador")
        print(SEP)

    except ConnectionError as e:
        print(f"\n  [ERROR] {e}")
        print("  Verifica que MySQL esté corriendo.")
        sys.exit(1)
    except Exception as e:
        print(f"\n  [ERROR inesperado] {e}")
        sys.exit(1)


if __name__ == "__main__":
    limpiar_base_de_datos()