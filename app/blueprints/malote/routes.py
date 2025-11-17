from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app.domain.status import StatusPedido
from app.repositories import pedidos as pedidos_repo
from app.services.pedidos_service import atualizar_status
from app.utils.decorators import roles_required
from . import malote_bp


@malote_bp.route("/pedidos")
@login_required
@roles_required("malote", "admin")
def listar():
    # Obter parâmetros de filtro da query string
    unidade = request.args.get('unidade', '').strip()
    categoria = request.args.get('categoria', '').strip()
    cpf = request.args.get('cpf', '').strip()
    nome = request.args.get('nome', '').strip()
    
    # Listar todos os pedidos (repository atual não aceita filtros)
    pedidos = pedidos_repo.listar_para_malote()
    
    # Filtrar no Python se há parâmetros de filtro
    if unidade or categoria or cpf or nome:
        pedidos_filtrados = []
        
        for pedido in pedidos:
            incluir = True
            
            # Filtro por unidade
            if unidade and unidade.lower() not in pedido.get('unidade_nome', '').lower():
                incluir = False
                
            # Filtro por categoria
            if categoria and pedido.get('tipo_solicitacao') != categoria:
                incluir = False
                
            # Filtro por CPF
            if cpf:
                cpf_limpo = ''.join(filter(str.isdigit, cpf))
                pedido_cpf_limpo = ''.join(filter(str.isdigit, pedido.get('paciente_cpf', '')))
                if cpf_limpo not in pedido_cpf_limpo:
                    incluir = False
                    
            # Filtro por nome
            if nome and nome.lower() not in pedido.get('paciente_nome', '').lower():
                incluir = False
                
            if incluir:
                pedidos_filtrados.append(pedido)
                
        pedidos = pedidos_filtrados
    
    # Obter lista de unidades para o dropdown
    unidades_disponiveis = sorted(list(set(p.get('unidade_nome', '') for p in pedidos_repo.listar_para_malote() if p.get('unidade_nome'))))
    
    # Dados para o template
    template_data = {
        'pedidos': pedidos,
        'filtros': {
            'unidade': unidade,
            'categoria': categoria,
            'cpf': cpf,
            'nome': nome
        },
        'unidades_disponiveis': unidades_disponiveis
    }
    
    return render_template("malote/list.html", **template_data)


@malote_bp.route("/pedidos/<int:pedido_id>/classificar", methods=["POST"])
@login_required
@roles_required("malote", "admin")
def classificar(pedido_id: int):
    tipo_regulacao = request.form.get("tipo_regulacao")
    prioridade = request.form.get("prioridade")
    
    # Obter filtros ativos para manter na navegação após ação
    filtros_ativos = {
        'unidade': request.form.get('filtro_unidade', ''),
        'categoria': request.form.get('filtro_categoria', ''),
        'cpf': request.form.get('filtro_cpf', ''),
        'nome': request.form.get('filtro_nome', '')
    }
    
    if tipo_regulacao not in ("municipal", "estadual") or prioridade not in ("P1", "P2"):
        flash("Selecione tipo de regulação e prioridade válidos.", "danger")
        
        # Redirecionar mantendo filtros
        params = []
        for key, value in filtros_ativos.items():
            if value:
                params.append(f"{key}={value}")
        
        redirect_url = url_for("malote.listar")
        if params:
            redirect_url += "?" + "&".join(params)
            
        return redirect(redirect_url)

    status_destino = (
        StatusPedido.AGUARDANDO_ANALISE_MEDICO_MUNICIPAL
        if tipo_regulacao == "municipal"
        else StatusPedido.AGUARDANDO_ANALISE_MEDICO_ESTADUAL
    )

    atualizar_status(
        pedido_id=pedido_id,
        status=status_destino,
        usuario_id=current_user.id,
        descricao=f"Pedido encaminhado ao médico regulador ({tipo_regulacao.upper()}) com prioridade {prioridade}.",
        extra_campos={
            "tipo_regulacao": tipo_regulacao,
            "prioridade": prioridade,
            "pendente_recepcao": 0,
        },
    )
    flash("Pedido encaminhamento ao médico regulador.", "success")
    
    # Redirecionar mantendo filtros ativos
    params = []
    for key, value in filtros_ativos.items():
        if value:
            params.append(f"{key}={value}")
    
    redirect_url = url_for("malote.listar")
    if params:
        redirect_url += "?" + "&".join(params)
        
    return redirect(redirect_url)


@malote_bp.route("/pedidos/limpar-filtros")
@login_required
@roles_required("malote", "admin")
def limpar_filtros():
    """Rota para limpar filtros e voltar à lista completa"""
    return redirect(url_for("malote.listar"))