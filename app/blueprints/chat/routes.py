from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.extensions import mysql
import os
from werkzeug.utils import secure_filename

# Configurações de upload
UPLOAD_FOLDER = 'app/static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

chat_blueprint = Blueprint('chat', __name__)

@chat_blueprint.route('/chat')
@login_required
def chat():
    role = current_user.role
    room_name = None

    if role == "malote":
        room_name = "malote_admin"
    elif role == "recepcao":
        room_name = "recepcao_admin"
    elif role == "medico_regulador":
        room_name = "regulacao_admin"
    elif role == "admin":
        room_name = "malote_admin"  # o admin pode ter interface para trocar entre salas

    return render_template("chat/chat.html", room_name=room_name)

@chat_blueprint.route("/chat/malote")
@login_required
def chat_malote_admin():
    # Buscar o usuário admin
    with mysql.get_cursor(dictionary=True) as (_, cursor):
        cursor.execute("SELECT id FROM usuarios WHERE role = 'admin' LIMIT 1")
        admin = cursor.fetchone()

    if not admin:
        return "❌ Nenhum administrador encontrado.", 500

    # Criar ou obter conversa privada entre o malote e o admin
    conversation_id, room_name = get_or_create_private_conversation(
        current_user.id, admin["id"]
    )

    return render_template("chat/chat.html", room_name=room_name)

@chat_blueprint.route('/chat/<room_name>')
@login_required
def chat_room(room_name):
    conn = mysql.connect()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT m.message, m.created_at, u.nome AS user
        FROM messages m
        JOIN usuarios u ON m.user_id = u.id
        JOIN conversations c ON m.conversation_id = c.id
        WHERE c.room = %s
        ORDER BY m.created_at ASC
    """, (room_name,))
    messages = cursor.fetchall()
    cursor.close()

    return render_template('chat/chat.html', room_name=room_name, messages=messages)

@chat_blueprint.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(UPLOAD_FOLDER, filename))
        return jsonify({'filename': filename}), 201
    return jsonify({'error': 'File type not allowed'}), 400


@chat_blueprint.route('/chat/mensagens/<room_name>')
@login_required
def get_messages(room_name):
    """Retorna as mensagens salvas de uma sala específica"""
    try:
        print(f"🧠 Buscando mensagens da sala: {room_name}")

        with mysql.get_cursor() as (conn, cursor):
            cursor.execute("""
                SELECT m.id, u.nome AS user, m.message, m.created_at
                FROM messages m
                JOIN usuarios u ON u.id = m.user_id
                JOIN conversations c ON c.id = m.conversation_id
                WHERE c.room = %s
                ORDER BY m.created_at ASC
            """, (room_name,))
            mensagens = cursor.fetchall()

        print(f"✅ {len(mensagens)} mensagens carregadas da sala {room_name}")
        return jsonify(mensagens)

    except Exception as e:
        print(f"❌ Erro ao carregar mensagens da sala {room_name}: {e}")
        return jsonify({"error": str(e)}), 500