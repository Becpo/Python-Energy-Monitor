# ============================================================
#  Fábrica de la aplicación Flask
#  Sistema de Monitoreo Energético
# ============================================================

import os

from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

# Ruta absoluta a la raíz del proyecto (un nivel arriba de app/)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Carga el .env usando ruta absoluta — funciona sin importar
# desde dónde se ejecute el script (run.py, flask CLI, tests)
load_dotenv(os.path.join(ROOT, ".env"))


def create_app():
    app = Flask(__name__, template_folder=os.path.join(ROOT, "templates"),
        static_folder=os.path.join(ROOT, "static"),)
    
    # ── Configuración base de datos ────────────────────────
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"mysql+mysqlconnector://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
        f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
 
    # ── Inicializar extensiones ────────────────────────────
    # Importamos desde su ubicación real: app/database/
    from app.database.extensions import db, migrate
    db.init_app(app)
    migrate.init_app(app, db)
 
    # Importar modelos para que Flask-Migrate los detecte
    from app.database import models  # noqa: F401
    
    # CORS permite que el HTML (en otro puerto o archivo local)
    # pueda hacer peticiones fetch() a esta API sin bloqueos
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Registra todas las rutas desde routes.py
    from app.routes import main
    app.register_blueprint(main)

    # Manejadores globales de error
    from app.routes import manejar_error_global, no_encontrado
    app.register_error_handler(Exception, manejar_error_global)
    app.register_error_handler(404, no_encontrado)

    return app