# ============================================================
#  FASE 1 — Generador de Datasets Simulados
#  Sistema de Monitoreo Energético
# ============================================================

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import random

# ──────────────────────────────────────────────────────────
# 1. DEFINICIÓN DE DISPOSITIVOS
#    Cada dispositivo tiene:
#      - potencia_base : consumo en Watts cuando está encendido
#      - limite_seguro : límite máximo antes de considerar sobrecarga
#      - perfil        : lista de 24 valores (0.0 a 1.0) que indica
#                        qué tan activo está cada hora del día
# ──────────────────────────────────────────────────────────
DISPOSITIVOS = {
    "nevera": {
        "potencia_base": 450,       # Watts
        "limite_seguro": 500,       # Watts — umbral de sobrecarga
        "perfil": [                 # Hora 0 a hora 23
            0.6, 0.6, 0.6, 0.6, 0.6, 0.7,   # 00–05 madrugada
            0.7, 0.8, 0.9, 0.8, 0.8, 0.9,   # 06–11 mañana
            1.0, 1.0, 0.9, 0.9, 0.9, 1.0,   # 12–17 tarde (más calor)
            1.0, 0.9, 0.8, 0.7, 0.6, 0.6,   # 18–23 noche
        ],
    },
    "ventilador": {
        "potencia_base": 60,
        "limite_seguro": 80,
        "perfil": [
            1.0, 1.0, 1.0, 1.0, 1.0, 1.0,   # madrugada: apagado
            1.0, 1.0, 0.3, 0.6, 0.9, 0.0,   # mañana: apagado
            0.0, 0.0, 0.0, 0.0, 0.2, 0.1,   # tarde
            0.2, 0.4, 0.3, 0.2, 0.1, 1.0,   # noche: disminuye
        ],
    },
    "iluminacion": {
        "potencia_base": 200,
        "limite_seguro": 300,
        "perfil": [
            0.1, 0.1, 0.1, 0.1, 0.1, 0.3,   # madrugada: mínimo
            0.6, 0.7, 0.5, 0.4, 0.4, 0.4,   # mañana
            0.3, 0.3, 0.3, 0.4, 0.5, 0.8,   # tarde
            1.0, 1.0, 0.9, 0.7, 0.0, 0.0,   # noche: máximo uso
        ],
    },
    "lavadora": {
        "potencia_base": 500,
        "limite_seguro": 600,
        "perfil": [
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.3, 0.8, 0.9, 0.7, 0.5,   # mañana: uso principal
            0.3, 0.2, 0.2, 0.3, 0.5, 0.6,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        ],
    },
    "computador": {
        "potencia_base": 120,
        "limite_seguro": 150,
        "perfil": [
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.1, 0.5, 0.9, 1.0, 1.0, 0.9,   # horario laboral
            0.8, 0.9, 1.0, 1.0, 0.9, 0.7,
            0.6, 0.5, 0.4, 0.3, 0.1, 0.8,
        ],
    },
    "television": {
        "potencia_base": 100,
        "limite_seguro": 130,
        "perfil": [
            0.1, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.1, 0.1, 0.1, 0.1, 0.1,
            0.2, 0.2, 0.3, 0.3, 0.5, 0.8,   # tarde-noche: más uso
            1.0, 1.0, 0.9, 0.7, 0.4, 0.2,
        ],
    },
}

# Tarifa eléctrica en Colombia (COP por kWh, estrato 3 aprox.)
TARIFA_COP_KWH = 871.0


