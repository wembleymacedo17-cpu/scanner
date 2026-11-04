from flask import Blueprint, jsonify, request
from datetime import datetime
from sqlalchemy import or_, cast, String
from app.models import db, RetiradaDependente, RetiradaJovemAprendiz

api_bp = Blueprint('api', __name__, url_prefix='/api')

def extrair_nomes_dependentes(resumo_str):
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


@api_bp.route('/autocompletar', methods=['GET'])
def autocompletar_nome():
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify({'sucesso': True, 'sugestoes': []}), 200

    termo_like = f"%{query}%"
    sugestoes = []

    # 1. Busca nos Dependentes (por nome, resumo ou crachá)
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

    # 2. Busca nos Jovens Aprendizes (pesquisa direta em resumo_kits e id_colaborador)
    limite_restante = 8 - len(sugestoes)
    if limite_restante > 0:
        jovens = RetiradaJovemAprendiz.query.filter(
            or_(
                RetiradaJovemAprendiz.resumo_kits.ilike(termo_like),
                cast(RetiradaJovemAprendiz.id_colaborador, String).ilike(termo_like)
            )
        ).limit(limite_restante).all()

        for j in jovens:
            sugestoes.append({
                'codigo_retirada': j.codigo_retirada,
                'id_colaborador': j.id_colaborador,
                'nome_colaborador': j.extrair_nome_jovem(),
                'dependentes': [j.extrair_nome_jovem()],
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

    if 'RETIRADA_KIT:' in codigo_str:
        codigo_str = codigo_str.replace('RETIRADA_KIT:', '').strip()

    if not codigo_str or index_kit is None:
        return jsonify({'sucesso': False, 'mensagem': 'Dados incompletos para efetuar a baixa.'}), 400

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
    db.session.commit()

    dados_atualizados = reg.to_dict()

    return jsonify({
        'sucesso': True,
        'mensagem': f'Kit {index_kit + 1} baixado com sucesso! (Modelo: {modelo_baixa})',
        'dados': dados_atualizados
    }), 200