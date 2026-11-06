from flask import Blueprint, jsonify, request, session, Response
from datetime import datetime, timedelta
from sqlalchemy import or_, cast, String, func
from app.models import db, RetiradaDependente, RetiradaJovemAprendiz, Usuario, HistoricoBaixa, MovimentacaoEstoque, EstoqueKit
from app.services.estoque_service import recalibrar_estoque
from io import StringIO
import csv
import time

api_bp = Blueprint('api', __name__, url_prefix='/api')


# ==============================================================================
# MIDDLEWARE ALTA PERFORMANCE DE SESSÃO ÚNICA (CACHE DE VALIDAÇÃO)
# ==============================================================================
@api_bp.before_app_request
def verificar_sessao_unica():
    """
    Verifica se o token de sessão é válido.
    Usa cache temporal (10s) na sessão do Flask para evitar queries repetitivas 
    no banco de dados em cada chamada de API, eliminando a lentidão do sistema.
    """
    # Isenta a rota de login da verificação
    if request.endpoint == 'api.login_api':
        return None

    user_id = session.get('usuario_id')
    token_sessao_local = session.get('session_token')

    if user_id and token_sessao_local:
        agora = time.time()
        ultima_checagem = session.get('ultimo_check_sessao', 0)

        # Valida no banco de dados APENAS se tiver passado mais de 10 segundos da última checagem
        if (agora - ultima_checagem) > 10:
            user = Usuario.query.get(user_id)
            
            # Se o usuário não existe mais, foi inativado ou se logou em outro dispositivo
            if not user or not user.ativo or user.session_token != token_sessao_local:
                session.clear()
                return jsonify({
                    'sucesso': False,
                    'sessao_expirada': True,
                    'mensagem': 'Sua sessão foi encerrada pois sua conta foi conectada em outro dispositivo.'
                }), 401

            session['ultimo_check_sessao'] = agora


@api_bp.route('/logout', methods=['POST', 'GET'])
def logout_api():
    """Invalida a sessão ativa do usuário no banco e limpa a sessão local."""
    user_id = session.get('usuario_id')
    if user_id:
        user = Usuario.query.get(user_id)
        if user:
            user.session_token = None
            db.session.commit()
    session.clear()
    return jsonify({'sucesso': True, 'mensagem': 'Sessão encerrada com sucesso.'}), 200

def extrair_nomes_dependentes(resumo_str):
    """Auxiliar para extrair apenas os nomes dos dependentes para o autocomplete."""
    if not resumo_str:
        return []
    
    partes = resumo_str.split('|')
    nomes = []
    
    for parte in partes:
        parte_strip = parte.strip()
        texto_upper = parte_strip.upper()
        
        if "ÓRFÃOS" in texto_upper or "ORFAOS" in texto_upper or "AUTOMÁTICOS" in texto_upper or "AUTOMATICOS" in texto_upper:
            if ":" in parte_strip:
                sub = parte_strip.split(":")[1].strip()
            else:
                sub = parte_strip.replace("Kits Automáticos (Órfãos)", "").replace("Kits Automáticos", "").strip()
            sub_nomes = [n.strip() for n in sub.split(',') if n.strip()]
            nomes.extend(sub_nomes)
        else:
            pedacos = parte_strip.split('-')
            if pedacos and pedacos[0].strip():
                nomes.append(pedacos[0].strip())
                
    return nomes


@api_bp.route('/login', methods=['POST'])
def login_api():
    data = request.json or {}
    email = data.get('email', '').strip()
    senha = data.get('senha', '').strip()

    if not email or not senha:
        return jsonify({'sucesso': False, 'mensagem': 'Preencha todos os campos.'}), 400

    user = Usuario.query.filter_by(email=email, ativo=True).first()
    if not user or not user.checar_senha(senha):
        return jsonify({'sucesso': False, 'mensagem': 'E-mail ou senha incorretos.'}), 401

    # GERA NOVO TOKEN E INVALIDA SESSÕES EM OUTROS DISPOSITIVOS
    novo_token = user.gerar_novo_session_token()
    db.session.commit()

    # REGISTRA A SESSÃO ATUAL NO FLASK
    session['usuario_id'] = user.id_usuario
    session['usuario_nome'] = user.nome
    session['usuario_email'] = user.email
    session['usuario_perfil'] = user.perfil
    session['session_token'] = novo_token
    session['ultimo_check_sessao'] = time.time()  # Timestamp inicial

    return jsonify({
        'sucesso': True,
        'mensagem': 'Login efetuado com sucesso!',
        'usuario': user.to_dict()
    }), 200


