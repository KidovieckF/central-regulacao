from flask_login import LoginManager

from .database import MySQLConnector
from .models.usuario import Usuario

from flask_socketio import SocketIO

socketio = SocketIO(async_mode='eventlet') 
mysql = MySQLConnector()
login_manager = LoginManager()

def init_extensions(app):
    socketio.init_app(app)

@login_manager.user_loader
def load_user(user_id: str):
    from app.repositories import usuarios as usuarios_repo

    data = usuarios_repo.obter_por_id(int(user_id))
    if data:
        return Usuario.from_row(data)
    return None

