from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.extensions import mysql
from datetime import datetime, timedelta
import os
import json
from werkzeug.utils import secure_filename

# =====================================
# Configurações
# =====================================
UPLOAD_FOLDER = "app/static/uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "pdf", "docx", "txt", "xlsx", "xls", "zip", "rar"}

chat_blueprint = Blueprint("chat", __name__)

# ---------------------------------------
# Funções auxiliares
# ---------------------------------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def update_user_status(user_id, is_online=True):
    """Atualiza o status de presença do usuário"""
    with mysql.get_cursor() as (_, cursor):
        cursor.execute("""
            UPDATE usuarios 
            SET is_online = %s, last_seen = %s 
            WHERE id = %s
        """, (is_online, datetime.now(), user_id))

def get_user_status(user_id):
    """Retorna o status de um usuário"""
    with mysql.get_cursor(dictionary=True) as (_, cursor):
        cursor.execute("""
            SELECT is_online, last_seen 
            FROM usuarios 
            WHERE id = %s
        """, (user_id,))
        result = cursor.fetchone()
        
        if not result:
            return {"is_online": False, "last_seen": None}
            
        # Se last_seen é muito antigo (>5 min), consideramos offline
        if result['last_seen']:
            time_diff = datetime.now() - result['last_seen']
            if time_diff > timedelta(minutes=5):
                update_user_status(user_id, False)
                return {"is_online": False, "last_seen": result['last_seen']}
        
        return result

def get_or_create_conversation(user_a_id, user_b_id):
    """Cria ou retorna uma conversa única entre dois usuários."""
    with mysql.get_cursor(dictionary=True) as (_, cursor):
        cursor.execute("""
            SELECT c.id, c.room
            FROM conversations c
            JOIN conversation_participants p1 ON p1.conversation_id = c.id
            JOIN conversation_participants p2 ON p2.conversation_id = c.id
            WHERE p1.user_id = %s AND p2.user_id = %s
            LIMIT 1
        """, (user_a_id, user_b_id))
        existing = cursor.fetchone()
        if existing:
            return existing["id"], existing["room"]

        room_name = f"chat_{user_a_id}_{user_b_id}"
        cursor.execute("INSERT INTO conversations (room) VALUES (%s)", (room_name,))
        conv_id = cursor.lastrowid
        cursor.executemany("""
            INSERT INTO conversation_participants (conversation_id, user_id)
            VALUES (%s, %s)
        """, [(conv_id, user_a_id), (conv_id, user_b_id)])
        return conv_id, room_name

# ==========================================================
# 🔹 Página principal do chat
# ==========================================================
@chat_blueprint.route("/chat")
@login_required
def chat():
    # Marcar usuário como online ao acessar o chat
    update_user_status(current_user.id, True)
    
    with mysql.get_cursor(dictionary=True) as (_, cursor):
        cursor.execute("""
            SELECT 
                c.id,
                c.room,
                COALESCE(
                    NULLIF(
                        GROUP_CONCAT(DISTINCT CASE WHEN u.id != %s THEN u.nome END SEPARATOR ', '),
                        ''
                    ),
                    u_self.nome
                ) AS participantes,
                MAX(m.created_at) AS ultima_mensagem,
                -- Pegar o ID do outro participante para verificar status
                (SELECT user_id FROM conversation_participants 
                 WHERE conversation_id = c.id AND user_id != %s LIMIT 1) AS outro_user_id
            FROM conversations c
            JOIN conversation_participants p ON c.id = p.conversation_id
            JOIN usuarios u ON p.user_id = u.id
            JOIN conversation_participants p_self ON c.id = p_self.conversation_id
            JOIN usuarios u_self ON p_self.user_id = u_self.id AND u_self.id = %s
            LEFT JOIN messages m ON m.conversation_id = c.id
            WHERE p_self.user_id = %s
            GROUP BY c.id
            ORDER BY ultima_mensagem DESC, c.created_at DESC
        """, (current_user.id, current_user.id, current_user.id, current_user.id))

        conversas = cursor.fetchall()

    return render_template(
        "chat/chat.html",
        current_user=current_user,
        role=current_user.role,
        conversas=conversas,
    )

