from flask_socketio import SocketIO
from flask_login import LoginManager
from .database import MySQLConnector
from .models.usuario import Usuario

# Usa gevent em vez de eventlet
socketio = SocketIO(
    async_mode="gevent",
    cors_allowed_origins="*",
    ping_timeout=30,
    ping_interval=10,
)

mysql = MySQLConnector()
login_manager = LoginManager()

def init_extensions(app):
    mysql.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"

@login_manager.user_loader
def load_user(user_id: str):
    from app.repositories import usuarios as usuarios_repo
    data = usuarios_repo.obter_por_id(int(user_id))
    if data:
        return Usuario.from_row(data)
    return None