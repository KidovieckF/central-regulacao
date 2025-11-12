from flask_socketio import emit
from flask_socketio import join_room
from flask_login import current_user
from app.extensions import socketio, mysql


@socketio.on('join')
def handle_join(data):
    room = data.get('room')
    join_room(room)
    print(f"👥 {current_user.nome if current_user.is_authenticated else 'Anônimo'} entrou na sala {room}")

@socketio.on("send_message")
def handle_send_message(data):
    print("📩 Evento send_message recebido:", data)
    try:
        room = data.get("room", "geral")
        message_text = data.get("message", "").strip()

        if not message_text:
            print("⚠️ Mensagem vazia.")
            return

        # ✅ usa o contexto do pool corretamente
        with mysql.get_cursor(dictionary=True) as (conn, cursor):
            # Verifica se sala existe
            cursor.execute("SELECT id FROM conversations WHERE room = %s", (room,))
            conversation = cursor.fetchone()

            if not conversation:
                cursor.execute(
                    "INSERT INTO conversations (room, created_at) VALUES (%s, NOW())",
                    (room,),
                )
                conversation_id = cursor.lastrowid
                print(f"💬 Nova conversa criada: {conversation_id}")
            else:
                conversation_id = conversation["id"]

            # Insere mensagem
            cursor.execute(
                """
                INSERT INTO messages (conversation_id, user_id, message, created_at)
                VALUES (%s, %s, %s, NOW())
                """,
                (
                    conversation_id,
                    current_user.id if current_user.is_authenticated else 1,
                    message_text,
                ),
            )

        print(f"✅ Mensagem salva no banco: {message_text}")

        # Emite a mensagem para todos conectados
        emit(
            "message",
            {
                "user": current_user.nome
                if current_user.is_authenticated
                else "Anônimo",
                "msg": message_text,
            },
            broadcast=True,
        )

    except Exception as e:
        print("❌ Erro ao processar mensagem:", e)