# ==========================================================
# 🔹 API: status de usuário
# ==========================================================
@chat_blueprint.route("/chat/status/<int:user_id>")
@login_required
def get_user_online_status(user_id):
    """Retorna status online/offline de um usuário"""
    status = get_user_status(user_id)
    
    # Calcular tempo offline se não está online
    last_seen_text = "nunca"
    if status['last_seen'] and not status['is_online']:
        time_diff = datetime.now() - status['last_seen']
        if time_diff.days > 0:
            last_seen_text = f"{time_diff.days}d atrás"
        elif time_diff.seconds > 3600:
            hours = time_diff.seconds // 3600
            last_seen_text = f"{hours}h atrás"
        elif time_diff.seconds > 60:
            minutes = time_diff.seconds // 60
            last_seen_text = f"{minutes}min atrás"
        else:
            last_seen_text = "agora mesmo"
    
    return jsonify({
        "is_online": status['is_online'],
        "last_seen_text": last_seen_text
    })

# ==========================================================
# 🔹 API: heartbeat para manter usuário online
# ==========================================================
@chat_blueprint.route("/chat/heartbeat", methods=["POST"])
@login_required
def heartbeat():
    """Atualiza o timestamp de atividade do usuário"""
    update_user_status(current_user.id, True)
    return jsonify({"status": "ok"})

# ==========================================================
# 🔹 Buscar mensagens de uma conversa COM ANEXOS
# ==========================================================
@chat_blueprint.route("/chat/mensagens/<int:conversation_id>")
@login_required
def get_messages(conversation_id):
    try:
        with mysql.get_cursor(dictionary=True) as (_, cursor):
            cursor.execute("""
                SELECT 
                    m.id as message_id,
                    u.nome AS user, 
                    m.message, 
                    m.created_at
                FROM messages m
                JOIN usuarios u ON u.id = m.user_id
                WHERE m.conversation_id = %s
                ORDER BY m.created_at ASC
            """, (conversation_id,))
            
            mensagens = cursor.fetchall()
            
            # Buscar anexos para cada mensagem
            for msg in mensagens:
                cursor.execute("""
                    SELECT id, original_filename, stored_filename, mime_type, size
                    FROM attachments
                    WHERE message_id = %s
                """, (msg['message_id'],))
                
                msg['attachments'] = cursor.fetchall()
        
        return jsonify(mensagens)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================================
