from typing import List, Optional
from app.extensions import mysql

def listar_todas() -> List[dict]:
    """Lista todas as consultas para administração"""
    query = """
        SELECT id, nome, especialidade, descricao, ativo, criado_em
        FROM consultas 
        ORDER BY especialidade
    """
    with mysql.get_cursor(dictionary=True) as (_, cursor):
        cursor.execute(query)
        return cursor.fetchall()

def listar_ativas() -> List[dict]:
    """Lista apenas consultas ativas para recepção"""
    query = """
        SELECT id, especialidade, descricao
        FROM consultas 
        WHERE ativo = 1 
        ORDER BY especialidade
    """
    with mysql.get_cursor(dictionary=True) as (_, cursor):
        cursor.execute(query)
        return cursor.fetchall()

def obter_por_id(consulta_id: int) -> Optional[dict]:
    """Obtém consulta por ID"""
    query = """
        SELECT id, nome, especialidade, descricao, ativo, criado_em
        FROM consultas 
        WHERE id = %s
    """
    with mysql.get_cursor(dictionary=True) as (_, cursor):
        cursor.execute(query, (consulta_id,))
        return cursor.fetchone()

def criar_consulta(especialidade: str, descricao: str = None) -> int:
    """Cria nova consulta"""
    nome = f"Consulta {especialidade}"
    query = """
        INSERT INTO consultas (nome, especialidade, descricao, ativo, criado_em)
        VALUES (%s, %s, %s, 1, NOW())
    """
    with mysql.get_cursor() as (conn, cursor):
        cursor.execute(query, (nome, especialidade, descricao))
        conn.commit()
        return cursor.lastrowid

def atualizar_consulta(consulta_id: int, especialidade: str, descricao: str = None):
    """Atualiza consulta existente"""
    nome = f"Consulta {especialidade}"
    query = """
        UPDATE consultas 
        SET nome = %s, especialidade = %s, descricao = %s
        WHERE id = %s
    """
    with mysql.get_cursor() as (conn, cursor):
        cursor.execute(query, (nome, especialidade, descricao, consulta_id))
        conn.commit()

def alterar_status(consulta_id: int, ativo: bool):
    """Altera status da consulta"""
    query = "UPDATE consultas SET ativo = %s WHERE id = %s"
    with mysql.get_cursor() as (conn, cursor):
        cursor.execute(query, (1 if ativo else 0, consulta_id))
        conn.commit()