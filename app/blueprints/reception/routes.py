from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from urllib.parse import urlparse

from app.domain.status import StatusPedido
from app.repositories import pacientes as pacientes_repo
from app.repositories import pedidos as pedidos_repo
from app.repositories import exames as exames_repo
from app.repositories import unidades as unidades_repo
from app.services.pedidos_service import atualizar_status, registrar_historico
from app.utils.decorators import roles_required
from . import reception_bp


def _parse_data_nascimento(valor: Optional[str]) -> Optional[str]:
    """
    Normaliza a data de nascimento para o formato YYYY-MM-DD ou retorna None.
    Aceita valores vazios ou já normalizados.
    """
    if not valor:
        return None

    valor = valor.strip()
    if not valor:
        return None

    try:
        # tenta formatos dd/mm/aaaa ou yyyy-mm-dd
        if "-" in valor:
            data = datetime.strptime(valor, "%Y-%m-%d").date()
        else:
            data = datetime.strptime(valor, "%d/%m/%Y").date()
        return data.strftime("%Y-%m-%d")
    except ValueError:
        return None


def _formatar_data_display(valor: Optional[Any]) -> Optional[str]:
    """
    Converte datas provenientes do banco (datetime.date, datetime.datetime ou string)
    para o formato dd/mm/aaaa para exibição.
    """
    if valor is None:
        return None

    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y")

    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")

    if isinstance(valor, str):
        valor = valor.strip()
        if not valor:
            return None

        formatos_entrada = ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S")
        for formato in formatos_entrada:
            try:
                return datetime.strptime(valor, formato).strftime("%d/%m/%Y")
            except ValueError:
                continue
        return valor  # mantém o valor original se não conseguir converter

    raise TypeError(f"Tipo de data não suportado: {type(valor)!r}")


def _to_time(value):
    """
    Converte valores retornados pelo MySQL (timedelta) para datetime.time,
    permitindo o uso de strftime nos templates.
    """
    if value is None:
        return None
    if isinstance(value, timedelta):
        return (datetime.min + value).time()
    return value


def _coletar_dados_paciente(unidade_id: int) -> Dict[str, Any]:
    """
    Extrai e normaliza os dados do paciente a partir do formulário.
    """
    data_nascimento = _parse_data_nascimento(request.form.get("data_nascimento"))

    return {
        "nome": (request.form.get("nome_paciente") or "").strip(),
        "cpf": (request.form.get("cpf_paciente") or "").strip(),
        "data_nascimento": data_nascimento,
        "telefone_principal": (request.form.get("telefone_principal") or "").strip() or None,
        "telefone_secundario": (request.form.get("telefone_secundario") or "").strip() or None,
        "email": (request.form.get("email") or "").strip() or None,
        "cartao_sus": (request.form.get("cartao_sus") or "").strip() or None,
        "endereco": (request.form.get("endereco") or "").strip() or None,
        "unidade_id": unidade_id,
    }


def _determinar_unidade_id(unidades: list[dict]) -> Optional[int]:
    """
    Determina o ID da unidade para o pedido ou paciente.
    - Usuário não-admin: usa a unidade vinculada ao usuário (se houver).
    - Admin: usa o valor enviado no formulário, garantindo que seja válido.
    """
    if current_user.role != "admin":
        return current_user.unidade_id

    unidade_id_str = (request.form.get("unidade_id") or "").strip()
    if not unidade_id_str:
        return None

    try:
        unidade_id = int(unidade_id_str)
    except ValueError:
        return None

    ids_validos = {unidade["id"] for unidade in unidades}
    return unidade_id if unidade_id in ids_validos else None


@reception_bp.route("/pedidos")
@login_required
@roles_required("recepcao", "admin")
def listar_pedidos():
    if current_user.unidade_id is None and current_user.role != "admin":
        flash("Usuário de recepção sem unidade vinculada. Contate o administrador.", "danger")
        return redirect(url_for("dashboards.home"))

    unidade_id = current_user.unidade_id
    pedidos = pedidos_repo.listar_por_unidade(unidade_id) if unidade_id else []
    return render_template("reception/list.html", pedidos=pedidos)


