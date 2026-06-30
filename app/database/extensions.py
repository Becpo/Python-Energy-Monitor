# ============================================================
#  ARCHIVO: migrations/extensions.py
#  Instancia las extensiones Flask de forma global.
#
#  Por qué un archivo separado:
#  Si instanciáramos db dentro de app.py o models.py,
#  tendríamos importaciones circulares:
#    app.py importa models → models importa db → db necesita app
#  Al poner db aquí, todos importan desde extensions.py
#  sin crear ciclos.
# ============================================================

from flask_sqlalchemy import SQLAlchemy
from flask_migrate    import Migrate

# Instancias globales — aún no están ligadas a ninguna app.
# Se conectan a la app en run.py mediante init_app().
db      = SQLAlchemy()
migrate = Migrate()