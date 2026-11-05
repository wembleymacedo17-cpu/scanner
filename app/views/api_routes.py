from flask import Blueprint, jsonify, request, session
from datetime import datetime, timedelta
from sqlalchemy import or_, cast, String, func
from app.models import db, RetiradaDependente, RetiradaJovemAprendiz, Usuario, HistoricoBaixa

api_bp = Blueprint('api', __name__, url_prefix='/api')


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

    session['usuario_id'] = user.id_usuario
    session['usuario_nome'] = user.nome
    session['usuario_email'] = user.email
    session['usuario_perfil'] = user.perfil

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
    modelo_baixa = data.get('modelo_baixa', 'Padrão')
    nome_dependente = data.get('nome_dependente', '').strip()

    if 'RETIRADA_KIT:' in codigo_str:
        codigo_str = codigo_str.replace('RETIRADA_KIT:', '').strip()

    if not codigo_str or index_kit is None:
        return jsonify({'sucesso': False, 'mensagem': 'Dados incompletos para baixa.'}), 400

    reg = RetiradaDependente.query.filter_by(codigo_retirada=codigo_str).first()
    tipo_pub = 'Dependente'
    if not reg:
        reg = RetiradaJovemAprendiz.query.filter_by(codigo_retirada=codigo_str).first()
        tipo_pub = 'Jovem Aprendiz'

    if not reg:
        return jsonify({'sucesso': False, 'mensagem': 'Registro de retirada não encontrado.'}), 404

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
