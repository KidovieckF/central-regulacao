# app/repositories/chat.py
import os
import logging
from app.extensions import mysql

logger = logging.getLogger(__name__)

def criar_tabelas():
    # usa o pool definido em app.database.MySQLConnector
        logger.debug("criar_tabelas: iniciando criação/verificação de tabelas")
        with mysql.get_cursor(dictionary=False) as (conn, cur):
                cur.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(200),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    conversation_id INT NULL,
                    sender_id INT NOT NULL,
                    sender_name VARCHAR(150) NOT NULL,
                    text TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX (conversation_id),
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS attachments (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    message_id BIGINT NOT NULL,
                    original_filename VARCHAR(512) NOT NULL,
                    stored_filename VARCHAR(512) NOT NULL,
                    mime_type VARCHAR(255),
                    size INT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX (message_id),
                    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                logger.info("criar_tabelas: tabelas verificadas/criadas com sucesso")
        # commit é feito pelo context manager

def inserir_mensagem(conversation_id, sender_id, sender_name, text):
    logger.debug("inserir_mensagem: conv=%s sender=%s sender_name=%s text_len=%s", conversation_id, sender_id, sender_name, len(text or ""))
    with mysql.get_cursor(dictionary=False) as (conn, cur):
        cur.execute(
            "INSERT INTO messages (conversation_id, sender_id, sender_name, text) VALUES (%s, %s, %s, %s)",
            (conversation_id, sender_id, sender_name, text),
        )
        message_id = cur.lastrowid
    logger.info("inserir_mensagem: inserted message id=%s conv=%s", message_id, conversation_id)
    return message_id

def inserir_anexos(message_id, attachments):
    """attachments: lista de dicts com original_filename, stored_filename, mime_type, size"""
    logger.debug("inserir_anexos: message_id=%s attachments_count=%s", message_id, len(attachments or []))
    with mysql.get_cursor(dictionary=False) as (conn, cur):
        for a in attachments:
            cur.execute(
                """
                INSERT INTO attachments (message_id, original_filename, stored_filename, mime_type, size)
                VALUES (%s, %s, %s, %s)
                """,
                (message_id, a['original_filename'], a['stored_filename'], a.get('mime_type'), a.get('size')),
            )
    logger.info("inserir_anexos: inserted %s attachments for message_id=%s", len(attachments or []), message_id)
    # commit pelo context manager

def listar_mensagens(conversation_id, limit=100):
    logger.debug("listar_mensagens: conv=%s limit=%s", conversation_id, limit)
    with mysql.get_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            """
            SELECT m.id, m.conversation_id, m.sender_id, m.sender_name, m.text, m.created_at
            FROM messages m
            WHERE m.conversation_id = %s
            ORDER BY m.created_at ASC
            LIMIT %s
        """,
            (conversation_id, limit),
        )
        msgs = cur.fetchall() or []
        logger.debug("listar_mensagens: fetched %s messages for conv=%s", len(msgs), conversation_id)
        for msg in msgs:
            cur.execute(
                "SELECT original_filename, stored_filename, mime_type, size FROM attachments WHERE message_id=%s",
                (msg['id'],),
            )
            msg['attachments'] = cur.fetchall() or []
            logger.debug("listar_mensagens: message id=%s attachments=%s", msg.get('id'), len(msg['attachments']))
    logger.info("listar_mensagens: returning %s messages for conv=%s", len(msgs), conversation_id)
    return msgs