@reception_bp.route("/pedidos/novo", methods=["GET", "POST"])
@login_required
@roles_required("recepcao", "admin")
def novo_pedido():
    exames = exames_repo.listar_exames()
    unidades = unidades_repo.listar_unidades_ativas()
    dados_form = dict(request.form) if request.method == "POST" else {}

    if request.method == "POST":
        unidade_id = _determinar_unidade_id(unidades)

        if unidade_id is None:
            mensagem = "Selecione a unidade do pedido." if current_user.role == "admin" else \
                "Usuário de recepção sem unidade vinculada. Contate o administrador."
            flash(mensagem, "danger")
            return render_template(
                "reception/form.html",
                exames=exames,
                unidades=unidades,
                unidade_atual=current_user.unidade_id,
                dados_form=dados_form,
            )

        paciente_data = _coletar_dados_paciente(unidade_id)
        exame_id_bruto = (request.form.get("exame_id") or "").strip()
        observacoes = (request.form.get("observacoes") or "").strip() or None

        erros = []
        if not paciente_data["nome"]:
            erros.append("Nome do paciente é obrigatório.")
        if not paciente_data["cpf"]:
            erros.append("CPF do paciente é obrigatório.")
        if not exame_id_bruto:
            erros.append("Selecione o exame solicitado.")

        exame_id = None
        if exame_id_bruto:
            try:
                exame_id = int(exame_id_bruto)
            except ValueError:
                erros.append("Exame inválido selecionado.")

        ids_exames_validos = {exame["id"] for exame in exames}
        if exame_id and exame_id not in ids_exames_validos:
            erros.append("Exame solicitado não está disponível.")

        if paciente_data["data_nascimento"] is None and request.form.get("data_nascimento"):
            erros.append("Data de nascimento em formato inválido (use dd/mm/aaaa ou yyyy-mm-dd).")

        if erros:
            for erro in erros:
                flash(erro, "danger")
            return render_template(
                "reception/form.html",
                exames=exames,
                unidades=unidades,
                unidade_atual=current_user.unidade_id,
                dados_form=dados_form,
            )

        paciente_existente = pacientes_repo.obter_por_cpf(paciente_data["cpf"])
        if paciente_existente:
            pacientes_repo.atualizar_paciente(paciente_existente["id"], paciente_data)
            paciente_id = paciente_existente["id"]
        else:
            paciente_id = pacientes_repo.criar_paciente(paciente_data)

        pedido_id = pedidos_repo.criar_pedido(
            {
                "paciente_id": paciente_id,
                "exame_id": exame_id,
                "unidade_id": unidade_id,
                "usuario_criacao": current_user.id,
                "observacoes": observacoes,
            }
        )

        registrar_historico(
            pedido_id=pedido_id,
            status=StatusPedido.AGUARDANDO_TRIAGEM,
            descricao="Pedido criado pela recepção.",
            usuario_id=current_user.id,
        )
        flash("Pedido criado e enviado para triagem do malote.", "success")
        return redirect(url_for("reception.listar_pedidos"))

    return render_template(
        "reception/form.html",
        exames=exames,
        unidades=unidades,
        unidade_atual=current_user.unidade_id,
        dados_form=dados_form,
    )


@reception_bp.route("/pedidos/<int:pedido_id>")
@login_required
@roles_required("recepcao", "admin")
def detalhes_pedido(pedido_id: int):
    pedido = pedidos_repo.obter_por_id(pedido_id)
    if not pedido:
        abort(404)

    if current_user.role != "admin" and pedido["unidade_id"] != current_user.unidade_id:
        abort(403)

    pedido["horario_exame"] = _to_time(pedido.get("horario_exame"))

    historico = pedidos_repo.obter_historico(pedido_id)
    return render_template("reception/detalhe.html", pedido=pedido, historico=historico)


@reception_bp.route("/pedidos/<int:pedido_id>/cancelar", methods=["POST"])
@login_required
@roles_required("recepcao", "admin")
def cancelar_pedido(pedido_id: int):
    justificativa = (request.form.get("justificativa") or "").strip()
    if not justificativa:
        flash("Informe a justificativa para cancelamento.", "danger")
        return redirect(url_for("reception.detalhes_pedido", pedido_id=pedido_id))

    pedido = pedidos_repo.obter_por_id(pedido_id)
    if not pedido:
        abort(404)
    if current_user.role != "admin" and pedido["unidade_id"] != current_user.unidade_id:
        abort(403)

    atualizar_status(
        pedido_id=pedido_id,
        status=StatusPedido.CANCELADO_RECEPCAO,
        usuario_id=current_user.id,
        descricao=f"Cancelado pela recepção. Motivo: {justificativa}",
        extra_campos={"motivo_cancelamento": justificativa},
    )
    flash("Pedido cancelado com sucesso.", "info")
    return redirect(url_for("reception.listar_pedidos"))


@reception_bp.route("/pedidos/<int:pedido_id>/tratativa", methods=["GET", "POST"])
@login_required
@roles_required("recepcao", "admin")
def tratar_devolucao(pedido_id: int):
    pedido = pedidos_repo.obter_por_id(pedido_id)
    if not pedido:
        abort(404)

    if current_user.role != "admin" and pedido["unidade_id"] != current_user.unidade_id:
        abort(403)

    if request.method == "POST":
        tratativa = (request.form.get("tratativa") or "").strip()
        if not tratativa:
            flash("Descreva a tratativa realizada.", "danger")
            return redirect(url_for("reception.tratar_devolucao", pedido_id=pedido_id))

        registrar_historico(
            pedido_id=pedido_id,
            status=StatusPedido.DEVOLVIDO_PELO_MEDICO,
            descricao=f"Tratativa da recepção: {tratativa}",
            usuario_id=current_user.id,
        )
        pedidos_repo.atualizar_campos(
            pedido_id,
            {
                "status": StatusPedido.AGUARDANDO_TRIAGEM.value,
                "tipo_regulacao": None,
                "prioridade": None,
                "pendente_recepcao": 0,
                "motivo_devolucao": None,
                "usuario_atualizacao": current_user.id,
            },
        )
        registrar_historico(
            pedido_id=pedido_id,
            status=StatusPedido.AGUARDANDO_TRIAGEM,
            descricao="Pedido reenviado à triagem após tratativa.",
            usuario_id=current_user.id,
        )
        flash("Tratativa registrada e pedido reenviado ao malote.", "success")
        return redirect(url_for("reception.listar_pedidos"))

    pedido["horario_exame"] = _to_time(pedido.get("horario_exame"))

    historico = pedidos_repo.obter_historico(pedido_id)
    return render_template("reception/devolucao.html", pedido=pedido, historico=historico)


