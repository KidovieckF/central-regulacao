from datetime import datetime, date, time
from typing import Optional

from app.domain.status import StatusPedido
from app.extensions import mysql
from app.repositories import pedidos as pedidos_repo
from .pedidos_service import atualizar_status, registrar_historico


def registrar_tentativa(
    pedido_id: int,
    usuario_id: int,
    resultado: str,
    resumo: str,
    data_exame: Optional[date],
    horario_exame: Optional[time],
    local_exame: Optional[str],
):
    with mysql.get_cursor() as (_, cursor):
        cursor.execute("SELECT status, tentativas_contato, tipo_regulacao FROM pedidos WHERE id = %s", (pedido_id,))
        pedido = cursor.fetchone()
        if not pedido:
            raise ValueError("Pedido não encontrado.")

        nova_tentativa = (pedido["tentativas_contato"] or 0) + 1

        cursor.execute(
            """
            INSERT INTO tentativas_contato
            (pedido_id, tentativa_numero, resultado, resumo, data_tentativa, usuario_id)
            VALUES (%s, %s, %s, %s, NOW(), %s)
            """,
            (pedido_id, nova_tentativa, resultado, resumo, usuario_id),  # ✅ REMOVIDO datetime.utcnow()
        )

        cursor.execute(
            "UPDATE pedidos SET tentativas_contato=%s WHERE id=%s",
            (nova_tentativa, pedido_id),
        )

    if resultado == "contato_sucesso":
        extra = {
            "data_exame": data_exame,
            "horario_exame": horario_exame,
            "local_exame": local_exame,
            "tentativas_contato": nova_tentativa,
        }
        status_final = StatusPedido.AGENDAMENTO_CONFIRMADO
        atualizar_status(
            pedido_id=pedido_id,
            status=status_final,
            usuario_id=usuario_id,
            descricao=f"Contato confirmado. Exame agendado para {data_exame} às {horario_exame} em {local_exame}.",
            extra_campos=extra,
        )
    else:
        if resultado == "sem_contato" and nova_tentativa >= 3:
            extra = {
                "pendente_recepcao": 1,
                "tipo_regulacao": None,
                "prioridade": None,
            }
            atualizar_status(
                pedido_id=pedido_id,
                status=StatusPedido.DEVOLVIDO_SEM_CONTATO,
                usuario_id=usuario_id,
                descricao="Três tentativas sem sucesso. Pedido devolvido à recepção da unidade.",
                extra_campos=extra,
            )
        else:
            atualizar_status(
                pedido_id=pedido_id,
                status=StatusPedido.AGENDAMENTO_EM_ANDAMENTO,
                usuario_id=usuario_id,
                descricao=f"Tentativa registrada com resultado: {resultado}.",
                extra_campos={"tentativas_contato": nova_tentativa},
            )