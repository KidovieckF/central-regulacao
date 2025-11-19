from typing import List, Optional
from app.domain.status import StatusPedido
from app.extensions import mysql


# ==========================================================
# 🧾 Criar Pedido (Exame ou Consulta) - CORRIGIDO
# ==========================================================
def criar_pedido(dados: dict) -> int:
    # Determinar tipo de solicitação baseado nos IDs
    tipo_solicitacao = 'consulta' if dados.get("consulta_id") else 'exame'
    
    query = """
        INSERT INTO pedidos
        (paciente_id, exame_id, consulta_id, unidade_id, tipo_solicitacao, status, tipo_regulacao, prioridade,
         usuario_criacao, usuario_atualizacao, observacoes, pendente_recepcao)
        VALUES (%s, %s, %s, %s, %s, %s, NULL, NULL, %s, %s, %s, 0)
    """
    valores = (
        dados["paciente_id"],
        dados.get("exame_id"),
        dados.get("consulta_id"),
        dados["unidade_id"],
        tipo_solicitacao,  # ✅ ADICIONAR TIPO_SOLICITACAO
        StatusPedido.AGUARDANDO_TRIAGEM.value,
        dados["usuario_criacao"],
        dados["usuario_criacao"],
        dados.get("observacoes"),
    )
    with mysql.get_cursor() as (_, cursor):
        cursor.execute(query, valores)
        return cursor.lastrowid


# ==========================================================
# 🛠 Atualizar campos
# ==========================================================
def atualizar_campos(pedido_id: int, campos: dict):
    set_clause = ", ".join([f"{coluna}=%s" for coluna in campos.keys()])
    valores = list(campos.values())
    valores.append(pedido_id)
    query = f"UPDATE pedidos SET {set_clause}, data_atualizacao=NOW() WHERE id=%s"
    with mysql.get_cursor() as (_, cursor):
        cursor.execute(query, tuple(valores))


# ==========================================================
# 🔎 Obter Pedido por ID
# ==========================================================
def obter_por_id(pedido_id: int) -> Optional[dict]:
    query = """
        SELECT p.*,
               pa.nome AS paciente_nome,
               pa.cpf AS paciente_cpf,
               pa.telefone_principal,
               pa.telefone_secundario,
               pa.email,
               pa.cartao_sus,
               pa.data_nascimento,
               e.nome AS exame_nome,
               c.nome AS consulta_nome,
               c.especialidade AS consulta_especialidade,
               un.nome AS unidade_nome
        FROM pedidos p
        JOIN pacientes pa ON pa.id = p.paciente_id
        LEFT JOIN exames e ON e.id = p.exame_id
        LEFT JOIN consultas c ON c.id = p.consulta_id
        JOIN unidades_saude un ON un.id = p.unidade_id
        WHERE p.id = %s
    """
    with mysql.get_cursor(dictionary=True) as (_, cursor):
        cursor.execute(query, (pedido_id,))
        return cursor.fetchone()


# ==========================================================
# 📋 Listar por unidade
# ==========================================================
def listar_por_unidade(unidade_id: int) -> List[dict]:
    query = """
        SELECT p.id,
               p.status,
               p.tipo_regulacao,
               p.prioridade,
               p.tipo_solicitacao,
               p.data_solicitacao,
               p.pendente_recepcao,
               pa.nome AS paciente_nome,
               pa.cpf AS paciente_cpf,
               COALESCE(e.nome, c.especialidade) AS nome_solicitacao
        FROM pedidos p
        JOIN pacientes pa ON pa.id = p.paciente_id
        LEFT JOIN exames e ON e.id = p.exame_id
        LEFT JOIN consultas c ON c.id = p.consulta_id
        WHERE p.unidade_id = %s
        ORDER BY p.data_atualizacao DESC
    """
    with mysql.get_cursor(dictionary=True) as (_, cursor):
        cursor.execute(query, (unidade_id,))
        return cursor.fetchall()


