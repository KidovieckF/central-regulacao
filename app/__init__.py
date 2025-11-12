from datetime import datetime

from flask import Flask, current_app
from flask_login import current_user

from config import Config
from .extensions import login_manager, mysql, socketio, init_extensions
from .blueprints.auth import auth_bp
from .blueprints.dashboards import dashboards_bp
from .blueprints.reception import reception_bp
from .blueprints.malote import malote_bp
from .blueprints.regulator import regulator_bp
from .blueprints.scheduling import scheduling_bp
from .blueprints.admin import admin_bp
from .blueprints.chat import chat_blueprint

def create_app(config_class: type[Config] = Config) -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(config_class)

    init_extensions(app)
    mysql.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Faça login para continuar."

    register_blueprints(app)

    @app.context_processor
    def inject_template_globals():
        role = getattr(current_user, "role", None)
        unidade = getattr(current_user, "unidade_nome", None)
        return {
            "usuario_logado_role": role,
            "usuario_logado_unidade": unidade,
            "current_year": datetime.now().year,
            "app_version": current_app.config.get("APP_VERSION", "1.0.0"),
        }
    
    from .blueprints.chat import socket_events

    return app


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboards_bp)
    app.register_blueprint(reception_bp, url_prefix="/recepcao")
    app.register_blueprint(malote_bp, url_prefix="/malote")
    app.register_blueprint(regulator_bp, url_prefix="/regulador")
    app.register_blueprint(scheduling_bp, url_prefix="/agendamento")
    app.register_blueprint(admin_bp)
    app.register_blueprint(chat_blueprint)