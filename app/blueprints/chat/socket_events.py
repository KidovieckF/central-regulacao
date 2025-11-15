from flask_socketio import emit, join_room
from flask_login import current_user
from app.extensions import socketio, mysql
import json

@socketio.on('connect')
def on_connect():
    if current_user.is_authenticated:
        try:
            with mysql.get_cursor() as (conn, cursor):
                cursor.execute("""
                    UPDATE usuarios 
                    SET is_online = TRUE, last_seen = NOW()
                    WHERE id = %s
                """, (current_user.id,))  # ✅ USAR NOW()
                conn.commit()
            
            emit('user_status_changed', {
                'user_id': current_user.id,
                'user_name': current_user.nome,
                'is_online': True,
                'event': 'connected'
            }, broadcast=True, include_self=False)
            
            print(f"✅ {current_user.nome} ficou online")
        except Exception as e:
            print(f"❌ Erro ao marcar como online: {e}")

@socketio.on('disconnect')
def on_disconnect():
    if current_user.is_authenticated:
        try:
            with mysql.get_cursor() as (conn, cursor):
                cursor.execute("""
                    UPDATE usuarios 
                    SET is_online = FALSE, last_seen = NOW()
                    WHERE id = %s
                """, (current_user.id,))  # ✅ USAR NOW()
                conn.commit()
            
            emit('user_status_changed', {
                'user_id': current_user.id,
                'user_name': current_user.nome,
                'is_online': False,
                'event': 'disconnected'
            }, broadcast=True)
            
            print(f"❌ {current_user.nome} ficou offline")
        except Exception as e:
            print(f"❌ Erro ao marcar como offline: {e}")

@socketio.on('heartbeat')
def on_heartbeat():
    if current_user.is_authenticated:
        try:
            with mysql.get_cursor() as (conn, cursor):
                cursor.execute("""
                    UPDATE usuarios 
                    SET last_seen = NOW()
                    WHERE id = %s
                """, (current_user.id,))  # ✅ USAR NOW()
                conn.commit()
        except Exception as e:
            print(f"❌ Erro no heartbeat: {e}")

@socketio.on("join")
def handle_join(data):
    room = data.get("room")
    if not room:
        print("⚠️ Evento JOIN sem room.")
        return
    join_room(room)
    print(f"👥 {current_user.nome if current_user.is_authenticated else 'Anônimo'} entrou na sala {room}")

@socketio.on("send_message")
def handle_send_message(data):
    print("📩 Evento send_message recebido:", data)
    try:
        room = data.get("room")
        conversation_id = data.get("conversation_id")
        message_text = (data.get("message") or "").strip()
        attachments = data.get("attachments", [])

        if not room or not conversation_id or (not message_text and not attachments):
            print("⚠️ Dados incompletos para enviar mensagem.")
            return

        user_id = current_user.id if current_user.is_authenticated else None
        user_name = current_user.nome if current_user.is_authenticated else "Anônimo"

        # Salvar mensagem + anexos no banco
        with mysql.get_cursor(dictionary=True) as (conn, cursor):
            cursor.execute(
                """
                INSERT INTO messages (conversation_id, user_id, message, created_at)
                VALUES (%s, %s, %s, NOW())
                """,
                (conversation_id, user_id, message_text or ""),
            )
            
            message_id = cursor.lastrowid
            
            # ✅ BUSCAR TIMESTAMP CORRETO DA MENSAGEM INSERIDA
            cursor.execute("SELECT created_at FROM messages WHERE id = %s", (message_id,))
            message_row = cursor.fetchone()
            message_timestamp = message_row['created_at']
            
            # Salvar anexos
            saved_attachments = []
            if attachments:
                for attachment in attachments:
                    cursor.execute("""
                        INSERT INTO attachments (message_id, original_filename, stored_filename, mime_type, size, created_at)
                        VALUES (%s, %s, %s, %s, %s, NOW())
                    """, (
                        message_id,
                        attachment.get('original_name', attachment.get('filename')),
                        attachment['filename'],
                        attachment.get('type', attachment.get('mime_type')),
                        attachment.get('size', 0)
                    ))
                    
                    saved_attachments.append({
                        'id': cursor.lastrowid,
                        'original_filename': attachment.get('original_name', attachment.get('filename')),
                        'stored_filename': attachment['filename'],
                        'mime_type': attachment.get('type', attachment.get('mime_type')),
                        'size': attachment.get('size', 0)
                    })
            
            # Atualizar last_seen do usuário
            if current_user.is_authenticated:
                cursor.execute("""
                    UPDATE usuarios 
                    SET last_seen = NOW()
                    WHERE id = %s
                """, (current_user.id,))  # ✅ USAR NOW()
            
            conn.commit()

        print(f"✅ Mensagem salva na conversa {conversation_id} por {user_name}")

        # ✅ EMITIR COM TIMESTAMP DO BANCO
        emit(
            "message",
            {
                "conversation_id": conversation_id,
                "room": room,
                "user": user_name,
                "msg": message_text,
                "attachments": saved_attachments,
                "timestamp": message_timestamp.isoformat(),  # ✅ TIMESTAMP CORRETO
            },
            room=room,
        )

        preview_text = message_text or f"📎 {len(saved_attachments)} arquivo(s)"
        emit(
            "update_conversations",
            {
                "conversation_id": conversation_id,
                "last_message": preview_text,
                "sender": user_name,
            },
            broadcast=True,
        )

    except Exception as e:
        print(f"❌ Erro ao processar mensagem: {e}")
        emit("error", {"error": str(e)})