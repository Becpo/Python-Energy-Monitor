# ============================================================
#  MÓDULO: motor_analisis.py
#  Orquestador principal — coordina los tres módulos
#  especializados y produce el reporte final.
# ============================================================

import pandas as pd
from datetime import datetime

from .generador            import generar_lecturas
from .lectura_energetica   import LecturaEnergetica
from .detector_sobrecargas import DetectorSobrecargas
from .calculador_costos    import CalculadorCostos


class AnalizadorConsumo:
    """
    Orquestador principal del sistema.
    No contiene lógica de negocio propia — delega todo
    a los módulos especializados y ensambla el reporte.

    Uso:
        df         = generar_lecturas(dias=30)
        analizador = AnalizadorConsumo(df)
        reporte    = analizador.generar_reporte()
    """

    def __init__(self, df: pd.DataFrame):
        self.df         = df.copy()
        self.detector   = DetectorSobrecargas(df)
        self.calculador = CalculadorCostos(df)

    # ----------------------------------------------------------
    # Perfil de consumo por hora del día
    # ----------------------------------------------------------
    def perfil_por_hora(self) -> pd.DataFrame:
        """
        Potencia promedio por hora (0–23) y por dispositivo.
        Útil para renderizar la curva de carga en el dashboard.
        """
        self.df["hora"] = pd.to_datetime(self.df["timestamp"]).dt.hour
        return (
            self.df.groupby(["hora", "dispositivo"])["potencia_w"]
            .mean()
            .round(2)
            .reset_index()
            .rename(columns={"potencia_w": "promedio_w"})
        )

    # ----------------------------------------------------------
    # Consumo diario por dispositivo
    # ----------------------------------------------------------
    def consumo_diario(self) -> pd.DataFrame:
        """
        Energía total (kWh) por fecha y dispositivo.
        Útil para la gráfica de barras apiladas del dashboard.
        """
        self.df["fecha"] = pd.to_datetime(self.df["timestamp"]).dt.date
        return (
            self.df.groupby(["fecha", "dispositivo"])["energia_kwh"]
            .sum()
            .round(4)
            .reset_index()
        )

    # ----------------------------------------------------------
    # Top N consumidores
    # ----------------------------------------------------------
    def top_consumidores(self, n: int = 3) -> list[dict]:
        return (
            self.df.groupby("dispositivo")["energia_kwh"]
            .sum()
            .sort_values(ascending=False)
            .head(n)
            .round(3)
            .reset_index()
            .rename(columns={"energia_kwh": "energia_kwh"})
            .to_dict(orient="records")
        )

    # ----------------------------------------------------------
    # Reporte completo
    # ----------------------------------------------------------
    def generar_reporte(self) -> dict:
        """
        Ensambla todos los indicadores en un único diccionario.
        Este es el contrato de datos que consumen:
          - la Fase 3 (MySQL)
          - la Fase 4 (API Flask)
          - la Fase 5 (Dashboard)
        """
        costos      = self.calculador.costo_por_dispositivo()
        sobrecargas = self.detector.resumen()
        mas_costoso = self.calculador.dispositivo_mas_costoso()

        return {
            "generado_en":            datetime.now().isoformat(),
            "periodo_inicio":         str(self.df["timestamp"].min()),
            "periodo_fin":            str(self.df["timestamp"].max()),
            "total_lecturas":         len(self.df),
            "total_energia_kwh":      round(self.df["energia_kwh"].sum(), 3),
            "total_costo_cop":        round(self.calculador.df["costo_real_cop"].sum(), 2),
            "proyeccion_mensual":     self.calculador.proyeccion_mensual(),
            "dispositivo_mas_costoso": mas_costoso[0],
            "top_consumidores":       self.top_consumidores(3),
            "costos_por_dispositivo": costos,
            "costos_por_franja":      self.calculador.costo_por_franja(),
            "sobrecargas": {
                "total_picos":        sobrecargas["total_picos"],
                "total_sostenidas":   sobrecargas["total_sostenidas"],
                "peor_pico_w":        sobrecargas["peor_pico_w"],
                "afectados":          sobrecargas["dispositivos_afectados"],
            },
            "riesgo_por_dispositivo": {
                disp: self.detector.nivel_riesgo(disp)
                for disp in self.df["dispositivo"].unique()
            },
            "ahorros_potenciales": {
                disp: self.calculador.ahorro_si_optimiza(disp)
                for disp in self.df["dispositivo"].unique()
            },
        }


# ──────────────────────────────────────────────────────────
# Prueba de integración completa
# ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    SEP = "=" * 58

    print(SEP)
    print("  MOTOR DE ANÁLISIS — Prueba de integración completa")
    print(SEP)

    df = generar_lecturas(dias=30, intervalo_minutos=15)
    analizador = AnalizadorConsumo(df)
    reporte    = analizador.generar_reporte()

    print(f"\n  Periodo        : {reporte['periodo_inicio'][:10]}  →  {reporte['periodo_fin'][:10]}")
    print(f"  Total energía  : {reporte['total_energia_kwh']} kWh")
    print(f"  Costo real     : ${reporte['total_costo_cop']:>12,.0f} COP")
    print(f"  Proyec. mensual: ${reporte['proyeccion_mensual']:>12,.0f} COP")

    print(f"\n{'─'*58}")
    print("  TOP CONSUMIDORES")
    for i, item in enumerate(reporte["top_consumidores"], 1):
        print(f"  {i}. {item['dispositivo']:<24} {item['energia_kwh']:>8.3f} kWh")

    print(f"\n{'─'*58}")
    print("  COSTOS POR FRANJA")
    etq = {"valle": "Valle  00–06h", "normal": "Normal 06–18h", "punta": "Punta  18–24h"}
    for f, c in reporte["costos_por_franja"].items():
        print(f"  {etq[f]}   ${c:>12,.0f} COP")

    print(f"\n{'─'*58}")
    print("  RIESGO POR DISPOSITIVO")
    iconos = {"SEGURO": "✓", "BAJO": "~", "MEDIO": "!", "ALTO": "!!", "DESCONOCIDO": "?"}
    for disp, nivel in reporte["riesgo_por_dispositivo"].items():
        print(f"  [{iconos.get(nivel,'?')}] {disp:<24} {nivel}")

    print(f"\n{'─'*58}")
    print("  AHORRO POTENCIAL (reducción 15%)")
    ahorros = sorted(reporte["ahorros_potenciales"].items(), key=lambda x: x[1], reverse=True)
    for disp, ahorro in ahorros:
        print(f"  {disp:<26} ${ahorro:>10,.0f} COP/mes")

    print(f"\n{SEP}")
    print("  Todos los módulos integrados correctamente.")
    print(SEP)