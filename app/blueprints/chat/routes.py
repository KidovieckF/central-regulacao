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
# Funções auxiliares CORRIGIDAS
# ---------------------------------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def update_user_status(user_id, is_online=True):
    """Atualiza o status de presença do usuário"""
    with mysql.get_cursor() as (_, cursor):
        cursor.execute("""
            UPDATE usuarios 
            SET is_online = %s, last_seen = NOW()
            WHERE id = %s
        """, (is_online, user_id))  # ✅ USAR NOW() EM VEZ DE datetime.now()

def get_user_status(user_id):
    """Retorna o status de um usuário"""
    with mysql.get_cursor(dictionary=True) as (_, cursor):
        cursor.execute("""
            SELECT is_online, last_seen,
                   TIMESTAMPDIFF(MINUTE, last_seen, NOW()) as minutes_ago
            FROM usuarios 
            WHERE id = %s
        """, (user_id,))
        result = cursor.fetchone()
        
        if not result:
            return {"is_online": False, "last_seen": None}
            
        # Se last_seen é muito antigo (>5 min), consideramos offline
        if result.get('minutes_ago', 0) > 5:
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
        cursor.execute("INSERT INTO conversations (room, created_at) VALUES (%s, NOW())", (room_name,))  # ✅ USAR NOW()
        conv_id = cursor.lastrowid
        cursor.executemany("""
            INSERT INTO conversation_participants (conversation_id, user_id, joined_at)
            VALUES (%s, %s, NOW())
        """, [(conv_id, user_a_id), (conv_id, user_b_id)])  # ✅ USAR NOW()
        return conv_id, room_name

# ==========================================================
# 🔹 Página principal do chat
# ==========================================================
@chat_blueprint.route("/chat")
@login_required
def chat():
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
    with mysql.get_cursor(dictionary=True) as (_, cursor):
        cursor.execute("""
            SELECT is_online, last_seen,
                   TIMESTAMPDIFF(MINUTE, last_seen, NOW()) as minutes_ago,
                   TIMESTAMPDIFF(HOUR, last_seen, NOW()) as hours_ago,
                   TIMESTAMPDIFF(DAY, last_seen, NOW()) as days_ago
            FROM usuarios 
            WHERE id = %s
        """, (user_id,))
        result = cursor.fetchone()
        
        if not result:
            return jsonify({"is_online": False, "last_seen_text": "nunca"})
        
        # ✅ CALCULAR TEMPO USANDO TIMESTAMPDIFF DO MYSQL
        last_seen_text = "online"
        if not result['is_online']:
            days_ago = result.get('days_ago', 0)
            hours_ago = result.get('hours_ago', 0)
            minutes_ago = result.get('minutes_ago', 0)
            
            if days_ago > 0:
                last_seen_text = f"{days_ago}d atrás"
            elif hours_ago > 0:
                last_seen_text = f"{hours_ago}h atrás"
            elif minutes_ago > 0:
                last_seen_text = f"{minutes_ago}min atrás"
            else:
                last_seen_text = "agora mesmo"
    
    return jsonify({
        "is_online": result['is_online'],
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
            
            mensagens = cursor.fetchall() or []
            
            # Buscar anexos para cada mensagem
            for msg in mensagens:
                cursor.execute("""
                    SELECT id, original_filename, stored_filename, mime_type, size
                    FROM attachments
                    WHERE message_id = %s
                """, (msg['message_id'],))
                
                msg['attachments'] = cursor.fetchall() or []
        
        return jsonify(mensagens)
    except Exception as e:
        print(f"❌ Erro ao carregar mensagens: {e}")
        return jsonify({"error": str(e)}), 500

# ==========================================================
# 🔹 Upload de arquivos
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
        filename = secure_filename(file.filename)
        name, ext = os.path.splitext(filename)
        
        # ✅ USAR TIMESTAMP DO MYSQL PARA CONSISTÊNCIA
        with mysql.get_cursor(dictionary=True) as (_, cursor):
            cursor.execute("SELECT DATE_FORMAT(NOW(), '%Y%m%d_%H%i%s') as timestamp_mysql")
            timestamp = cursor.fetchone()['timestamp_mysql']
        
        unique_filename = f"{name}_{timestamp}{ext}"
        
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
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
        SELECT id, nome, role, is_online, last_seen,
               TIMESTAMPDIFF(MINUTE, last_seen, NOW()) as minutes_ago
        FROM usuarios 
        WHERE ativo=1 AND id != %s
    """
    params = [current_user.id]

    if role == "recepcao":
        query += " AND role != 'recepcao'"

    query += " ORDER BY is_online DESC, nome ASC"

    with mysql.get_cursor(dictionary=True) as (_, cursor):
        cursor.execute(query, params)
        usuarios = cursor.fetchall() or []
        
        # ✅ PROCESSAR STATUS USANDO TIMESTAMPDIFF DO MYSQL
        for usuario in usuarios:
            minutes_ago = usuario.get('minutes_ago', 0) or 0
            if minutes_ago > 5:  # > 5 minutos
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
                    SELECT COALESCE(m2.message, '📎 Arquivo')
                    FROM messages m2
                    WHERE m2.conversation_id = c.id
                    ORDER BY m2.created_at DESC
                    LIMIT 1
                ) AS ultima_msg_texto,
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

        conversas = cursor.fetchall() or []

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
            SELECT user_id, u.nome, u.is_online, u.last_seen,
                   TIMESTAMPDIFF(MINUTE, u.last_seen, NOW()) as minutes_ago,
                   TIMESTAMPDIFF(HOUR, u.last_seen, NOW()) as hours_ago,
                   TIMESTAMPDIFF(DAY, u.last_seen, NOW()) as days_ago
            FROM conversation_participants cp
            JOIN usuarios u ON u.id = cp.user_id
            WHERE cp.conversation_id = %s AND cp.user_id != %s
            LIMIT 1
        """, (conversation_id, current_user.id))
        
        participante = cursor.fetchone()
        if not participante:
            return jsonify({"error": "Participante não encontrado"}), 404
        
        # ✅ CALCULAR TEMPO USANDO TIMESTAMPDIFF DO MYSQL
        last_seen_text = "online"
        if not participante['is_online']:
            days_ago = participante.get('days_ago', 0) or 0
            hours_ago = participante.get('hours_ago', 0) or 0
            minutes_ago = participante.get('minutes_ago', 0) or 0
            
            if days_ago > 0:
                last_seen_text = f"visto há {days_ago}d"
            elif hours_ago > 0:
                last_seen_text = f"visto há {hours_ago}h"
            elif minutes_ago > 0:
                last_seen_text = f"visto há {minutes_ago}min"
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