@api_bp.route('/criar-usuario', methods=['POST'])
def criar_usuario():
    if session.get('usuario_perfil') != 'ADMIN':
        return jsonify({'sucesso': False, 'mensagem': 'Acesso negado. Apenas gestores podem cadastrar usuários.'}), 403

    data = request.json or {}
    nome = data.get('nome', '').strip()
    email = data.get('email', '').strip().lower()
    senha = data.get('senha', '').strip()
    perfil = data.get('perfil', 'OPERADOR').upper()

    if not nome or not email or not senha:
        return jsonify({'sucesso': False, 'mensagem': 'Todos os campos são obrigatórios.'}), 400

    if Usuario.query.filter_by(email=email).first():
        return jsonify({'sucesso': False, 'mensagem': 'Já existe um usuário cadastrado com este e-mail.'}), 400

    novo_user = Usuario(nome=nome, email=email, perfil=perfil)
    novo_user.set_senha(senha)
    db.session.add(novo_user)
    db.session.commit()

    return jsonify({'sucesso': True, 'mensagem': 'Usuário cadastrado com sucesso!'}), 201


@api_bp.route('/autocompletar', methods=['GET'])
def autocompletar_nome():
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify({'sucesso': True, 'sugestoes': []}), 200

    termo_like = f"%{query}%"
    sugestoes = []

    deps = RetiradaDependente.query.filter(
        or_(
            RetiradaDependente.nome_colaborador.ilike(termo_like),
            RetiradaDependente.resumo_kits.ilike(termo_like),
            cast(RetiradaDependente.id_colaborador, String).ilike(termo_like)
        )
    ).limit(8).all()

    for d in deps:
        sugestoes.append({
            'codigo_retirada': d.codigo_retirada,
            'id_colaborador': d.id_colaborador,
            'nome_colaborador': d.nome_colaborador or "NÃO INFORMADO",
            'dependentes': extrair_nomes_dependentes(d.resumo_kits),
            'tipo_publico': 'Dependente'
        })

    limite_restante = 8 - len(sugestoes)
    if limite_restante > 0:
        jovens = RetiradaJovemAprendiz.query.filter(
            or_(
                RetiradaJovemAprendiz.resumo_kits.ilike(termo_like),
                cast(RetiradaJovemAprendiz.id_colaborador, String).ilike(termo_like)
            )
        ).limit(limite_restante).all()

        for j in jovens:
            nome_jovem = j.extrair_nome_jovem()
            sugestoes.append({
                'codigo_retirada': j.codigo_retirada,
                'id_colaborador': j.id_colaborador,
                'nome_colaborador': nome_jovem,
                'dependentes': [nome_jovem],
                'tipo_publico': 'Jovem Aprendiz'
            })

    return jsonify({'sucesso': True, 'sugestoes': sugestoes}), 200


@api_bp.route('/buscar/<string:termo_busca>', methods=['GET'])
def buscar_retirada(termo_busca):
    termo = str(termo_busca).strip()
    if 'RETIRADA_KIT:' in termo:
        termo = termo.replace('RETIRADA_KIT:', '').strip()
    
    apenas_numeros = "".join(filter(str.isdigit, termo))
    
    reg_dep = RetiradaDependente.query.filter_by(codigo_retirada=termo).first()
    reg_jovem = None
    if not reg_dep:
        reg_jovem = RetiradaJovemAprendiz.query.filter_by(codigo_retirada=termo).first()

    if not reg_dep and not reg_jovem and apenas_numeros.isdigit():
        id_num = int(apenas_numeros)
        reg_dep = RetiradaDependente.query.filter_by(id_colaborador=id_num).first()
        if not reg_dep:
            reg_jovem = RetiradaJovemAprendiz.query.filter_by(id_colaborador=id_num).first()

    if not reg_dep and not reg_jovem:
        termo_like = f"%{termo}%"
        reg_dep = RetiradaDependente.query.filter(
            or_(
                RetiradaDependente.nome_colaborador.ilike(termo_like),
                RetiradaDependente.resumo_kits.ilike(termo_like)
            )
        ).first()

        if not reg_dep:
            reg_jovem = RetiradaJovemAprendiz.query.filter(
                RetiradaJovemAprendiz.resumo_kits.ilike(termo_like)
            ).first()

    if reg_dep:
        return jsonify({'sucesso': True, 'dados': reg_dep.to_dict()}), 200

    if reg_jovem:
        return jsonify({'sucesso': True, 'dados': reg_jovem.to_dict()}), 200

    return jsonify({'sucesso': False, 'mensagem': 'Nenhum registro encontrado para este termo.'}), 404


