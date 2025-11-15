from contextlib import contextmanager
from typing import Generator, Tuple

import mysql.connector
from mysql.connector import pooling

from werkzeug.security import generate_password_hash

from .schema import SCHEMA_STATEMENTS

DEFAULT_ADMIN = {
    "nome": "Leandro da Silva",
    "cpf": "39927600810",
    "senha": "dG4rTALaq8",
    "role": "admin",
}


class MySQLConnector:
    def __init__(self):
        self.pool: pooling.MySQLConnectionPool | None = None

    def init_app(self, app):
        if self.pool is not None:
            return

        self.pool = pooling.MySQLConnectionPool(
            pool_name=app.config["MYSQL_POOL_NAME"],
            pool_size=app.config["MYSQL_POOL_SIZE"],
            pool_reset_session=app.config["MYSQL_POOL_RESET_SESSION"],
            host=app.config["MYSQL_HOST"],
            port=app.config["MYSQL_PORT"],
            user=app.config["MYSQL_USER"],
            password=app.config["MYSQL_PASSWORD"],
            database=app.config["MYSQL_DATABASE"],
            autocommit=False,
            time_zone='-03:00',  # ✅ TIMEZONE BRASÍLIA
            sql_mode='',  # ✅ OPCIONAL: desabilitar modo estrito se necessário
        )

        app.logger.info("Pool de conexões MySQL inicializado.")
        self.ensure_schema(app.logger)

    def ensure_schema(self, logger=None):
        if not self.pool:
            raise RuntimeError("Pool de conexões não inicializado.")

        with self.get_cursor(dictionary=False) as (connection, cursor):
            # ✅ DEFINIR TIMEZONE LOGO APÓS CONECTAR
            cursor.execute("SET time_zone = '-03:00'")
            
            for statement in SCHEMA_STATEMENTS:
                cursor.execute(statement)

        if logger:
            logger.info("Schema do banco verificado/criado com sucesso.")

        self.ensure_default_admin(logger)

    def ensure_default_admin(self, logger=None):
        if not self.pool:
            raise RuntimeError("Pool de conexões não inicializado.")

        with self.get_cursor(dictionary=True) as (_, cursor):
            cursor.execute(
                "SELECT id FROM usuarios WHERE cpf = %s LIMIT 1",
                (DEFAULT_ADMIN["cpf"],),
            )
            existing = cursor.fetchone()

            if existing:
                if logger:
                    logger.info(
                        "Usuário administrador padrão já existe (CPF: %s).",
                        DEFAULT_ADMIN["cpf"],
                    )
                return

            senha_hash = generate_password_hash(
                DEFAULT_ADMIN["senha"],
                method="pbkdf2:sha256",
                salt_length=12,
            )

            cursor.execute(
                """
                INSERT INTO usuarios (nome, cpf, senha_hash, role, unidade_id, ativo)
                VALUES (%s, %s, %s, %s, NULL, 1)
                """,
                (
                    DEFAULT_ADMIN["nome"],
                    DEFAULT_ADMIN["cpf"],
                    senha_hash,
                    DEFAULT_ADMIN["role"],
                ),
            )

        if logger:
            logger.info("Usuário administrador padrão criado com sucesso.")

    def get_connection(self) -> mysql.connector.MySQLConnection:
        if not self.pool:
            raise RuntimeError("Pool de conexões não inicializado.")
        connection = self.pool.get_connection()
        # ✅ DEFINIR TIMEZONE EM CADA CONEXÃO
        cursor = connection.cursor()
        cursor.execute("SET time_zone = '-03:00'")
        cursor.close()
        return connection

    @contextmanager
    def get_cursor(
        self, *, dictionary: bool = True
    ) -> Generator[
        Tuple[mysql.connector.MySQLConnection, mysql.connector.cursor.MySQLCursor], None, None
    ]:
        connection = self.get_connection()
        cursor = connection.cursor(dictionary=dictionary)
        try:
            yield connection, cursor
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()