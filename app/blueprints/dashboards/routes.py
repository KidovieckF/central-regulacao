from flask import redirect, url_for, render_template
from flask_login import current_user, login_required
from app.extensions import mysql
from datetime import datetime, timedelta

from . import dashboards_bp


def _get_dashboard_stats():
    """Busca estatísticas gerais do sistema"""
    with mysql.get_cursor(dictionary=True) as (_, cursor):
        stats = {}
        
        # Estatísticas de pedidos
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN tipo_solicitacao = 'exame' THEN 1 END) as total_exames,
                COUNT(CASE WHEN tipo_solicitacao = 'consulta' THEN 1 END) as total_consultas,
                COUNT(CASE WHEN status LIKE '%AGUARDANDO%' THEN 1 END) as aguardando,
                COUNT(CASE WHEN status LIKE '%AGENDADO%' THEN 1 END) as agendados,
                COUNT(CASE WHEN status LIKE '%CANCELADO%' THEN 1 END) as cancelados,
                COUNT(CASE WHEN prioridade = 'P1' THEN 1 END) as prioridade_alta,
                COUNT(CASE WHEN DATE(data_solicitacao) = CURDATE() THEN 1 END) as hoje
            FROM pedidos
        """)
        stats['pedidos'] = cursor.fetchone()
        
        # Estatísticas de usuários
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN is_online = 1 THEN 1 END) as online,
                COUNT(CASE WHEN ativo = 1 THEN 1 END) as ativos
            FROM usuarios
        """)
        stats['usuarios'] = cursor.fetchone()
        
        # Estatísticas por unidade
        cursor.execute("""
            SELECT 
                u.nome as unidade,
                COUNT(p.id) as total_pedidos,
                COUNT(CASE WHEN p.status LIKE '%AGUARDANDO%' THEN 1 END) as pendentes
            FROM unidades_saude u
            LEFT JOIN pedidos p ON u.id = p.unidade_id AND p.data_solicitacao >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            WHERE u.ativo = 1
            GROUP BY u.id, u.nome
            ORDER BY total_pedidos DESC
            LIMIT 10
        """)
        stats['unidades'] = cursor.fetchall()
        
        # Atividade recente (últimos 7 dias)
        cursor.execute("""
            SELECT 
                DATE(data_solicitacao) as data,
                COUNT(*) as total,
                COUNT(CASE WHEN tipo_solicitacao = 'exame' THEN 1 END) as exames,
                COUNT(CASE WHEN tipo_solicitacao = 'consulta' THEN 1 END) as consultas
            FROM pedidos
            WHERE data_solicitacao >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            GROUP BY DATE(data_solicitacao)
            ORDER BY data DESC
        """)
        stats['atividade'] = cursor.fetchall()
        
        # Estatísticas do chat
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT c.id) as total_conversas,
                COUNT(m.id) as total_mensagens,
                COUNT(CASE WHEN DATE(m.created_at) = CURDATE() THEN 1 END) as mensagens_hoje
            FROM conversations c
            LEFT JOIN messages m ON c.id = m.conversation_id
        """)
        stats['chat'] = cursor.fetchone()
        
        return stats


def _get_role_specific_stats(role):
    """Busca estatísticas específicas por perfil"""
    with mysql.get_cursor(dictionary=True) as (_, cursor):
        stats = {}
        
        if role == "admin":
            # Para admin: visão geral do sistema
            cursor.execute("""
                SELECT 
                    role,
                    COUNT(*) as total,
                    COUNT(CASE WHEN is_online = 1 THEN 1 END) as online
                FROM usuarios
                WHERE ativo = 1
                GROUP BY role
                ORDER BY total DESC
            """)
            stats['usuarios_por_role'] = cursor.fetchall()
            
        elif role == "medico_regulador":
            # Para médico: pedidos aguardando análise
            cursor.execute("""
                SELECT 
                    tipo_regulacao,
                    COUNT(*) as total,
                    COUNT(CASE WHEN prioridade = 'P1' THEN 1 END) as urgentes
                FROM pedidos
                WHERE status IN ('AGUARDANDO_ANALISE_MEDICO_MUNICIPAL', 'AGUARDANDO_ANALISE_MEDICO_ESTADUAL')
                GROUP BY tipo_regulacao
            """)
            stats['pedidos_regulacao'] = cursor.fetchall()
            
        elif role == "malote":
            # Para malote: pedidos para triagem
            cursor.execute("""
                SELECT 
                    u.nome as unidade,
                    COUNT(p.id) as total,
                    COUNT(CASE WHEN p.status = 'DEVOLVIDO_SEM_CONTATO' THEN 1 END) as devolvidos
                FROM unidades_saude u
                LEFT JOIN pedidos p ON u.id = p.unidade_id 
                    AND p.status IN ('AGUARDANDO_TRIAGEM', 'DEVOLVIDO_SEM_CONTATO')
                WHERE u.ativo = 1
                GROUP BY u.id, u.nome
                HAVING total > 0
                ORDER BY total DESC
            """)
            stats['pedidos_por_unidade'] = cursor.fetchall()
        
        return stats


@dashboards_bp.route("/")
@login_required
def home():
    role = current_user.role
    
    # Para perfis específicos, redirecionar direto
    if role == "recepcao":
        return redirect(url_for("reception.listar_pedidos"))
    if role == "agendador_municipal":
        return redirect(url_for("scheduling.lista", tipo="municipal"))
    if role == "agendador_estadual":
        return redirect(url_for("scheduling.lista", tipo="estadual"))
    
    # Para admin, malote e médico regulador, mostrar dashboard
    stats_gerais = _get_dashboard_stats()
    stats_especificos = _get_role_specific_stats(role)
    
    return render_template(
        "dashboards/home.html", 
        stats=stats_gerais,
        role_stats=stats_especificos,
        user_role=role,
        datetime=datetime  # ✅ ADICIONAR DATETIME
    )


@dashboards_bp.route("/relatorios")
@login_required
def relatorios():
    """Página de relatórios detalhados"""
    role = current_user.role
    
    if role not in ["admin", "medico_regulador", "malote"]:
        return redirect(url_for("dashboards.home"))
    
    # Buscar dados para relatórios
    with mysql.get_cursor(dictionary=True) as (_, cursor):
        relatorios = {}
        
        # Relatório de pedidos por período
        cursor.execute("""
            SELECT 
                DATE_FORMAT(data_solicitacao, '%Y-%m') as mes,
                tipo_solicitacao,
                status,
                COUNT(*) as total
            FROM pedidos
            WHERE data_solicitacao >= DATE_SUB(NOW(), INTERVAL 12 MONTH)
            GROUP BY DATE_FORMAT(data_solicitacao, '%Y-%m'), tipo_solicitacao, status
            ORDER BY mes DESC
        """)
        relatorios['pedidos_periodo'] = cursor.fetchall()
        
        # Relatório de performance por unidade
        cursor.execute("""
            SELECT 
                u.nome as unidade,
                COUNT(p.id) as total_pedidos,
                AVG(DATEDIFF(p.data_atualizacao, p.data_solicitacao)) as tempo_medio_dias,
                COUNT(CASE WHEN p.status LIKE '%AGENDADO%' THEN 1 END) as agendados,
                COUNT(CASE WHEN p.status LIKE '%CANCELADO%' THEN 1 END) as cancelados
            FROM unidades_saude u
            LEFT JOIN pedidos p ON u.id = p.unidade_id 
                AND p.data_solicitacao >= DATE_SUB(NOW(), INTERVAL 3 MONTH)
            WHERE u.ativo = 1
            GROUP BY u.id, u.nome
            ORDER BY total_pedidos DESC
        """)
        relatorios['performance_unidades'] = cursor.fetchall()
        
        # Relatório de usuários mais ativos
        cursor.execute("""
            SELECT 
                u.nome,
                u.role,
                COUNT(h.id) as acoes_realizadas,
                MAX(u.last_seen) as ultimo_acesso
            FROM usuarios u
            LEFT JOIN historico_pedidos h ON u.id = h.criado_por 
                AND h.criado_em >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            WHERE u.ativo = 1
            GROUP BY u.id
            ORDER BY acoes_realizadas DESC
            LIMIT 20
        """)
        relatorios['usuarios_ativos'] = cursor.fetchall()
    
    return render_template("dashboards/relatorios.html", relatorios=relatorios, user_role=role)