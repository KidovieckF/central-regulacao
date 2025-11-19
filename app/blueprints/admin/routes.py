from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required
from werkzeug.security import generate_password_hash

from app.repositories import exames as exames_repo
from app.repositories import unidades as unidades_repo
from app.repositories import usuarios as usuarios_repo
from app.repositories import consultas as consultas_repo
from app.utils.decorators import roles_required

from . import admin_bp

ROLES_DISPONIVEIS = {
    "admin",
    "recepcao",
    "recepcao_regulacao",  # NOVO: Usuário de recepção da regulação sem necessidade de unidade
    "malote",
    "medico_regulador",
    "agendador_municipal",
    "agendador_estadual",
}

ROLES_LABELS: dict[str, str] = {
    "admin": "Administrador",
    "recepcao": "Recepção",
    "recepcao_regulacao": "Recepção Regulação",  # NOVO: Label para o novo role
    "malote": "Malote",
    "medico_regulador": "Médico Regulador",
    "agendador_municipal": "Agendador Municipal",
    "agendador_estadual": "Agendador Estadual",
}

ROLES_OPCOES = [
    (valor, ROLES_LABELS.get(valor, valor.replace("_", " ").title()))
    for valor in sorted(ROLES_DISPONIVEIS)
]

# IMPORTANTE: Apenas "recepcao" exige unidade, "recepcao_regulacao" NÃO exige
ROLES_EXIGEM_UNIDADE = {"recepcao"}


def _normalizar_cpf(valor: Optional[str]) -> str:
    if not valor:
        return ""
    return re.sub(r"\D", "", valor)


def _carregar_unidades_para_formulario():
    unidades = unidades_repo.listar_unidades_ativas()
    return sorted(unidades, key=lambda unidade: unidade["nome"].lower())


@admin_bp.route("/unidades")
@login_required
@roles_required("recepcao", "admin")
def listar_unidades():
    unidades = unidades_repo.listar_todas()
    return render_template("admin/unidades/list.html", unidades=unidades)


