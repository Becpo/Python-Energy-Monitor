# ============================================================
#  MÓDULO: lectura_energetica.py
#  Representa un único registro de consumo eléctrico.
# ============================================================

from dataclasses import dataclass
from datetime import datetime

# Importamos solo los límites de dispositivos que necesitamos
from .generador import DISPOSITIVOS


@dataclass
class LecturaEnergetica:
    """
    Un registro puntual de consumo de un dispositivo.

    Atributos:
        timestamp     : momento exacto de la lectura
        dispositivo   : nombre del dispositivo (debe existir en DISPOSITIVOS)
        potencia_w    : potencia en Watts en ese instante
        energia_kwh   : energía consumida en el intervalo (kWh)
        costo_cop     : costo base del intervalo en pesos colombianos
        es_sobrecarga : True si la potencia supera el límite seguro
    """
    timestamp:     datetime
    dispositivo:   str
    potencia_w:    float
    energia_kwh:   float
    costo_cop:     float
    es_sobrecarga: bool

    def estado(self) -> str:
        """
        Clasifica el estado de esta lectura en cuatro niveles:
          APAGADO    → potencia cero
          NORMAL     → por debajo del 85% del límite seguro
          ADVERTENCIA→ entre el 85% y el 100% del límite seguro
          SOBRECARGA → supera el límite seguro
        """
        if self.es_sobrecarga:
            return "SOBRECARGA"
        if self.potencia_w == 0:
            return "APAGADO"

        limite = DISPOSITIVOS[self.dispositivo]["limite_seguro"]
        if self.potencia_w > limite * 0.85:
            return "ADVERTENCIA"

        return "NORMAL"

    def resumen(self) -> str:
        """Texto de una línea para depuración o logs."""
        return (
            f"[{self.timestamp:%Y-%m-%d %H:%M}] "
            f"{self.dispositivo:<22} "
            f"{self.potencia_w:>7.1f} W  "
            f"{self.estado()}"
        )


# ──────────────────────────────────────────────────────────
# Prueba rápida — solo se ejecuta si corres este archivo
# directamente: python lectura_energetica.py
# ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    from datetime import datetime

    print("=== Prueba: LecturaEnergetica ===\n")

    casos = [
        LecturaEnergetica(datetime.now(), "nevera",             90.0,  0.0225, 14.6, False),
        LecturaEnergetica(datetime.now(), "nevera",            175.0,  0.0437, 28.4, False),
        LecturaEnergetica(datetime.now(), "nevera",            195.0,  0.0487, 31.7, False),
        LecturaEnergetica(datetime.now(), "aire_acondicionado",1850.0, 0.4625, 300.6, True),
        LecturaEnergetica(datetime.now(), "computador",          0.0,  0.0,    0.0,  False),
    ]

    for lectura in casos:
        print(" ", lectura.resumen())

    print("\nEstados posibles:", set(l.estado() for l in casos))