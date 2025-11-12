from app.extensions import mysql

def get_or_create_private_conversation(user_id_1: int, user_id_2: int):
    """Obtém ou cria uma conversa privada entre dois usuários."""
    with mysql.get_cursor(dictionary=True) as (conn, cursor):
        # Verifica se já existe uma conversa entre esses dois usuários
        cursor.execute("""
            SELECT c.id, c.room
            FROM conversations AS c
            JOIN conversation_users cu1 ON cu1.conversation_id = c.id
            JOIN conversation_users cu2 ON cu2.conversation_id = c.id
            WHERE cu1.user_id = %s AND cu2.user_id = %s
        """, (user_id_1, user_id_2))
        existing = cursor.fetchone()

        if existing:
            return existing["id"], existing["room"]

        # Se não existe, cria uma nova room
        room_name = f"private_{user_id_1}_{user_id_2}"
        cursor.execute("INSERT INTO conversations (room) VALUES (%s)", (room_name,))
        conversation_id = cursor.lastrowid

        cursor.execute(
            "INSERT INTO conversation_users (conversation_id, user_id) VALUES (%s, %s)",
            (conversation_id, user_id_1),
        )
        cursor.execute(
            "INSERT INTO conversation_users (conversation_id, user_id) VALUES (%s, %s)",
            (conversation_id, user_id_2),
        )

        print(f"💬 Nova room privada criada: {room_name}")
        return conversation_id, room_name