@api_bp.route('/dar-baixa-item', methods=['POST'])
def dar_baixa_item():
    data = request.json or {}
    codigo_str = data.get('codigo_retirada', '').strip()
    index_kit = data.get('index_kit')
    modelo_baixa = data.get('modelo_baixa', '---').strip()
    nome_dependente = data.get('nome_dependente', '').strip()

    if 'RETIRADA_KIT:' in codigo_str:
        codigo_str = codigo_str.replace('RETIRADA_KIT:', '').strip()

    if not codigo_str or index_kit is None:
        return jsonify({'sucesso': False, 'mensagem': 'Dados incompletos para baixa.'}), 400

    if modelo_baixa == '---' or not modelo_baixa:
        return jsonify({'sucesso': False, 'mensagem': 'Selecione um modelo de kit válido antes de confirmar a entrega.'}), 400

    # 1. Busca o registro da retirada
    reg = RetiradaDependente.query.filter_by(codigo_retirada=codigo_str).first()
    tipo_pub = 'Dependente'
    if not reg:
        reg = RetiradaJovemAprendiz.query.filter_by(codigo_retirada=codigo_str).first()
        tipo_pub = 'Jovem Aprendiz'

    if not reg:
        return jsonify({'sucesso': False, 'mensagem': 'Registro de retirada não encontrado.'}), 404

    # 2. VALIDAÇÃO GERAL DE ESTOQUE (Trava para Todos os Públicos e Órfãos)
    item_est = EstoqueKit.query.filter_by(codigo_kit=modelo_baixa, ativo=True).first()
    if not item_est:
        return jsonify({
            'sucesso': False, 
            'mensagem': f'O modelo "{modelo_baixa}" ainda não possui entrada cadastrada no estoque!'
        }), 400

    lote_total = item_est.quantidade_disponivel or 0
    saidas = item_est.quantidade_baixada or 0
    saldo_balcao = max(0, lote_total - saidas)

    resumo_beneficiario = str(getattr(reg, 'resumo_kits', '') or "")
    is_orfeo = any(term in resumo_beneficiario.upper() for term in ["ÓRFÃOS", "ORFAOS", "AUTOMÁTICOS", "AUTOMATICOS"])

    if is_orfeo:
        reserva = item_est.quantidade_reservada or 0
        sobra_atual = saldo_balcao - reserva
        if sobra_atual <= 0:
            return jsonify({
                'sucesso': False, 
                'mensagem': f'Atenção! O modelo "{modelo_baixa}" está ESGOTADO para escolha presencial (Sobra: 0 un).'
            }), 400
    else:
        # Trava para solicitações regulares: impede baixa se não houver saldo físico no balcão
        if saldo_balcao <= 0:
            return jsonify({
                'sucesso': False, 
                'mensagem': f'Atenção! Não há mochilas do modelo "{modelo_baixa}" em estoque no balcão (Saldo: 0 un).'
            }), 400

    # 3. Atualiza o JSON de detalhes de entrega
    detalhes = dict(reg.detalhes_entregas or {})
    chave_item = f"kit_{index_kit}"

    detalhes[chave_item] = {
        'entregue': True,
        'modelo': modelo_baixa,
        'nome_dependente': nome_dependente,
        'data_entrega': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    total_kits = reg.qtd_kits
    qtd_entregues = sum(1 for v in detalhes.values() if isinstance(v, dict) and v.get('entregue') == True)

    if qtd_entregues >= total_kits:
        reg.status = 'ENTREGUE'
    elif qtd_entregues > 0:
        reg.status = 'ENTREGA PARCIAL'
    else:
        reg.status = 'PENDENTE'

    reg.detalhes_entregas = detalhes
    reg.data_entrega = datetime.now()

    # 4. Histórico da Baixa
    nome_op = session.get('usuario_nome', 'Operador Desconhecido')
    id_user = session.get('usuario_id')
    nome_titular = getattr(reg, 'nome_colaborador', None) or (reg.extrair_nome_jovem() if hasattr(reg, 'extrair_nome_jovem') else 'Beneficiário')

    nome_completo_registro = nome_titular
    if nome_dependente and nome_dependente != nome_titular:
        nome_completo_registro = f"{nome_titular} — Filho: {nome_dependente}"

    log_baixa = HistoricoBaixa(
        id_usuario=id_user,
        nome_operador=nome_op,
        codigo_retirada=reg.codigo_retirada,
        id_colaborador=reg.id_colaborador,
        nome_beneficiario=nome_completo_registro,
        tipo_publico=tipo_pub,
        index_kit=index_kit,
        modelo_baixa=modelo_baixa
    )
    db.session.add(log_baixa)
    
    # 5. Decrementa o saldo físico incrementando as saídas
    if item_est:
        item_est.quantidade_baixada = (item_est.quantidade_baixada or 0) + 1

        mov = MovimentacaoEstoque(
            id_estoque=item_est.id_estoque,
            tipo_movimentacao='SAIDA_BAIXA',
            quantidade=1,
            codigo_retirada=reg.codigo_retirada,
            observacao=f"Baixa presencial ({tipo_pub}) - Beneficiário: {nome_completo_registro}"
        )
        db.session.add(mov)

    db.session.commit()

    return jsonify({
        'sucesso': True,
        'mensagem': f'Kit {index_kit + 1} baixado com sucesso! (Modelo: {modelo_baixa})',
        'dados': reg.to_dict()
    }), 200


@api_bp.route('/historico-baixas', methods=['GET'])
def listar_historico():
    id_user = session.get('usuario_id')
    perfil_user = session.get('usuario_perfil')

    if not id_user:
        return jsonify({'sucesso': False, 'mensagem': 'Usuário não autenticado.'}), 401

    user_target_id = request.args.get('id_usuario', type=int)

    if perfil_user != 'ADMIN':
        user_target_id = id_user

    query = db.session.query(
        HistoricoBaixa.id_historico,
        HistoricoBaixa.data_baixa,
        HistoricoBaixa.nome_operador,
        HistoricoBaixa.nome_beneficiario,
        HistoricoBaixa.id_colaborador,
        HistoricoBaixa.tipo_publico,
        HistoricoBaixa.modelo_baixa
    )

    if user_target_id:
        query = query.filter(HistoricoBaixa.id_usuario == user_target_id)

    historicos = query.order_by(HistoricoBaixa.data_baixa.desc()).limit(200).all()

    lista_formatada = []
    for h in historicos:
        dt_str = ""
        if h.data_baixa:
            data_brasilia = h.data_baixa - timedelta(hours=3)
            dt_str = data_brasilia.strftime("%d/%m/%Y %H:%M:%S")

        lista_formatada.append({
            'id_historico': h.id_historico,
            'data_baixa': dt_str,
            'nome_operador': h.nome_operador,
            'nome_beneficiario': h.nome_beneficiario,
            'id_colaborador': h.id_colaborador,
            'tipo_publico': h.tipo_publico,
            'modelo_baixa': h.modelo_baixa
        })

    return jsonify({
        'sucesso': True,
        'perfil_logado': perfil_user,
        'historico': lista_formatada
    }), 200


@api_bp.route('/editar-baixa-historico', methods=['PUT'])
def editar_baixa_historico():
    if session.get('usuario_perfil') != 'ADMIN':
        return jsonify({'sucesso': False, 'mensagem': 'Acesso negado. Apenas administradores podem alterar baixas.'}), 403

    data = request.json or {}
    id_historico = data.get('id_historico')
    novo_modelo = data.get('novo_modelo', '').strip()

    if not id_historico or not novo_modelo:
        return jsonify({'sucesso': False, 'mensagem': 'Dados incompletos.'}), 400

    log_baixa = HistoricoBaixa.query.get(id_historico)
    if not log_baixa:
        return jsonify({'sucesso': False, 'mensagem': 'Registro de histórico não encontrado.'}), 404

    modelo_antigo = log_baixa.modelo_baixa
    if modelo_antigo == novo_modelo:
        return jsonify({'sucesso': True, 'mensagem': 'O modelo selecionado é idêntico ao atual.'}), 200

    reg = RetiradaDependente.query.filter_by(codigo_retirada=log_baixa.codigo_retirada).first()
    if not reg:
        reg = RetiradaJovemAprendiz.query.filter_by(codigo_retirada=log_baixa.codigo_retirada).first()

    if reg:
        detalhes = dict(reg.detalhes_entregas or {})
        chave_item = f"kit_{log_baixa.index_kit}"
        if chave_item in detalhes and isinstance(detalhes[chave_item], dict):
            detalhes[chave_item]['modelo'] = novo_modelo
            reg.detalhes_entregas = detalhes

    item_antigo = EstoqueKit.query.filter_by(codigo_kit=modelo_antigo).first()
    if item_antigo:
        item_antigo.quantidade_baixada = max(0, (item_antigo.quantidade_baixada or 0) - 1)
        mov_estorno = MovimentacaoEstoque(
            id_estoque=item_antigo.id_estoque,
            tipo_movimentacao='ESTORNO_CORRECAO',
            quantidade=1,
            codigo_retirada=log_baixa.codigo_retirada,
            observacao=f"Estorno por correção de baixa do histórico (Admin: {session.get('usuario_nome')})"
        )
        db.session.add(mov_estorno)

    item_novo = EstoqueKit.query.filter_by(codigo_kit=novo_modelo).first()
    if item_novo:
        item_novo.quantidade_baixada = (item_novo.quantidade_baixada or 0) + 1
        mov_saida = MovimentacaoEstoque(
            id_estoque=item_novo.id_estoque,
            tipo_movimentacao='SAIDA_CORRECAO',
            quantidade=1,
            codigo_retirada=log_baixa.codigo_retirada,
            observacao=f"Saída por troca de kit no histórico de {modelo_antigo} para {novo_modelo}"
        )
        db.session.add(mov_saida)

    log_baixa.modelo_baixa = novo_modelo
    db.session.commit()

    return jsonify({
        'sucesso': True,
        'mensagem': f'Modelo alterado com sucesso de "{modelo_antigo}" para "{novo_modelo}"!'
    }), 200


@api_bp.route('/revogar-baixa-historico', methods=['POST'])
def revogar_baixa_historico():
    if session.get('usuario_perfil') != 'ADMIN':
        return jsonify({'sucesso': False, 'mensagem': 'Acesso negado. Apenas administradores podem revogar baixas.'}), 403

    data = request.json or {}
    id_historico = data.get('id_historico')

    if not id_historico:
        return jsonify({'sucesso': False, 'mensagem': 'ID do histórico não informado.'}), 400

    log_baixa = HistoricoBaixa.query.get(id_historico)
    if not log_baixa:
        return jsonify({'sucesso': False, 'mensagem': 'Registro de histórico não encontrado.'}), 404

    modelo_estornado = log_baixa.modelo_baixa
    codigo_retirada = log_baixa.codigo_retirada
    index_kit_revogado = log_baixa.index_kit

    reg = RetiradaDependente.query.filter_by(codigo_retirada=codigo_retirada).first()
    if not reg:
        reg = RetiradaJovemAprendiz.query.filter_by(codigo_retirada=codigo_retirada).first()

    if not reg:
        return jsonify({'sucesso': False, 'mensagem': 'Registro de retirada correspondente não foi encontrado.'}), 404

    detalhes = dict(reg.detalhes_entregas or {})
    chave_item = f"kit_{index_kit_revogado}"

    if chave_item in detalhes:
        detalhes[chave_item] = {
            'entregue': False,
            'modelo': '---',
            'data_entrega': None
        }
        reg.detalhes_entregas = detalhes

    qtd_entregues_restantes = sum(
        1 for v in detalhes.values() 
        if isinstance(v, dict) and v.get('entregue') == True
    )

    if qtd_entregues_restantes == 0:
        reg.status = 'PENDENTE'
        reg.data_entrega = None
    else:
        reg.status = 'ENTREGA PARCIAL'

    item_estoque = EstoqueKit.query.filter_by(codigo_kit=modelo_estornado).first()
    if item_estoque:
        item_estoque.quantidade_baixada = max(0, (item_estoque.quantidade_baixada or 0) - 1)
        
        mov_estorno = MovimentacaoEstoque(
            id_estoque=item_estoque.id_estoque,
            tipo_movimentacao='REVOGACAO_ADMIN',
            quantidade=1,
            codigo_retirada=codigo_retirada,
            observacao=f"Revogação de baixa efetuada pelo Admin ({session.get('usuario_nome')}) - Modelo {modelo_estornado}"
        )
        db.session.add(mov_estorno)

    db.session.delete(log_baixa)
    db.session.commit()

    return jsonify({
        'sucesso': True,
        'mensagem': f'Baixa revogada com sucesso! O modelo "{modelo_estornado}" foi devolvido ao estoque e o status foi atualizado para {reg.status}.'
    }), 200


@api_bp.route('/historico-ranking-operadores', methods=['GET'])
def ranking_operadores():
    if session.get('usuario_perfil') != 'ADMIN':
        return jsonify({'sucesso': False, 'mensagem': 'Acesso negado.'}), 403

    resultados = db.session.query(
        Usuario.id_usuario,
        Usuario.nome,
        Usuario.email,
        Usuario.perfil,
        func.coalesce(func.count(HistoricoBaixa.id_historico), 0).label('total_baixas'),
        func.max(HistoricoBaixa.data_baixa).label('ultima_baixa')
    ).outerjoin(
        HistoricoBaixa, Usuario.id_usuario == HistoricoBaixa.id_usuario
    ).group_by(
        Usuario.id_usuario, Usuario.nome, Usuario.email, Usuario.perfil
    ).order_by(
        func.count(HistoricoBaixa.id_historico).desc()
    ).all()

    ranking = []
    for r in resultados:
        ultima = None
        if r.ultima_baixa:
            dt_br = r.ultima_baixa - timedelta(hours=3)
            ultima = dt_br.strftime("%d/%m/%Y %H:%M:%S")

        ranking.append({
            'id_usuario': r.id_usuario,
            'nome': r.nome,
            'email': r.email,
            'perfil': r.perfil,
            'total_baixas': r.total_baixas,
            'ultima_baixa': ultima or "Nenhuma baixa"
        })

    return jsonify({
        'sucesso': True,
        'ranking': ranking
    }), 200


@api_bp.route('/usuarios', methods=['GET'])
def listar_usuarios():
    if session.get('usuario_perfil') != 'ADMIN':
        return jsonify({'sucesso': False, 'mensagem': 'Acesso negado.'}), 403

    users = db.session.query(
        Usuario.id_usuario,
        Usuario.nome,
        Usuario.email,
        Usuario.perfil,
        Usuario.ativo
    ).order_by(Usuario.data_criacao.desc()).all()

    return jsonify({
        'sucesso': True,
        'usuarios': [
            {
                'id_usuario': u.id_usuario,
                'nome': u.nome,
                'email': u.email,
                'perfil': u.perfil,
                'ativo': u.ativo
            } for u in users
        ]
    }), 200


@api_bp.route('/usuarios/<int:id_usuario>', methods=['PUT'])
def atualizar_usuario(id_usuario):
    if session.get('usuario_perfil') != 'ADMIN':
        return jsonify({'sucesso': False, 'mensagem': 'Acesso negado.'}), 403

    user = Usuario.query.get(id_usuario)
    if not user:
        return jsonify({'sucesso': False, 'mensagem': 'Usuário não encontrado.'}), 404

    if user.email.lower() == 'admin@funfarme.com.br':
        return jsonify({'sucesso': False, 'mensagem': 'O usuário Administrador Master não pode ser alterado.'}), 400

    data = request.json or {}
    if 'nome' in data and data['nome'].strip():
        user.nome = data['nome'].strip()
    if 'email' in data and data['email'].strip():
        user.email = data['email'].strip().lower()
    if 'perfil' in data and data['perfil'].strip():
        user.perfil = data['perfil'].strip().upper()
    if 'senha' in data and data['senha'].strip():
        user.set_senha(data['senha'].strip())

    db.session.commit()
    return jsonify({'sucesso': True, 'mensagem': 'Usuário atualizado com sucesso!'}), 200


@api_bp.route('/usuarios/<int:id_usuario>', methods=['DELETE'])
def excluir_usuario(id_usuario):
    if session.get('usuario_perfil') != 'ADMIN':
        return jsonify({'sucesso': False, 'mensagem': 'Acesso negado.'}), 403

    user = Usuario.query.get(id_usuario)
    if not user:
        return jsonify({'sucesso': False, 'mensagem': 'Usuário não encontrado.'}), 404

    if user.email.lower() == 'admin@funfarme.com.br':
        return jsonify({'sucesso': False, 'mensagem': 'O usuário Administrador Master não pode ser excluído.'}), 400

    if session.get('usuario_id') == id_usuario:
        return jsonify({'sucesso': False, 'mensagem': 'Você não pode excluir sua própria conta.'}), 400

    db.session.delete(user)
    db.session.commit()
    return jsonify({'sucesso': True, 'mensagem': 'Usuário excluído com sucesso!'}), 200


@api_bp.route('/estoque/listar', methods=['GET'])
def listar_estoque():
    if session.get('usuario_perfil') != 'ADMIN':
        return jsonify({'sucesso': False, 'mensagem': 'Acesso negado.'}), 403

    info_calibragem = recalibrar_estoque()
    # REMOVIDO o filtro ativo=True para exibir TODOS os kits (ativos e inativos)
    itens = EstoqueKit.query.order_by(EstoqueKit.codigo_kit.asc()).all()
    
    return jsonify({
        'sucesso': True,
        'estoque': [item.to_dict() for item in itens],
        'calibragem': info_calibragem
    }), 200

@api_bp.route('/estoque/alternar-status', methods=['PUT'])
def alternar_status_estoque():
    if session.get('usuario_perfil') != 'ADMIN':
        return jsonify({'sucesso': False, 'mensagem': 'Acesso negado. Apenas administradores podem alterar o status.'}), 403

    data = request.json or {}
    codigo_kit = data.get('codigo_kit', '').strip()

    if not codigo_kit:
        return jsonify({'sucesso': False, 'mensagem': 'Modelo do kit não informado.'}), 400

    item = EstoqueKit.query.filter_by(codigo_kit=codigo_kit).first()
    if not item:
        return jsonify({'sucesso': False, 'mensagem': 'Modelo não encontrado no estoque.'}), 404

    # Inverte o status atual (se True vira False, se False vira True)
    item.ativo = not item.ativo
    novo_status_str = "ativado" if item.ativo else "inativado"

    mov = MovimentacaoEstoque(
        id_estoque=item.id_estoque,
        tipo_movimentacao='ALTERACAO_STATUS',
        quantidade=0,
        observacao=f"Modelo {novo_status_str} pelo Admin {session.get('usuario_nome')}"
    )
    db.session.add(mov)
    db.session.commit()

    return jsonify({
        'sucesso': True,
        'mensagem': f'O modelo "{codigo_kit}" foi {novo_status_str} com sucesso!',
        'novo_status': item.ativo
    }), 200

@api_bp.route('/estoque/inativar', methods=['PUT'])
def inativar_estoque():
    if session.get('usuario_perfil') != 'ADMIN':
        return jsonify({'sucesso': False, 'mensagem': 'Acesso negado. Apenas administradores podem inativar modelos.'}), 403

    data = request.json or {}
    codigo_kit = data.get('codigo_kit', '').strip()

    if not codigo_kit:
        return jsonify({'sucesso': False, 'mensagem': 'Modelo do kit não informado.'}), 400

    item = EstoqueKit.query.filter_by(codigo_kit=codigo_kit).first()
    if not item:
        return jsonify({'sucesso': False, 'mensagem': 'Modelo não encontrado no estoque.'}), 404

    item.ativo = False

    mov = MovimentacaoEstoque(
        id_estoque=item.id_estoque,
        tipo_movimentacao='INATIVACAO',
        quantidade=0,
        observacao=f"Modelo inativado pelo Admin {session.get('usuario_nome')}"
    )
    db.session.add(mov)
    db.session.commit()

    return jsonify({'sucesso': True, 'mensagem': f'O modelo "{codigo_kit}" foi inativado e bloqueado para novas baixas!'}), 200

@api_bp.route('/estoque/entrada', methods=['POST'])
def entrada_estoque():
    if session.get('usuario_perfil') != 'ADMIN':
        return jsonify({'sucesso': False, 'mensagem': 'Acesso negado.'}), 403

    data = request.json or {}
    codigo_kit = data.get('codigo_kit', '').strip()
    quantidade = data.get('quantidade', 0)
    observacao = data.get('observacao', 'Entrada manual de lote')

    if not codigo_kit or quantidade <= 0:
        return jsonify({'sucesso': False, 'mensagem': 'Informe o modelo e uma quantidade válida.'}), 400

    item = EstoqueKit.query.filter_by(codigo_kit=codigo_kit).first()
    if not item:
        item = EstoqueKit(
            codigo_kit=codigo_kit,
            descricao_kit=f"Kit Escolar {codigo_kit}",
            quantidade_disponivel=quantidade,
            quantidade_reservada=0,
            quantidade_baixada=0
        )
        db.session.add(item)
    else:
        item.quantidade_disponivel += quantidade

    db.session.flush()

    mov = MovimentacaoEstoque(
        id_estoque=item.id_estoque,
        tipo_movimentacao='ENTRADA',
        quantidade=quantidade,
        observacao=f"{observacao} (Admin: {session.get('usuario_nome')})"
    )
    db.session.add(mov)
    db.session.commit()

    return jsonify({'sucesso': True, 'mensagem': f'{quantidade} unidades adicionadas ao modelo {codigo_kit}!'}), 200


@api_bp.route('/estoque/ajustar', methods=['PUT'])
def ajustar_estoque():
    if session.get('usuario_perfil') != 'ADMIN':
        return jsonify({'sucesso': False, 'mensagem': 'Acesso negado.'}), 403

    data = request.json or {}
    codigo_kit = data.get('codigo_kit', '').strip()
    nova_quantidade = data.get('quantidade')

    if not codigo_kit or nova_quantidade is None or nova_quantidade < 0:
        return jsonify({'sucesso': False, 'mensagem': 'Informações inválidas para ajuste.'}), 400

    item = EstoqueKit.query.filter_by(codigo_kit=codigo_kit).first()
    if not item:
        return jsonify({'sucesso': False, 'mensagem': 'Modelo não encontrado no estoque.'}), 404

    qtd_antiga = item.quantidade_disponivel
    item.quantidade_disponivel = nova_quantidade

    mov = MovimentacaoEstoque(
        id_estoque=item.id_estoque,
        tipo_movimentacao='AJUSTE_MANUAL',
        quantidade=nova_quantidade - qtd_antiga,
        observacao=f"Ajuste manual de {qtd_antiga} un para {nova_quantidade} un por {session.get('usuario_nome')}"
    )
    db.session.add(mov)
    db.session.commit()

    return jsonify({'sucesso': True, 'mensagem': f'Estoque do modelo {codigo_kit} redefinido para {nova_quantidade} unidades com sucesso!'}), 200


@api_bp.route('/estoque/disponibilidade', methods=['GET'])
def estoque_disponibilidade():
    estoques = EstoqueKit.query.filter_by(ativo=True).all()
    disponibilidade = {}

    for est in estoques:
        reserva = est.quantidade_reservada or 0
        saidas = getattr(est, 'quantidade_baixada', 0) or 0
        lote_total = est.quantidade_disponivel or 0
        saldo_balcao = max(0, lote_total - saidas)
        sobra = saldo_balcao - reserva

        disponibilidade[est.codigo_kit] = {
            'entrada_total': lote_total,
            'saidas_presenciais': saidas,
            'saldo_balcao': saldo_balcao,
            'reserva_garantida': reserva,
            'sobra_orfaos': max(0, sobra)
        }

    return jsonify({'sucesso': True, 'disponibilidade': disponibilidade}), 200


# ROTA EM FALTA QUE CARREGA OS REGISTOS DO MODAL DE ESTRATIFICAÇÃO
@api_bp.route('/estoque/detalhes/<string:modelo_kit>', methods=['GET'])
def estoque_detalhes_modelo(modelo_kit):
    if session.get('usuario_perfil') != 'ADMIN':
        return jsonify({'sucesso': False, 'mensagem': 'Acesso negado.'}), 403

    modelo_limpo = str(modelo_kit).strip()
    
    baixas = db.session.query(
        HistoricoBaixa.data_baixa,
        HistoricoBaixa.nome_operador,
        HistoricoBaixa.nome_beneficiario,
        HistoricoBaixa.id_colaborador,
        HistoricoBaixa.tipo_publico
    ).filter(
        HistoricoBaixa.modelo_baixa.ilike(modelo_limpo)
    ).order_by(
        HistoricoBaixa.data_baixa.desc()
    ).all()

    lista_estratificada = []
    for b in baixas:
        dt_str = ""
        if b.data_baixa:
            data_brasilia = b.data_baixa - timedelta(hours=3)
            dt_str = data_brasilia.strftime("%d/%m/%Y %H:%M:%S")

        lista_estratificada.append({
            'data_baixa': dt_str,
            'nome_operador': b.nome_operador or 'Sistema / Anônimo',
            'nome_beneficiario': b.nome_beneficiario or 'NÃO INFORMADO',
            'id_colaborador': b.id_colaborador,
            'tipo_publico': b.tipo_publico
        })

    return jsonify({
        'sucesso': True,
        'modelo': modelo_limpo,
        'total_baixado': len(lista_estratificada),
        'historico': lista_estratificada
    }), 200


@api_bp.route('/estoque/exportar/<string:modelo_kit>', methods=['GET'])
def estoque_exportar_modelo(modelo_kit):
    if session.get('usuario_perfil') != 'ADMIN':
        return jsonify({'sucesso': False, 'mensagem': 'Acesso negado.'}), 403

    modelo_limpo = str(modelo_kit).strip()

    baixas = db.session.query(
        HistoricoBaixa.data_baixa,
        HistoricoBaixa.nome_beneficiario,
        HistoricoBaixa.id_colaborador,
        HistoricoBaixa.tipo_publico,
        HistoricoBaixa.nome_operador
    ).filter(
        HistoricoBaixa.modelo_baixa.ilike(modelo_limpo)
    ).order_by(
        HistoricoBaixa.data_baixa.desc()
    ).all()

    output = StringIO()
    writer = csv.writer(output, delimiter=';')

    writer.writerow(['Data/Hora Baixa', 'ID Colaborador', 'Beneficiario / Dependente', 'Publico', 'Operador Responsavel'])

    for b in baixas:
        dt_str = ""
        if b.data_baixa:
            data_brasilia = b.data_baixa - timedelta(hours=3)
            dt_str = data_brasilia.strftime("%d/%m/%Y %H:%M:%S")

        writer.writerow([
            dt_str,
            b.id_colaborador,
            b.nome_beneficiario or 'NÃO INFORMADO',
            b.tipo_publico,
            b.nome_operador or 'Sistema'
        ])

    response = Response(
        "\ufeff" + output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename=extrato_mochila_{modelo_limpo}.csv"}
    )
    return response

@api_bp.route('/validar-senha-admin', methods=['POST'])
def validar_senha_admin():
    id_user = session.get('usuario_id')
    if not id_user or session.get('usuario_perfil') != 'ADMIN':
        return jsonify({'sucesso': False, 'mensagem': 'Acesso não autorizado.'}), 403

    data = request.json or {}
    senha = data.get('senha', '').strip()

    if not senha:
        return jsonify({'sucesso': False, 'mensagem': 'Por favor, informe sua senha de confirmação.'}), 400

    user = Usuario.query.get(id_user)
    if not user or not user.checar_senha(senha):
        return jsonify({'sucesso': False, 'mensagem': 'Senha de confirmação incorreta!'}), 401

    return jsonify({'sucesso': True, 'mensagem': 'Senha validada com sucesso!'}), 200