# ──────────────────────────────────────────────────────────
# 2. FUNCIÓN PRINCIPAL DE GENERACIÓN
# ──────────────────────────────────────────────────────────
def generar_lecturas(dias: int = 30, intervalo_minutos: int = 15) -> pd.DataFrame:
    """
    Genera un DataFrame con lecturas simuladas de consumo.

    Parámetros:
      dias               : cuántos días hacia atrás simular
      intervalo_minutos  : cada cuántos minutos tomar una lectura

    Retorna:
      DataFrame con columnas: timestamp, dispositivo,
                               potencia_w, energia_kwh,
                               costo_cop, es_sobrecarga
    """
    registros = []

    # Punto de inicio: hace 'dias' días desde ahora
    inicio = datetime.now() - timedelta(days=dias)
    # Total de intervalos = dias * 24 horas * (60 / intervalo_minutos)
    total_intervalos = int(dias * 24 * 60 / intervalo_minutos)

    for i in range(total_intervalos):
        # Calcula el timestamp de esta lectura
        timestamp = inicio + timedelta(minutes=i * intervalo_minutos)
        hora = timestamp.hour          # 0–23
        dia_semana = timestamp.weekday()  # 0=lunes, 6=domingo

        for nombre, config in DISPOSITIVOS.items():
            # Factor base del perfil para esta hora
            factor_hora = config["perfil"][hora]

            # Los fines de semana (sab=5, dom=6) la gente está más en casa
            if dia_semana >= 5:
                if nombre in ["television", "iluminacion", "computador"]:
                    factor_hora = min(1.0, factor_hora * 1.2)

            # Añade ruido gaussiano: pequeñas variaciones realistas
            # np.random.normal(media, desviacion_std)
            ruido = np.random.normal(0, 0.05)  # ±5% de variación
            factor_final = max(0.0, min(1.2, factor_hora + ruido))

            # Potencia real en esta lectura (Watts)
            potencia_w = config["potencia_base"] * factor_final

            # Energía consumida en este intervalo (kWh)
            # Fórmula: E = P * t   donde t está en horas
            horas_intervalo = intervalo_minutos / 60.0
            energia_kwh = (potencia_w / 1000.0) * horas_intervalo

            # Costo de esta lectura en pesos colombianos
            costo_cop = energia_kwh * TARIFA_COP_KWH

            # ¿Hay sobrecarga? Si supera el límite seguro
            es_sobrecarga = potencia_w > config["limite_seguro"]

            registros.append({
                "timestamp":     timestamp,
                "dispositivo":   nombre,
                "potencia_w":    round(potencia_w, 2),
                "energia_kwh":   round(energia_kwh, 6),
                "costo_cop":     round(costo_cop, 4),
                "es_sobrecarga": es_sobrecarga,
            })

    df = pd.DataFrame(registros)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


# ──────────────────────────────────────────────────────────
# 3. FUNCIÓN DE ANÁLISIS RÁPIDO
# ──────────────────────────────────────────────────────────
def analizar_dataset(df: pd.DataFrame) -> dict:
    """
    Calcula estadísticas clave del dataset generado.
    Retorna un diccionario con los resultados.
    """
    resumen = {}

    # Total de energía consumida por dispositivo
    resumen["energia_por_dispositivo"] = (
        df.groupby("dispositivo")["energia_kwh"]
        .sum()
        .round(3)
        .to_dict()
    )

    # Costo total por dispositivo
    resumen["costo_por_dispositivo"] = (
        df.groupby("dispositivo")["costo_cop"]
        .sum()
        .round(2)
        .to_dict()
    )

    # Cantidad de sobrecargas detectadas por dispositivo
    sobrecargas = df[df["es_sobrecarga"] == True]
    resumen["sobrecargas_por_dispositivo"] = (
        sobrecargas.groupby("dispositivo")
        .size()
        .to_dict()
    )

    # Totales globales
    resumen["total_energia_kwh"] = round(df["energia_kwh"].sum(), 3)
    resumen["total_costo_cop"] = round(df["costo_cop"].sum(), 2)
    resumen["total_lecturas"] = len(df)
    resumen["total_sobrecargas"] = len(sobrecargas)

    return resumen


# ──────────────────────────────────────────────────────────
# 4. PUNTO DE ENTRADA — Prueba el generador
# ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  GENERADOR DE DATOS — Sistema de Monitoreo Energético")
    print("=" * 55)

    print("\n  Generando 7 dias de lecturas cada 15 minutos...")
    df = generar_lecturas(dias=7, intervalo_minutos=15)

    print(f"  Lecturas generadas : {len(df):,}")
    print(f"  Dispositivos       : {df['dispositivo'].nunique()}")
    print(f"  Desde              : {df['timestamp'].min()}")
    print(f"  Hasta              : {df['timestamp'].max()}")

    print("\n--- Primeras 5 filas del dataset ---")
    print(df.head(5).to_string(index=False))

    print("\n--- Análisis del periodo ---")
    resumen = analizar_dataset(df)

    print(f"\n  Total energia consumida : {resumen['total_energia_kwh']} kWh")
    print(f"  Costo total estimado    : ${resumen['total_costo_cop']:,.0f} COP")
    print(f"  Total sobrecargas       : {resumen['total_sobrecargas']}")

    print("\n  Energia por dispositivo (kWh):")
    for disp, kwh in sorted(resumen["energia_por_dispositivo"].items(),
                             key=lambda x: x[1], reverse=True):
        barras = "█" * int(kwh * 2)
        print(f"    {disp:<22} {kwh:>8.3f} kWh  {barras}")

    print("\n  Sobrecargas detectadas:")
    if resumen["sobrecargas_por_dispositivo"]:
        for disp, cant in resumen["sobrecargas_por_dispositivo"].items():
            print(f"    {disp:<22} {cant:>5} eventos")
    else:
        print("    Ninguna en este periodo")

    # Guarda el dataset en un CSV para revisarlo
    df.to_csv("dataset_muestra.csv", index=False)
    print("\n  Dataset guardado en: dataset_muestra.csv")
    print("=" * 55)