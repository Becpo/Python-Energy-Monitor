# ============================================================
#  MÓDULO: detector_sobrecargas.py
#  Analiza un DataFrame de lecturas y encuentra eventos
#  peligrosos: picos, sobrecargas sostenidas y nivel de riesgo.
# ============================================================

import pandas as pd


class DetectorSobrecargas:
    """
    Recibe el DataFrame completo de lecturas y expone métodos
    para encontrar distintos tipos de eventos de sobrecarga.

    Uso:
        detector = DetectorSobrecargas(df)
        picos    = detector.detectar_picos()
        riesgo   = detector.nivel_riesgo("aire_acondicionado")
        resumen  = detector.resumen()
    """

    # Mínimo de lecturas consecutivas para considerar
    # que una sobrecarga es "sostenida" y no un pico aislado.
    # Con intervalos de 15 min → 3 lecturas = 45 minutos seguidos.
    UMBRAL_CONSECUTIVO = 3

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    # ----------------------------------------------------------
    # MÉTODO 1: Picos aislados
    # ----------------------------------------------------------
    def detectar_picos(self) -> pd.DataFrame:
        """
        Retorna todas las filas donde la potencia supera el
        límite seguro del dispositivo, sin importar si son
        consecutivas o no.
        """
        return self.df[self.df["es_sobrecarga"]].copy()

    # ----------------------------------------------------------
    # MÉTODO 2: Sobrecargas sostenidas
    # ----------------------------------------------------------
    def detectar_sobrecargas_sostenidas(self) -> list[dict]:
        """
        Agrupa lecturas consecutivas en sobrecarga para un mismo
        dispositivo y retorna solo los eventos que duran al menos
        UMBRAL_CONSECUTIVO intervalos seguidos.

        Cada evento del resultado es un dict con:
          dispositivo, inicio, fin, duracion_min, pico_w, tipo
        """
        eventos = []

        for dispositivo in self.df["dispositivo"].unique():
            # Filtramos y ordenamos solo este dispositivo
            sub = (
                self.df[self.df["dispositivo"] == dispositivo]
                .sort_values("timestamp")
                .reset_index(drop=True)
            )

            contador    = 0
            inicio_evt  = None

            for idx, fila in sub.iterrows():
                if fila["es_sobrecarga"]:
                    if contador == 0:
                        inicio_evt = fila["timestamp"]
                    contador += 1
                else:
                    # La racha terminó — ¿fue suficientemente larga?
                    if contador >= self.UMBRAL_CONSECUTIVO:
                        fin_idx = max(0, idx - 1)
                        eventos.append({
                            "dispositivo":  dispositivo,
                            "inicio":       inicio_evt,
                            "fin":          sub.iloc[fin_idx]["timestamp"],
                            "duracion_min": contador * 15,
                            "pico_w":       sub.iloc[max(0, idx - contador):idx]["potencia_w"].max(),
                            "tipo":         "SOSTENIDA",
                        })
                    contador   = 0
                    inicio_evt = None

            # Caso borde: el DataFrame termina mientras hay sobrecarga activa
            if contador >= self.UMBRAL_CONSECUTIVO:
                eventos.append({
                    "dispositivo":  dispositivo,
                    "inicio":       inicio_evt,
                    "fin":          sub.iloc[-1]["timestamp"],
                    "duracion_min": contador * 15,
                    "pico_w":       sub.tail(contador)["potencia_w"].max(),
                    "tipo":         "SOSTENIDA",
                })

        return eventos

    # ----------------------------------------------------------
    # MÉTODO 3: Nivel de riesgo
    # ----------------------------------------------------------
    def nivel_riesgo(self, dispositivo: str) -> str:
        """
        Clasifica el riesgo de un dispositivo en función del
        porcentaje de lecturas que estuvieron en sobrecarga:

          SEGURO      → 0 %
          BAJO        → < 2 %
          MEDIO       → 2 % – 10 %
          ALTO        → ≥ 10 %
          DESCONOCIDO → dispositivo sin lecturas
        """
        mask_disp = self.df["dispositivo"] == dispositivo
        total     = mask_disp.sum()

        if total == 0:
            return "DESCONOCIDO"

        sobrecargas = (mask_disp & self.df["es_sobrecarga"]).sum()
        porcentaje  = sobrecargas / total * 100

        if porcentaje == 0:
            return "SEGURO"
        elif porcentaje < 2:
            return "BAJO"
        elif porcentaje < 10:
            return "MEDIO"
        else:
            return "ALTO"

    # ----------------------------------------------------------
    # MÉTODO 4: Resumen consolidado
    # ----------------------------------------------------------
    def resumen(self) -> dict:
        """
        Devuelve un diccionario con todos los indicadores
        de sobrecarga. Es lo que consume el orquestador.
        """
        picos      = self.detectar_picos()
        sostenidas = self.detectar_sobrecargas_sostenidas()

        return {
            "total_picos":            len(picos),
            "total_sostenidas":       len(sostenidas),
            "dispositivos_afectados": picos["dispositivo"].unique().tolist(),
            "peor_pico_w":            round(picos["potencia_w"].max(), 2) if len(picos) else 0,
            "eventos_sostenidos":     sostenidas,
        }


# ──────────────────────────────────────────────────────────
# Prueba rápida — python detector_sobrecargas.py
# ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    from .generador import generar_lecturas

    print("=== Prueba: DetectorSobrecargas ===\n")

    # Usamos solo 7 días para que la prueba sea rápida
    df = generar_lecturas(dias=7, intervalo_minutos=15)
    detector = DetectorSobrecargas(df)

    picos = detector.detectar_picos()
    print(f"  Picos detectados     : {len(picos)}")

    sostenidas = detector.detectar_sobrecargas_sostenidas()
    print(f"  Sobrecargas sostenidas: {len(sostenidas)}")

    print("\n  Nivel de riesgo por dispositivo:")
    for disp in df["dispositivo"].unique():
        nivel = detector.nivel_riesgo(disp)
        print(f"    {disp:<24} {nivel}")

    print("\n  Resumen completo:")
    r = detector.resumen()
    for clave, valor in r.items():
        if clave != "eventos_sostenidos":
            print(f"    {clave:<28} {valor}")