@admin_bp.route("/unidades/nova", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def criar_unidade():
    if request.method == "POST":
        nome = (request.form.get("nome") or "").strip()
        ativa = request.form.get("ativa") == "1"

        if not nome:
            flash("Informe o nome da unidade de saúde.", "danger")
            return render_template("admin/unidades/form.html", unidade=None)

        unidades_repo.criar_unidade(nome=nome, ativa=ativa)
        flash("Unidade criada com sucesso.", "success")
        return redirect(url_for("admin.listar_unidades"))

    return render_template("admin/unidades/form.html", unidade=None)


@admin_bp.route("/unidades/<int:unidade_id>/editar", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def editar_unidade(unidade_id: int):
    unidade = unidades_repo.obter_por_id(unidade_id)
    if not unidade:
        flash("Unidade não encontrada.", "danger")
        return redirect(url_for("admin.listar_unidades"))

    if request.method == "POST":
        nome = (request.form.get("nome") or "").strip()
        ativa = request.form.get("ativa") == "1"

        if not nome:
            flash("Informe o nome da unidade de saúde.", "danger")
            return render_template("admin/unidades/form.html", unidade=unidade)

        unidades_repo.atualizar_unidade(unidade_id=unidade_id, nome=nome, ativa=ativa)
        flash("Unidade atualizada com sucesso.", "success")
        return redirect(url_for("admin.listar_unidades"))

    return render_template("admin/unidades/form.html", unidade=unidade)


@admin_bp.route("/unidades/<int:unidade_id>/alterar-status", methods=["POST"])
@login_required
@roles_required("admin")
def alterar_status_unidade(unidade_id: int):
    unidade = unidades_repo.obter_por_id(unidade_id)
    if not unidade:
        flash("Unidade não encontrada.", "danger")
        return redirect(url_for("admin.listar_unidades"))

    nova_situacao = not bool(unidade["ativo"])
    unidades_repo.definir_status(unidade_id=unidade_id, ativa=nova_situacao)

    mensagem = "Unidade ativada com sucesso." if nova_situacao else "Unidade desativada com sucesso."
    flash(mensagem, "success")
    return redirect(url_for("admin.listar_unidades"))


# --- Usuários ---

@admin_bp.route("/usuarios")
@login_required
@roles_required("admin")
def listar_usuarios():
    usuarios = usuarios_repo.listar_todos()
    return render_template(
        "admin/usuarios/list.html",
        usuarios=usuarios,
        roles_labels=ROLES_LABELS,
    )


@admin_bp.route("/usuarios/novo", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def criar_usuario():
    unidades = _carregar_unidades_para_formulario()
    dados_form = dict(request.form) if request.method == "POST" else {}

    if request.method == "POST":
        nome = (request.form.get("nome") or "").strip()
        cpf = _normalizar_cpf(request.form.get("cpf"))
        role = (request.form.get("role") or "").strip()
        unidade_id_bruto = (request.form.get("unidade_id") or "").strip()
        senha = request.form.get("senha") or ""
        ativo = request.form.get("ativo") == "1"

        erros = []

        if not nome:
            erros.append("Informe o nome do usuário.")
        if not cpf or len(cpf) != 11:
            erros.append("Informe um CPF válido (11 dígitos).")
        if role not in ROLES_DISPONIVEIS:
            erros.append("Selecione um perfil de acesso válido.")

        # VERIFICAÇÃO IMPORTANTE: Apenas "recepcao" exige unidade, "recepcao_regulacao" NÃO
        exige_unidade = role in ROLES_EXIGEM_UNIDADE
        if exige_unidade and not unidade_id_bruto:
            erros.append("Selecione a unidade do usuário de recepção.")

        unidade_id = None
        if unidade_id_bruto:
            try:
                unidade_id = int(unidade_id_bruto)
            except ValueError:
                erros.append("Unidade selecionada é inválida.")

            ids_validos = {unidade["id"] for unidade in unidades}
            if unidade_id is not None and unidade_id not in ids_validos:
                erros.append("Unidade selecionada não está disponível.")

        if not senha or len(senha) < 6:
            erros.append("Informe uma senha com pelo menos 6 caracteres.")

        if usuarios_repo.obter_por_cpf(cpf, incluir_inativos=True):
            erros.append("Já existe um usuário cadastrado com esse CPF.")

        if erros:
            for erro in erros:
                flash(erro, "danger")
            return render_template(
                "admin/usuarios/form.html",
                usuario=None,
                unidades=unidades,
                dados_form=dados_form,
                titulo_pagina="Novo usuário",
                form_action=url_for("admin.criar_usuario"),
                roles_opcoes=ROLES_OPCOES,
            )

        senha_hash = generate_password_hash(senha)

        usuarios_repo.criar_usuario(
            nome=nome,
            cpf=cpf,
            senha_hash=senha_hash,
            role=role,
            unidade_id=unidade_id,
            ativo=1 if ativo else 0,
        )

        flash("Usuário criado com sucesso.", "success")
        return redirect(url_for("admin.listar_usuarios"))

    return render_template(
        "admin/usuarios/form.html",
        usuario=None,
        unidades=unidades,
        dados_form=dados_form,
        titulo_pagina="Novo usuário",
        form_action=url_for("admin.criar_usuario"),
        roles_opcoes=ROLES_OPCOES,
    )


@admin_bp.route("/usuarios/<int:usuario_id>/editar", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def editar_usuario(usuario_id: int):
    usuario = usuarios_repo.obter_por_id(usuario_id)
    if not usuario:
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for("admin.listar_usuarios"))

    unidades = _carregar_unidades_para_formulario()

    if request.method == "POST":
        nome = (request.form.get("nome") or "").strip()
        role = (request.form.get("role") or "").strip()
        unidade_id_bruto = (request.form.get("unidade_id") or "").strip()
        novo_cpf = _normalizar_cpf(request.form.get("cpf"))
        senha = request.form.get("senha") or ""
        ativo = request.form.get("ativo") == "1"

        erros = []

        if not nome:
            erros.append("Informe o nome do usuário.")
        if not novo_cpf or len(novo_cpf) != 11:
            erros.append("Informe um CPF válido (11 dígitos).")
        if role not in ROLES_DISPONIVEIS:
            erros.append("Selecione um perfil de acesso válido.")

        # VERIFICAÇÃO IMPORTANTE: Apenas "recepcao" exige unidade, "recepcao_regulacao" NÃO
        exige_unidade = role in ROLES_EXIGEM_UNIDADE
        if exige_unidade and not unidade_id_bruto:
            erros.append("Selecione a unidade do usuário de recepção.")

        unidade_id = None
        if unidade_id_bruto:
            try:
                unidade_id = int(unidade_id_bruto)
            except ValueError:
                erros.append("Unidade selecionada é inválida.")

            ids_validos = {unidade["id"] for unidade in unidades}
            if unidade_id is not None and unidade_id not in ids_validos:
                erros.append("Unidade selecionada não está disponível.")

        usuario_existente = usuarios_repo.obter_por_cpf(
            novo_cpf,
            incluir_inativos=True,
            ignorar_usuario_id=usuario_id,
        )
        if usuario_existente:
            erros.append("Já existe outro usuário cadastrado com esse CPF.")

        if senha and len(senha) < 6:
            erros.append("A nova senha deve ter pelo menos 6 caracteres.")

        if erros:
            for erro in erros:
                flash(erro, "danger")
            dados_form = dict(request.form)
            return render_template(
                "admin/usuarios/form.html",
                usuario=usuario,
                unidades=unidades,
                dados_form=dados_form,
                titulo_pagina="Editar usuário",
                form_action=url_for("admin.editar_usuario", usuario_id=usuario_id),
                roles_opcoes=ROLES_OPCOES,
            )

        campos_atualizados = {
            "nome": nome,
            "cpf": novo_cpf,
            "role": role,
            "unidade_id": unidade_id,
            "ativo": 1 if ativo else 0,
            "atualizado_em": datetime.utcnow(),
        }

        if senha:
            campos_atualizados["senha_hash"] = generate_password_hash(senha)

        usuarios_repo.atualizar_usuario(usuario_id=usuario_id, **campos_atualizados)

        flash("Usuário atualizado com sucesso.", "success")
        return redirect(url_for("admin.listar_usuarios"))

    dados_form = {
        "nome": usuario["nome"],
        "cpf": usuario["cpf"],
        "role": usuario["role"],
        "unidade_id": usuario["unidade_id"] or "",
        "ativo": "1" if usuario.get("ativo") else "0",
    }

    return render_template(
        "admin/usuarios/form.html",
        usuario=usuario,
        unidades=unidades,
        dados_form=dados_form,
        titulo_pagina="Editar usuário",
        form_action=url_for("admin.editar_usuario", usuario_id=usuario_id),
        roles_opcoes=ROLES_OPCOES,
    )


@admin_bp.route("/usuarios/<int:usuario_id>/alterar-status", methods=["POST"])
@login_required
@roles_required("admin")
def alterar_status_usuario(usuario_id: int):
    usuario = usuarios_repo.obter_por_id(usuario_id)
    if not usuario:
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for("admin.listar_usuarios"))

    novo_status = 0 if usuario.get("ativo") else 1
    usuarios_repo.atualizar_usuario(
        usuario_id=usuario_id,
        ativo=novo_status,
        atualizado_em=datetime.utcnow(),
    )

    mensagem = "Usuário ativado com sucesso." if novo_status else "Usuário desativado com sucesso."
    flash(mensagem, "success")
    return redirect(url_for("admin.listar_usuarios"))


# --- Exames ---

@admin_bp.route("/exames")
@login_required
@roles_required("admin")
def listar_exames():
    exames = exames_repo.listar_todos()
    return render_template("admin/exames/list.html", exames=exames)


@admin_bp.route("/exames/novo", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def novo_exame():
    if request.method == "POST":
        nome = (request.form.get("nome") or "").strip()

        if not nome:
            flash("Informe o nome do exame.", "danger")
            return render_template(
                "admin/exames/form.html",
                exame=None,
                titulo_pagina="Novo exame",
                form_action=url_for("admin.novo_exame"),
            )

        exames_repo.criar_exame(nome=nome)
        flash("Exame criado com sucesso.", "success")
        return redirect(url_for("admin.listar_exames"))

    return render_template(
        "admin/exames/form.html",
        exame=None,
        titulo_pagina="Novo exame",
        form_action=url_for("admin.novo_exame"),
    )


@admin_bp.route("/exames/<int:exame_id>/editar", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def editar_exame(exame_id: int):
    exame = exames_repo.obter_por_id(exame_id)
    if not exame:
        flash("Exame não encontrado.", "danger")
        return redirect(url_for("admin.listar_exames"))

    if request.method == "POST":
        nome = (request.form.get("nome") or "").strip()

        if not nome:
            flash("Informe o nome do exame.", "danger")
            return render_template(
                "admin/exames/form.html",
                exame=exame,
                titulo_pagina="Editar exame",
                form_action=url_for("admin.editar_exame", exame_id=exame_id),
            )

        exames_repo.atualizar_exame(exame_id=exame_id, nome=nome)
        flash("Exame atualizado com sucesso.", "success")
        return redirect(url_for("admin.listar_exames"))

    return render_template(
        "admin/exames/form.html",
        exame=exame,
        titulo_pagina="Editar exame",
        form_action=url_for("admin.editar_exame", exame_id=exame_id),
    )


# --- Consultas ---

@admin_bp.route("/consultas")
@login_required
@roles_required("admin")
def listar_consultas():
    consultas = consultas_repo.listar_todas()
    return render_template("admin/consultas/list.html", consultas=consultas)


@admin_bp.route("/consultas/nova", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def nova_consulta():
    if request.method == "POST":
        especialidade = (request.form.get("especialidade") or "").strip()
        descricao = (request.form.get("descricao") or "").strip() or None

        if not especialidade:
            flash("Informe a especialidade.", "danger")
            return render_template(
                "admin/consultas/form.html",
                consulta=None,
                titulo_pagina="Nova especialidade",
                form_action=url_for("admin.nova_consulta"),
            )

        consultas_repo.criar_consulta(especialidade=especialidade, descricao=descricao)
        flash("Especialidade criada com sucesso.", "success")
        return redirect(url_for("admin.listar_consultas"))

    return render_template(
        "admin/consultas/form.html",
        consulta=None,
        titulo_pagina="Nova especialidade",
        form_action=url_for("admin.nova_consulta"),
    )


@admin_bp.route("/consultas/<int:consulta_id>/editar", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def editar_consulta(consulta_id: int):
    consulta = consultas_repo.obter_por_id(consulta_id)
    if not consulta:
        flash("Especialidade não encontrada.", "danger")
        return redirect(url_for("admin.listar_consultas"))

    if request.method == "POST":
        especialidade = (request.form.get("especialidade") or "").strip()
        descricao = (request.form.get("descricao") or "").strip() or None

        if not especialidade:
            flash("Informe a especialidade.", "danger")
            return render_template(
                "admin/consultas/form.html",
                consulta=consulta,
                titulo_pagina="Editar especialidade",
                form_action=url_for("admin.editar_consulta", consulta_id=consulta_id),
            )

        consultas_repo.atualizar_consulta(consulta_id=consulta_id, especialidade=especialidade, descricao=descricao)
        flash("Especialidade atualizada com sucesso.", "success")
        return redirect(url_for("admin.listar_consultas"))

    return render_template(
        "admin/consultas/form.html",
        consulta=consulta,
        titulo_pagina="Editar especialidade",
        form_action=url_for("admin.editar_consulta", consulta_id=consulta_id),
    )


@admin_bp.route("/consultas/<int:consulta_id>/alterar-status", methods=["POST"])
@login_required
@roles_required("admin")
def alterar_status_consulta(consulta_id: int):
    consulta = consultas_repo.obter_por_id(consulta_id)
    if not consulta:
        flash("Especialidade não encontrada.", "danger")
        return redirect(url_for("admin.listar_consultas"))

    nova_situacao = not bool(consulta["ativo"])
    consultas_repo.alterar_status(consulta_id=consulta_id, ativo=nova_situacao)

    mensagem = "Especialidade ativada com sucesso." if nova_situacao else "Especialidade desativada com sucesso."
    flash(mensagem, "success")
    return redirect(url_for("admin.listar_consultas"))