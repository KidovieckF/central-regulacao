from datetime import datetime
from typing import Optional

from app.domain.status import StatusPedido
from app.extensions import mysql
from app.repositories import pedidos as pedidos_repo


def registrar_historico(pedido_id: int, status: StatusPedido, descricao: Optional[str], usuario_id: int):
    query = """
        INSERT INTO historico_pedidos (pedido_id, status, descricao, criado_por, criado_em)
        VALUES (%s, %s, %s, %s, NOW())
    """
    with mysql.get_cursor() as (_, cursor):
        cursor.execute(
            query,
            (pedido_id, status.value, descricao, usuario_id),  # ✅ REMOVIDO datetime.utcnow()
        )


def atualizar_status(
    pedido_id: int,
    status: StatusPedido,
    usuario_id: int,
    descricao: Optional[str] = None,
    extra_campos: Optional[dict] = None,
):
    campos = {
        "status": status.value,
        "usuario_atualizacao": usuario_id,
        "pendente_recepcao": 0,
    }
    if extra_campos:
        campos.update(extra_campos)
    pedidos_repo.atualizar_campos(pedido_id, campos)
    registrar_historico(pedido_id, status, descricao, usuario_id)