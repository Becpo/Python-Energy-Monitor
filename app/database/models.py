# ============================================================
#  ARCHIVO: migrations/models.py
#  Define las 5 tablas de MySQL como clases Python (ORM).
#
#  Cada clase representa una tabla del schema.sql:
#    Dispositivo  →  TABLE dispositivos
#    Lectura      →  TABLE lecturas
#    Alerta       →  TABLE alertas
#    CostoDiario  →  TABLE costos_diarios
#    Reporte      →  TABLE reportes
#
#  Flask-Migrate lee este archivo para generar y aplicar
#  las migraciones automáticamente.
# ============================================================

from datetime import datetime
from .extensions import db
from sqlalchemy.sql import func


# ╔══════════════════════════════════════════════════════════╗
# ║  MODELO 1: Dispositivo                                  ║
# ║  TABLE dispositivos                                     ║
# ╚══════════════════════════════════════════════════════════╝
class Dispositivo(db.Model):
    __tablename__  = "dispositivos"
    __table_args__ = {
        "comment": "Catálogo de dispositivos eléctricos"
    }

    id            = db.Column(db.Integer,      primary_key=True, autoincrement=True)
    nombre        = db.Column(db.String(60),   nullable=False, unique=True)
    potencia_base = db.Column(db.Float,        nullable=False,
                              comment="Watts nominales")
    limite_seguro = db.Column(db.Float,        nullable=False,
                              comment="Umbral de sobrecarga en W")
    activo        = db.Column(db.SmallInteger, nullable=False, default=1)
    creado_en     = db.Column(db.DateTime,     nullable=False,
                              server_default=func.now())

    # Relaciones hacia las tablas hijas
    # backref crea el atributo inverso automáticamente:
    # lectura.dispositivo  →  devuelve el Dispositivo padre
    lecturas       = db.relationship("Lectura",     backref="dispositivo", lazy=True)
    alertas        = db.relationship("Alerta",      backref="dispositivo", lazy=True)
    costos_diarios = db.relationship("CostoDiario", backref="dispositivo", lazy=True)

    def __repr__(self):
        return f"<Dispositivo {self.nombre}>"

    def to_dict(self) -> dict:
        return {
            "id":            self.id,
            "nombre":        self.nombre,
            "potencia_base": self.potencia_base,
            "limite_seguro": self.limite_seguro,
            "activo":        bool(self.activo),
        }


# ╔══════════════════════════════════════════════════════════╗
# ║  MODELO 2: Lectura                                      ║
# ║  TABLE lecturas                                         ║
# ╚══════════════════════════════════════════════════════════╝
class Lectura(db.Model):
    __tablename__  = "lecturas"
    __table_args__ = (
        # Índice compuesto — acelera:
        # "dame lecturas de la nevera en las últimas 24h"
        db.Index("idx_disp_tiempo", "dispositivo_id", "timestamp"),
        db.Index("idx_timestamp",   "timestamp"),
        db.Index("idx_sobrecarga",  "es_sobrecarga"),
        {"comment": "Lecturas de consumo por intervalo de 15 minutos"},
    )

    id             = db.Column(db.BigInteger,    primary_key=True, autoincrement=True)
    dispositivo_id = db.Column(
                        db.Integer,
                        db.ForeignKey("dispositivos.id",
                                      ondelete="RESTRICT",
                                      onupdate="CASCADE"),
                        nullable=False
                     )
    timestamp      = db.Column(db.DateTime,      nullable=False)
    potencia_w     = db.Column(db.Float,         nullable=False,
                               comment="Watts en este instante")
    energia_kwh    = db.Column(db.Numeric(10, 6), nullable=False,
                               comment="kWh consumidos en el intervalo")
    costo_cop      = db.Column(db.Numeric(12, 4), nullable=False,
                               comment="Costo en pesos colombianos")
    es_sobrecarga  = db.Column(db.SmallInteger,  nullable=False, default=0)

    def __repr__(self):
        return f"<Lectura {self.dispositivo_id} @ {self.timestamp}>"

    def to_dict(self) -> dict:
        return {
            "id":             self.id,
            "dispositivo_id": self.dispositivo_id,
            "timestamp":      self.timestamp.isoformat(),
            "potencia_w":     self.potencia_w,
            "energia_kwh":    float(self.energia_kwh),
            "costo_cop":      float(self.costo_cop),
            "es_sobrecarga":  bool(self.es_sobrecarga),
        }