# ==========================================================
# 📋 Listar pedidos devolvidos por unidade
# ==========================================================
def listar_devolvidos_por_unidade(unidade_id: int) -> List[dict]:
    query = """
        SELECT p.id,
               p.status,
               p.tipo_regulacao,
               p.prioridade,
               p.tipo_solicitacao,
               p.data_solicitacao,
               p.motivo_devolucao,
               p.motivos_devolucao_checkboxes,
               pa.nome AS paciente_nome,
               pa.cpf AS paciente_cpf,
               COALESCE(e.nome, c.especialidade) AS nome_solicitacao,
               un.nome AS unidade_nome
        FROM pedidos p
        JOIN pacientes pa ON pa.id = p.paciente_id
        LEFT JOIN exames e ON e.id = p.exame_id
        LEFT JOIN consultas c ON c.id = p.consulta_id
        JOIN unidades_saude un ON un.id = p.unidade_id
        WHERE p.unidade_id = %s AND p.status = %s
        ORDER BY p.data_atualizacao DESC
    """
    with mysql.get_cursor(dictionary=True) as (_, cursor):
        cursor.execute(query, (unidade_id, "devolvido_medico_para_recepcao"))
        return cursor.fetchall()


# ==========================================================
# 📋 Listar todos os pedidos (para admin)
# ==========================================================
def listar_todos() -> List[dict]:
    query = """
        SELECT p.id,
               p.status,
               p.tipo_regulacao,
               p.prioridade,
               p.tipo_solicitacao,
               p.data_solicitacao,
               p.pendente_recepcao,
               pa.nome AS paciente_nome,
               pa.cpf AS paciente_cpf,
               COALESCE(e.nome, c.especialidade) AS nome_solicitacao,
               un.nome AS unidade_nome
        FROM pedidos p
        JOIN pacientes pa ON pa.id = p.paciente_id
        LEFT JOIN exames e ON e.id = p.exame_id
        LEFT JOIN consultas c ON c.id = p.consulta_id
        JOIN unidades_saude un ON un.id = p.unidade_id
        ORDER BY p.data_atualizacao DESC
    """
    with mysql.get_cursor(dictionary=True) as (_, cursor):
        cursor.execute(query)
        return cursor.fetchall()


# ==========================================================
# 📋 Listar todos os pedidos devolvidos (para admin) - NOVA
# ==========================================================
def listar_devolvidos_todas_unidades() -> List[dict]:
    """Lista todos os pedidos devolvidos de todas as unidades"""
    query = """
        SELECT p.id,
               p.status,
               p.tipo_regulacao,
               p.prioridade,
               p.tipo_solicitacao,
               p.data_solicitacao,
               p.motivo_devolucao,
               p.motivos_devolucao_checkboxes,
               pa.nome AS paciente_nome,
               pa.cpf AS paciente_cpf,
               COALESCE(e.nome, c.especialidade) AS nome_solicitacao,
               un.nome AS unidade_nome
        FROM pedidos p
        JOIN pacientes pa ON pa.id = p.paciente_id
        LEFT JOIN exames e ON e.id = p.exame_id
        LEFT JOIN consultas c ON c.id = p.consulta_id
        JOIN unidades_saude un ON un.id = p.unidade_id
        WHERE p.status = %s
        ORDER BY p.data_atualizacao DESC
    """
    with mysql.get_cursor(dictionary=True) as (_, cursor):
        cursor.execute(query, ("devolvido_medico_para_recepcao",))
        return cursor.fetchall()


# ==========================================================
# 📋 Listar todos os pedidos devolvidos (para admin)
# ==========================================================
def listar_todos_devolvidos() -> List[dict]:
    query = """
        SELECT p.id,
               p.status,
               p.tipo_regulacao,
               p.prioridade,
               p.tipo_solicitacao,
               p.data_solicitacao,
               p.motivo_devolucao,
               p.motivos_devolucao_checkboxes,
               pa.nome AS paciente_nome,
               pa.cpf AS paciente_cpf,
               COALESCE(e.nome, c.especialidade) AS nome_solicitacao,
               un.nome AS unidade_nome
        FROM pedidos p
        JOIN pacientes pa ON pa.id = p.paciente_id
        LEFT JOIN exames e ON e.id = p.exame_id
        LEFT JOIN consultas c ON c.id = p.consulta_id
        JOIN unidades_saude un ON un.id = p.unidade_id
        WHERE p.status = %s
        ORDER BY p.data_atualizacao DESC
    """
    with mysql.get_cursor(dictionary=True) as (_, cursor):
        cursor.execute(query, ("devolvido_medico_para_recepcao",))
        return cursor.fetchall()


