"""Ponto de entrada da aplicação Flask‑SocketIO."""

from app import create_app
from app.extensions import socketio

# Cria a instância da aplicação Flask
app = create_app()

if __name__ == "__main__":
    import gevent
    from gevent import monkey

    # Necessário para habilitar I/O cooperativo (patch de sockets e threads)
    monkey.patch_all()

    # Executa usando gevent, 100% compatível com Python 3.14
    socketio.run(
        app,
        host="0.0.0.0",
        port=5000,
        debug=app.config.get("FLASK_ENV") == "development",
        allow_unsafe_werkzeug=True,  # evita warnings em modo dev
    )