# ╔══════════════════════════════════════════════════════════╗
# ║  MODELO 3: Alerta                                       ║
# ║  TABLE alertas                                          ║
# ╚══════════════════════════════════════════════════════════╝
class Alerta(db.Model):
    __tablename__  = "alertas"
    __table_args__ = (
        db.Index("idx_alertas_disp",     "dispositivo_id"),
        db.Index("idx_alertas_tipo",     "tipo"),
        db.Index("idx_alertas_resuelta", "resuelta"),
        {"comment": "Eventos de sobrecarga y advertencia detectados"},
    )

    # Los tres valores válidos del ENUM tipo
    TIPOS = ("PICO", "SOSTENIDA", "ADVERTENCIA")

    id               = db.Column(db.Integer,   primary_key=True, autoincrement=True)
    dispositivo_id   = db.Column(
                          db.Integer,
                          db.ForeignKey("dispositivos.id",
                                        ondelete="RESTRICT",
                                        onupdate="CASCADE"),
                          nullable=False
                       )
    tipo             = db.Column(db.Enum("PICO", "SOSTENIDA", "ADVERTENCIA"),
                                 nullable=False)
    potencia_pico    = db.Column(db.Float,     nullable=False,
                                 comment="Peor W registrado en el evento")
    duracion_min     = db.Column(db.Integer,   nullable=False, default=0,
                                 comment="Minutos en sobrecarga")
    timestamp_inicio = db.Column(db.DateTime,  nullable=False)
    timestamp_fin    = db.Column(db.DateTime,  nullable=False)
    resuelta         = db.Column(
                          db.SmallInteger,
                          nullable=False,
                          default=0,
                          server_default="0"
                      )
    creado_en        = db.Column(db.DateTime,  nullable=False,
                                 server_default=func.now())

    def __repr__(self):
        return f"<Alerta {self.tipo} — {self.dispositivo_id}>"

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "dispositivo_id":   self.dispositivo_id,
            "tipo":             self.tipo,
            "potencia_pico":    self.potencia_pico,
            "duracion_min":     self.duracion_min,
            "timestamp_inicio": self.timestamp_inicio.isoformat(),
            "timestamp_fin":    self.timestamp_fin.isoformat(),
            "resuelta":         bool(self.resuelta),
        }


# ╔══════════════════════════════════════════════════════════╗
# ║  MODELO 4: CostoDiario                                  ║
# ║  TABLE costos_diarios                                   ║
# ╚══════════════════════════════════════════════════════════╝
class CostoDiario(db.Model):
    __tablename__  = "costos_diarios"
    __table_args__ = (
        # Garantiza que no haya duplicados por dispositivo + fecha
        # Equivale al UNIQUE KEY uq_disp_fecha del schema.sql
        db.UniqueConstraint("dispositivo_id", "fecha",
                            name="uq_disp_fecha"),
        db.Index("idx_costos_fecha", "fecha"),
        {"comment": "Costos energéticos agregados por día"},
    )

    id             = db.Column(db.Integer,       primary_key=True, autoincrement=True)
    dispositivo_id = db.Column(
                        db.Integer,
                        db.ForeignKey("dispositivos.id",
                                      ondelete="RESTRICT",
                                      onupdate="CASCADE"),
                        nullable=False
                     )
    fecha          = db.Column(db.Date,          nullable=False)
    energia_kwh    = db.Column(db.Numeric(10, 4), nullable=False)
    costo_cop      = db.Column(db.Numeric(14, 2), nullable=False)
    franja_valle   = db.Column(db.Numeric(14, 2), nullable=False, default=0,
                               comment="Costo 00-06h")
    franja_normal  = db.Column(db.Numeric(14, 2), nullable=False, default=0,
                               comment="Costo 06-18h")
    franja_punta   = db.Column(db.Numeric(14, 2), nullable=False, default=0,
                               comment="Costo 18-24h")

    def __repr__(self):
        return f"<CostoDiario {self.dispositivo_id} — {self.fecha}>"

    def to_dict(self) -> dict:
        return {
            "id":             self.id,
            "dispositivo_id": self.dispositivo_id,
            "fecha":          str(self.fecha),
            "energia_kwh":    float(self.energia_kwh),
            "costo_cop":      float(self.costo_cop),
            "franja_valle":   float(self.franja_valle),
            "franja_normal":  float(self.franja_normal),
            "franja_punta":   float(self.franja_punta),
        }


# ╔══════════════════════════════════════════════════════════╗
# ║  MODELO 5: Reporte                                      ║
# ║  TABLE reportes                                         ║
# ╚══════════════════════════════════════════════════════════╝
class Reporte(db.Model):
    __tablename__  = "reportes"
    __table_args__ = (
        db.Index("idx_reportes_fecha", "fecha_generacion"),
        {"comment": "Reportes generados por el motor de análisis"},
    )

    id                 = db.Column(db.Integer,       primary_key=True, autoincrement=True)
    fecha_generacion   = db.Column(db.DateTime,      nullable=False,
                                   server_default=func.now())
    periodo_inicio     = db.Column(db.DateTime,      nullable=False)
    periodo_fin        = db.Column(db.DateTime,      nullable=False)
    total_lecturas     = db.Column(db.Integer,       nullable=False)
    total_energia_kwh  = db.Column(db.Numeric(12, 3), nullable=False)
    total_costo_cop    = db.Column(db.Numeric(16, 2), nullable=False)
    proyeccion_mensual = db.Column(db.Numeric(16, 2), nullable=False)
    total_sobrecargas  = db.Column(db.Integer,       nullable=False, default=0)
    dispositivo_top    = db.Column(db.String(60),    nullable=True,
                                   comment="Mayor consumidor")
    datos_json         = db.Column(db.JSON,          nullable=True,
                                   comment="Reporte completo serializado")

    def __repr__(self):
        return f"<Reporte {self.id} — {self.fecha_generacion}>"

    def to_dict(self) -> dict:
        return {
            "id":                 self.id,
            "fecha_generacion":   self.fecha_generacion.isoformat(),
            "periodo_inicio":     self.periodo_inicio.isoformat(),
            "periodo_fin":        self.periodo_fin.isoformat(),
            "total_lecturas":     self.total_lecturas,
            "total_energia_kwh":  float(self.total_energia_kwh),
            "total_costo_cop":    float(self.total_costo_cop),
            "proyeccion_mensual": float(self.proyeccion_mensual),
            "total_sobrecargas":  self.total_sobrecargas,
            "dispositivo_top":    self.dispositivo_top,
        }