# ==========================================================
# 📦 Listar para Malote - ATUALIZADO
# ==========================================================
def listar_para_malote() -> List[dict]:
    query = """
        SELECT p.id,
               p.status,
               p.prioridade,
               p.tipo_regulacao,
               p.tipo_solicitacao,
               p.data_solicitacao,
               un.nome AS unidade_nome,
               pa.nome AS paciente_nome,
               pa.cpf AS paciente_cpf,
               COALESCE(e.nome, c.especialidade) AS nome_solicitacao
        FROM pedidos p
        JOIN pacientes pa ON pa.id = p.paciente_id
        LEFT JOIN exames e ON e.id = p.exame_id
        LEFT JOIN consultas c ON c.id = p.consulta_id
        JOIN unidades_saude un ON un.id = p.unidade_id
        WHERE p.status IN (%s, %s)
        ORDER BY un.nome, p.data_solicitacao
    """
    with mysql.get_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            query,
            (
                StatusPedido.AGUARDANDO_TRIAGEM.value,
                StatusPedido.DEVOLVIDO_SEM_CONTATO.value,
            ),
        )
        return cursor.fetchall()


# ==========================================================
# 🩺 Listar para Médico Regulador
# ==========================================================
def listar_para_medico(tipo_regulacao: str) -> List[dict]:
    if tipo_regulacao not in ("municipal", "estadual"):
        return []
    status_esperado = (
        StatusPedido.AGUARDANDO_ANALISE_MEDICO_MUNICIPAL.value
        if tipo_regulacao == "municipal"
        else StatusPedido.AGUARDANDO_ANALISE_MEDICO_ESTADUAL.value
    )
    query = """
        SELECT p.id,
               p.prioridade,
               p.status,
               p.tipo_solicitacao,
               p.motivo_devolucao,
               pa.nome AS paciente_nome,
               pa.cpf AS paciente_cpf,
               pa.telefone_principal,
               COALESCE(e.nome, c.especialidade) AS nome_solicitacao,
               un.nome AS unidade_nome,
               p.data_solicitacao
        FROM pedidos p
        JOIN pacientes pa ON pa.id = p.paciente_id
        LEFT JOIN exames e ON e.id = p.exame_id
        LEFT JOIN consultas c ON c.id = p.consulta_id
        JOIN unidades_saude un ON un.id = p.unidade_id
        WHERE p.status = %s
        ORDER BY p.prioridade ASC, p.data_solicitacao ASC
    """
    with mysql.get_cursor(dictionary=True) as (_, cursor):
        cursor.execute(query, (status_esperado,))
        return cursor.fetchall()


# ==========================================================
# 📅 Listar para Agendador (com filtros)
# ==========================================================
def listar_para_agendador(
    tipo_regulacao: str,
    ano: Optional[int] = None,
    mes: Optional[int] = None,
    prioridade: Optional[str] = None
) -> List[dict]:

    if tipo_regulacao not in ("municipal", "estadual"):
        return []

    status_validos = (
        StatusPedido.APROVADO_MUNICIPAL.value,
        StatusPedido.AGENDAMENTO_EM_ANDAMENTO.value,
    ) if tipo_regulacao == "municipal" else (
        StatusPedido.APROVADO_ESTADUAL.value,
        StatusPedido.AGENDAMENTO_EM_ANDAMENTO.value,
    )

    # 👉 SELECT unificado: traz exame OU consulta
    query = """
        SELECT 
            p.id,
            p.status,
            p.tentativas_contato,
            p.data_solicitacao,
            p.data_exame,
            p.horario_exame,
            p.local_exame,
            p.prioridade,

            pa.nome AS paciente_nome,
            pa.cpf AS paciente_cpf,
            pa.telefone_principal,
            pa.telefone_secundario,

            p.exame_id,
            e.nome AS exame_nome,

            p.consulta_id,
            c.nome AS consulta_nome,

            un.nome AS unidade_nome

        FROM pedidos p
        JOIN pacientes pa ON pa.id = p.paciente_id
        LEFT JOIN exames e ON e.id = p.exame_id
        LEFT JOIN consultas c ON c.id = p.consulta_id
        JOIN unidades_saude un ON un.id = p.unidade_id
        WHERE p.status IN (%s, %s)
          AND p.tipo_regulacao = %s
    """

    params = [status_validos[0], status_validos[1], tipo_regulacao]

    if ano:
        query += " AND YEAR(p.data_solicitacao) = %s"
        params.append(ano)
    if mes:
        query += " AND MONTH(p.data_solicitacao) = %s"
        params.append(mes)
    if prioridade:
        query += " AND p.prioridade = %s"
        params.append(prioridade)

    query += " ORDER BY p.prioridade ASC, p.data_solicitacao DESC"

    with mysql.get_cursor(dictionary=True) as (_, cursor):
        cursor.execute(query, tuple(params))
        return cursor.fetchall()