@reception_bp.route("/pacientes/<int:paciente_id>/editar", methods=["GET", "POST"])
@login_required
@roles_required("recepcao", "admin")
def editar_paciente(paciente_id: int):
    paciente = pacientes_repo.obter_por_id(paciente_id)
    if not paciente:
        abort(404)

    if current_user.role != "admin" and paciente["unidade_id"] != current_user.unidade_id:
        abort(403)

    unidades = unidades_repo.listar_unidades_ativas() if current_user.role == "admin" else []
    dados_form = request.form.to_dict() if request.method == "POST" else {}
    raw_next = request.args.get("next") or request.form.get("next")
    next_url = url_for("reception.listar_pedidos")
    if raw_next:
        parsed = urlparse(raw_next)
        if not parsed.netloc and not parsed.scheme:
            next_url = raw_next

    data_nascimento_fmt = _formatar_data_display(paciente.get("data_nascimento"))

    if request.method == "POST":
        unidade_id = paciente["unidade_id"]
        if current_user.role == "admin":
            unidade_selecionada = _determinar_unidade_id(unidades)
            if unidade_selecionada is None:
                flash("Selecione a unidade do paciente.", "danger")
                return render_template(
                    "reception/paciente_form.html",
                    paciente=paciente,
                    dados_form=dados_form,
                    data_nascimento_fmt=request.form.get("data_nascimento") or data_nascimento_fmt,
                    unidades=unidades,
                    next_url=next_url,
                )
            unidade_id = unidade_selecionada

        paciente_payload = _coletar_dados_paciente(unidade_id)
        erros = []
        if not paciente_payload["nome"]:
            erros.append("Nome do paciente é obrigatório.")
        if not paciente_payload["cpf"]:
            erros.append("CPF do paciente é obrigatório.")
        if request.form.get("data_nascimento") and paciente_payload["data_nascimento"] is None:
            erros.append("Data de nascimento em formato inválido (use dd/mm/aaaa ou yyyy-mm-dd).")

        if erros:
            for erro in erros:
                flash(erro, "danger")
            return render_template(
                "reception/paciente_form.html",
                paciente=paciente,
                dados_form=dados_form,
                data_nascimento_fmt=request.form.get("data_nascimento") or data_nascimento_fmt,
                unidades=unidades,
                next_url=next_url,
            )

        paciente_payload["unidade_id"] = unidade_id
        pacientes_repo.atualizar_paciente(paciente_id, paciente_payload)
        flash("Dados do paciente atualizados com sucesso.", "success")
        return redirect(next_url)

    return render_template(
        "reception/paciente_form.html",
        paciente=paciente,
        dados_form=dados_form,
        data_nascimento_fmt=data_nascimento_fmt,
        unidades=unidades,
        next_url=next_url,
    )

@reception_bp.route("/acompanhamento", methods=["GET", "POST"])
def acompanhar_pedido():
    """Consulta pública para acompanhamento de pedidos por CPF"""
    pedidos_paciente = []
    cpf_consulta = None
    
    if request.method == "POST":
        cpf_consulta = (request.form.get("cpf") or "").strip()
        
        if not cpf_consulta:
            flash("Informe o CPF para consulta.", "warning")
        elif len(cpf_consulta) != 11 or not cpf_consulta.isdigit():
            flash("CPF deve conter exatamente 11 dígitos.", "danger")
        else:
            # Buscar paciente pelo CPF
            paciente = pacientes_repo.obter_por_cpf(cpf_consulta)
            
            if not paciente:
                flash("Nenhum pedido encontrado para este CPF.", "info")
            else:
                # Buscar todos os pedidos do paciente
                pedidos_paciente = pedidos_repo.listar_por_paciente(paciente["id"])
                
                # Para cada pedido, buscar o histórico
                for pedido in pedidos_paciente:
                    pedido["historico"] = pedidos_repo.obter_historico(pedido["id"])
                    pedido["horario_exame"] = _to_time(pedido.get("horario_exame"))
    
    return render_template(
        "reception/acompanhamento.html", 
        pedidos=pedidos_paciente,
        cpf_consulta=cpf_consulta
    )