# ============================================================
#  MÓDULO: calculador_costos.py
#  Calcula costos reales por franja horaria, proyecciones
#  mensuales y oportunidades de ahorro.
#  Depende de: generador.py (para la tarifa base)
# ============================================================

import pandas as pd
from .generador import TARIFA_COP_KWH


class CalculadorCostos:
    """
    Aplica tarifas diferenciadas por franja horaria al DataFrame
    de lecturas y expone métodos de análisis económico.

    Franjas horarias (simulando tarifa colombiana):
      Valle  (00–06h): 75% de la tarifa base  → más barato
      Normal (06–18h): 100% de la tarifa base → precio estándar
      Punta  (18–24h): 135% de la tarifa base → más caro

    Uso:
        calc = CalculadorCostos(df)
        calc.costo_por_dispositivo()
        calc.proyeccion_mensual()
        calc.ahorro_si_optimiza("aire_acondicionado")
    """

    FRANJAS = {
        "valle":  {"horas": list(range(0, 6)),   "factor": 0.75},
        "normal": {"horas": list(range(6, 18)),  "factor": 1.00},
        "punta":  {"horas": list(range(18, 24)), "factor": 1.35},
    }

    def __init__(self, df: pd.DataFrame, tarifa_base: float = TARIFA_COP_KWH):
        self.tarifa_base = tarifa_base

        # Trabajamos sobre una copia para no modificar el DataFrame original
        self.df = df.copy()

        # Columna auxiliar: hora del día (0–23)
        self.df["hora"] = pd.to_datetime(self.df["timestamp"]).dt.hour

        # Columna auxiliar: franja según la hora
        self.df["franja"] = self.df["hora"].apply(self._clasificar_franja)

        # Columna principal: costo recalculado con factor de franja
        self.df["costo_real_cop"] = self.df.apply(self._costo_con_franja, axis=1)

    # ----------------------------------------------------------
    # Métodos internos (privados por convención: prefijo _)
    # ----------------------------------------------------------
    def _clasificar_franja(self, hora: int) -> str:
        """Devuelve el nombre de la franja para una hora dada."""
        for nombre, config in self.FRANJAS.items():
            if hora in config["horas"]:
                return nombre
        return "normal"

    def _costo_con_franja(self, fila) -> float:
        """Calcula el costo de una fila aplicando el factor de su franja."""
        factor = self.FRANJAS[fila["franja"]]["factor"]
        return round(fila["energia_kwh"] * self.tarifa_base * factor, 4)

    # ----------------------------------------------------------
    # MÉTODO 1: Costo total por dispositivo
    # ----------------------------------------------------------
    def costo_por_dispositivo(self) -> dict:
        """
        Suma el costo real (con franja) agrupado por dispositivo.
        Retorna dict ordenado de mayor a menor costo.
        """
        return (
            self.df.groupby("dispositivo")["costo_real_cop"]
            .sum()
            .round(2)
            .sort_values(ascending=False)
            .to_dict()
        )

    # ----------------------------------------------------------
    # MÉTODO 2: Costo por franja horaria
    # ----------------------------------------------------------
    def costo_por_franja(self) -> dict:
        """
        Muestra cuánto se gastó en cada franja horaria.
        Útil para recomendar cambiar horarios de uso.
        """
        return (
            self.df.groupby("franja")["costo_real_cop"]
            .sum()
            .round(2)
            .to_dict()
        )

    # ----------------------------------------------------------
    # MÉTODO 3: Proyección mensual
    # ----------------------------------------------------------
    def proyeccion_mensual(self) -> float:
        """
        Extrapola el gasto del periodo analizado a 30 días.

        Fórmula: (costo_total / dias_reales) × 30
        """
        dias = (
            self.df["timestamp"].max() - self.df["timestamp"].min()
        ).days
        if dias == 0:
            return 0.0
        costo_diario = self.df["costo_real_cop"].sum() / dias
        return round(costo_diario * 30, 2)

    # ----------------------------------------------------------
    # MÉTODO 4: Dispositivo más costoso
    # ----------------------------------------------------------
    def dispositivo_mas_costoso(self) -> tuple[str, float]:
        """Retorna (nombre, costo) del dispositivo que más gasta."""
        costos = self.costo_por_dispositivo()
        if not costos:
            return ("ninguno", 0.0)
        nombre = max(costos, key=costos.get) # type: ignore
        return (nombre, costos[nombre])

    # ----------------------------------------------------------
    # MÉTODO 5: Ahorro potencial por optimización
    # ----------------------------------------------------------
    def ahorro_si_optimiza(self, dispositivo: str, reduccion_pct: float = 0.15) -> float:
        """
        Responde: ¿cuánto ahorraría el usuario si reduce el consumo
        de este dispositivo en X%?

        Parámetros:
            dispositivo   : nombre del dispositivo a optimizar
            reduccion_pct : fracción de reducción (0.15 = 15%)
        """
        costo_disp = self.df[
            self.df["dispositivo"] == dispositivo
        ]["costo_real_cop"].sum()
        return round(costo_disp * reduccion_pct, 2)

    # ----------------------------------------------------------
    # MÉTODO 6: Comparativa de franjas para un dispositivo
    # ----------------------------------------------------------
    def desglose_franja_dispositivo(self, dispositivo: str) -> dict:
        """
        Para un dispositivo específico, muestra cuánto gasta
        en cada franja. Ayuda a decidir en qué horario conviene usarlo.
        """
        mask = self.df["dispositivo"] == dispositivo
        return (
            self.df[mask]
            .groupby("franja")["costo_real_cop"]
            .sum()
            .round(2)
            .to_dict()
        )


# ──────────────────────────────────────────────────────────
# Prueba rápida — python calculador_costos.py
# ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    from generador import generar_lecturas

    print("=== Prueba: CalculadorCostos ===\n")

    df   = generar_lecturas(dias=7, intervalo_minutos=15)
    calc = CalculadorCostos(df)

    print("  Costo por dispositivo (COP):")
    for disp, costo in calc.costo_por_dispositivo().items():
        print(f"    {disp:<24} ${costo:>10,.0f}")

    print("\n  Costo por franja horaria (COP):")
    etiquetas = {"valle": "Valle  00–06h", "normal": "Normal 06–18h", "punta": "Punta  18–24h"}
    for franja, costo in calc.costo_por_franja().items():
        print(f"    {etiquetas[franja]}   ${costo:>10,.0f}")

    nombre, costo = calc.dispositivo_mas_costoso()
    print(f"\n  Dispositivo más costoso : {nombre}  (${costo:,.0f} COP)")
    print(f"  Proyección mensual      : ${calc.proyeccion_mensual():,.0f} COP")

    print("\n  Ahorro potencial (reducción 15%):")
    for disp in df["dispositivo"].unique():
        ahorro = calc.ahorro_si_optimiza(disp)
        print(f"    {disp:<24} ${ahorro:>8,.0f} COP")

    print("\n  Desglose de lavadora por franja:")
    for franja, costo in calc.desglose_franja_dispositivo("lavadora").items():
        print(f"    {franja:<10}  ${costo:>8,.0f} COP")