# ==========================================================
# 🕓 Histórico de Pedido
# ==========================================================
def obter_historico(pedido_id: int) -> list[dict]:
    query = """
        SELECT h.id,
               h.status,
               h.descricao,
               h.criado_em,
               u.nome AS usuario_nome
        FROM historico_pedidos h
        JOIN usuarios u ON u.id = h.criado_por
        WHERE h.pedido_id = %s
        ORDER BY h.criado_em DESC
    """
    with mysql.get_cursor(dictionary=True) as (_, cursor):
        cursor.execute(query, (pedido_id,))
        return cursor.fetchall()


# ==========================================================
# 🔍 Listar por Status
# ==========================================================
def listar_por_status(status: str) -> List[dict]:
    query = """
        SELECT p.id,
               p.status,
               p.tipo_regulacao,
               p.prioridade,
               p.tipo_solicitacao,
               p.data_solicitacao,
               p.data_atualizacao,
               p.data_exame,
               p.horario_exame,
               p.local_exame,
               pa.nome AS paciente_nome,
               pa.cpf AS paciente_cpf,
               COALESCE(e.nome, c.especialidade) AS nome_solicitacao,
               un.nome AS unidade_nome
        FROM pedidos p
        JOIN pacientes pa ON pa.id = p.paciente_id
        LEFT JOIN exames e ON e.id = p.exame_id
        LEFT JOIN consultas c ON c.id = p.consulta_id
        JOIN unidades_saude un ON un.id = p.unidade_id
        WHERE p.status = %s
        ORDER BY p.data_solicitacao DESC
    """
    with mysql.get_cursor(dictionary=True) as (_, cursor):
        cursor.execute(query, (status,))
        return cursor.fetchall()


# ==========================================================
# 👤 Listar pedidos de um paciente
# ==========================================================
def listar_por_paciente(paciente_id: int) -> list[dict]:
    query = """
        SELECT 
            p.id,
            p.status,
            p.tipo_regulacao,
            p.prioridade,
            p.tipo_solicitacao,
            p.data_solicitacao,
            p.data_atualizacao,
            p.data_exame,
            p.horario_exame,
            p.local_exame,
            p.observacoes,
            p.motivo_cancelamento,
            p.motivo_devolucao,
            pac.nome as paciente_nome,
            pac.cpf as paciente_cpf,
            COALESCE(e.nome, c.especialidade) as nome_solicitacao,
            u.nome as unidade_nome,
            u_criacao.nome as usuario_criacao_nome
        FROM pedidos p
        JOIN pacientes pac ON p.paciente_id = pac.id
        LEFT JOIN exames e ON p.exame_id = e.id
        LEFT JOIN consultas c ON c.id = p.consulta_id
        JOIN unidades_saude u ON p.unidade_id = u.id
        JOIN usuarios u_criacao ON p.usuario_criacao = u_criacao.id
        WHERE p.paciente_id = %s
        ORDER BY p.data_solicitacao DESC
    """
    with mysql.get_cursor(dictionary=True) as (_, cursor):
        cursor.execute(query, (paciente_id,))
        return cursor.fetchall()


# ==========================================================
# 📋 Listar TODOS os pedidos devolvidos (NOVA - para admin)
# ==========================================================
def listar_devolvidos_todas_unidades() -> List[dict]:
    """Lista todos os pedidos devolvidos de todas as unidades"""
    query = """
        SELECT p.id,
               p.status,
               p.tipo_regulacao,
               p.prioridade,
               p.tipo_solicitacao,
               p.data_solicitacao,
               p.motivo_devolucao,
               p.motivos_devolucao_checkboxes,
               pa.nome AS paciente_nome,
               pa.cpf AS paciente_cpf,
               COALESCE(e.nome, c.especialidade) AS nome_solicitacao,
               un.nome AS unidade_nome
        FROM pedidos p
        JOIN pacientes pa ON pa.id = p.paciente_id
        LEFT JOIN exames e ON e.id = p.exame_id
        LEFT JOIN consultas c ON c.id = p.consulta_id
        JOIN unidades_saude un ON un.id = p.unidade_id
        WHERE p.status = %s
        ORDER BY p.data_atualizacao DESC
    """
    with mysql.get_cursor(dictionary=True) as (_, cursor):
        cursor.execute(query, ("devolvido_medico_para_recepcao",))
        return cursor.fetchall()