# 🔹 Upload de arquivos MELHORADO
# ==========================================================
@chat_blueprint.route("/chat/upload", methods=["POST"])
@login_required
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "Nenhum arquivo"}), 400
    
    file = request.files["file"]
    
    if not file or file.filename == '':
        return jsonify({"error": "Nenhum arquivo selecionado"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({"error": "Tipo de arquivo não permitido"}), 400
    
    try:
        # Gerar nome único para evitar conflitos
        filename = secure_filename(file.filename)
        name, ext = os.path.splitext(filename)
        unique_filename = f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
        
        # Criar diretório se não existir
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        # Salvar arquivo
        filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
        file.save(filepath)
        
        return jsonify({
            "filename": unique_filename,
            "original_filename": filename,
            "size": os.path.getsize(filepath),
            "mime_type": file.content_type
        }), 201
        
    except Exception as e:
        print(f"❌ Erro no upload: {e}")
        return jsonify({"error": "Erro ao fazer upload do arquivo"}), 500

# ==========================================================
# 🔹 API: lista de usuários com status online
# ==========================================================
@chat_blueprint.route("/chat/usuarios")
@login_required
def get_users():
    role = current_user.role
    query = """
        SELECT id, nome, role, is_online, last_seen 
        FROM usuarios 
        WHERE ativo=1 AND id != %s
    """
    params = [current_user.id]

    if role == "recepcao":
        query += " AND role != 'recepcao'"

    query += " ORDER BY is_online DESC, nome ASC"

    with mysql.get_cursor(dictionary=True) as (_, cursor):
        cursor.execute(query, params)
        usuarios = cursor.fetchall()
        
        # Processar status para cada usuário
        for usuario in usuarios:
            if usuario['last_seen']:
                time_diff = datetime.now() - usuario['last_seen']
                # Auto-desconectar se > 5 minutos
                if time_diff > timedelta(minutes=5):
                    usuario['is_online'] = False
                    update_user_status(usuario['id'], False)
    
    return jsonify(usuarios)

# ==========================================================
# 🔹 API: lista de conversas com status
# ==========================================================
@chat_blueprint.route("/chat/conversas")
@login_required
def list_conversations():
    with mysql.get_cursor(dictionary=True) as (_, cursor):
        cursor.execute("""
            SELECT 
                c.id,
                c.room,
                COALESCE(
                    NULLIF(
                        GROUP_CONCAT(DISTINCT CASE WHEN u.id != %s THEN u.nome END SEPARATOR ', '),
                        ''
                    ),
                    u_self.nome
                ) AS participantes,
                MAX(m.created_at) AS ultima_mensagem,
                (
                    SELECT 
                        CASE 
                            WHEN m2.message IS NOT NULL AND m2.message != '' THEN m2.message
                            WHEN (SELECT COUNT(*) FROM attachments a WHERE a.message_id = m2.id) > 0 
                            THEN CONCAT('📎 ', (SELECT COUNT(*) FROM attachments a WHERE a.message_id = m2.id), ' arquivo(s)')
                            ELSE 'Mensagem'
                        END
                    FROM messages m2
                    WHERE m2.conversation_id = c.id
                    ORDER BY m2.created_at DESC
                    LIMIT 1
                ) AS ultima_msg_texto,
                -- Status do outro usuário
                (SELECT u2.is_online FROM usuarios u2 
                 JOIN conversation_participants p2 ON u2.id = p2.user_id
                 WHERE p2.conversation_id = c.id AND u2.id != %s LIMIT 1) as outro_user_online
            FROM conversations c
            JOIN conversation_participants p ON c.id = p.conversation_id
            JOIN usuarios u ON p.user_id = u.id
            JOIN conversation_participants p_self ON c.id = p_self.conversation_id
            JOIN usuarios u_self ON p_self.user_id = u_self.id AND u_self.id = %s
            LEFT JOIN messages m ON m.conversation_id = c.id
            WHERE p_self.user_id = %s
            GROUP BY c.id
            ORDER BY ultima_mensagem DESC, c.created_at DESC
        """, (current_user.id, current_user.id, current_user.id, current_user.id))

        conversas = cursor.fetchall()

    return jsonify(conversas)

# ==========================================================
# 🔹 API: obter ID do outro participante da conversa
# ==========================================================
@chat_blueprint.route("/chat/conversa/<int:conversation_id>/participante")
@login_required
def get_other_participant(conversation_id):
    """Retorna o ID do outro participante da conversa"""
    with mysql.get_cursor(dictionary=True) as (_, cursor):
        cursor.execute("""
            SELECT user_id, u.nome, u.is_online, u.last_seen
            FROM conversation_participants cp
            JOIN usuarios u ON u.id = cp.user_id
            WHERE cp.conversation_id = %s AND cp.user_id != %s
            LIMIT 1
        """, (conversation_id, current_user.id))
        
        participante = cursor.fetchone()
        if not participante:
            return jsonify({"error": "Participante não encontrado"}), 404
        
        # Calcular texto do last_seen
        last_seen_text = "online"
        if not participante['is_online'] and participante['last_seen']:
            time_diff = datetime.now() - participante['last_seen']
            if time_diff.days > 0:
                last_seen_text = f"visto há {time_diff.days}d"
            elif time_diff.seconds > 3600:
                hours = time_diff.seconds // 3600
                last_seen_text = f"visto há {hours}h"
            elif time_diff.seconds > 60:
                minutes = time_diff.seconds // 60
                last_seen_text = f"visto há {minutes}min"
            else:
                last_seen_text = "visto agora mesmo"
        
        return jsonify({
            "user_id": participante['user_id'],
            "nome": participante['nome'],
            "is_online": participante['is_online'],
            "last_seen_text": last_seen_text
        })

# ==========================================================
# 🔹 Criar/obter conversa 1:1
# ==========================================================
@chat_blueprint.route("/chat/conversa/<int:target_id>", methods=["POST"])
@login_required
def open_conversation(target_id):
    conv_id, room = get_or_create_conversation(current_user.id, target_id)
    return jsonify({"conversation_id": conv_id, "room": room})