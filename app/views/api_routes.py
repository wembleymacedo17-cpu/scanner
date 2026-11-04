from flask import Blueprint, jsonify, request
from datetime import datetime
from app.models import db, RetiradaDependente, RetiradaJovemAprendiz

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/buscar/<string:termo_busca>', methods=['GET'])
def buscar_retirada(termo_busca):
    termo = str(termo_busca).strip()
    if 'RETIRADA_KIT:' in termo:
        termo = termo.replace('RETIRADA_KIT:', '').strip()
    
    # Limpa caracteres não numéricos para verificar se é CPF/Crachá
    apenas_numeros = "".join(filter(str.isdigit, termo))
    
    reg_dep = None
    reg_jovem = None

    # 1. Tenta buscar por Código de Retirada (UUID)
    reg_dep = RetiradaDependente.query.filter_by(codigo_retirada=termo).first()
    if not reg_dep:
        reg_jovem = RetiradaJovemAprendiz.query.filter_by(codigo_retirada=termo).first()

    # 2. Se não achou e possui números, tenta por Crachá (id_colaborador)
    if not reg_dep and not reg_jovem and apenas_numeros.isdigit():
        id_num = int(apenas_numeros)
        reg_dep = RetiradaDependente.query.filter_by(id_colaborador=id_num).first()
        if not reg_dep:
            reg_jovem = RetiradaJovemAprendiz.query.filter_by(id_colaborador=id_num).first()

    # 3. Retorna os resultados encontrados
    if reg_dep:
        dados = reg_dep.to_dict()
        dados['tipo_publico'] = 'Dependente'
        return jsonify({'sucesso': True, 'dados': dados}), 200

    if reg_jovem:
        dados = reg_jovem.to_dict()
        dados['tipo_publico'] = 'Jovem Aprendiz'
        return jsonify({'sucesso': True, 'dados': dados}), 200

    return jsonify({'sucesso': False, 'mensagem': 'Nenhum registro encontrado para este QR Code, Crachá ou CPF.'}), 404

from flask import Blueprint, jsonify, request
from datetime import datetime
from app.models import db, RetiradaDependente, RetiradaJovemAprendiz

api_bp = Blueprint('api', __name__, url_prefix='/api')

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

    if reg_dep:
        dados = reg_dep.to_dict()
        dados['tipo_publico'] = 'Dependente'
        return jsonify({'sucesso': True, 'dados': dados}), 200

    if reg_jovem:
        dados = reg_jovem.to_dict()
        dados['tipo_publico'] = 'Jovem Aprendiz'
        return jsonify({'sucesso': True, 'dados': dados}), 200

    return jsonify({'sucesso': False, 'mensagem': 'Nenhum registro encontrado para este QR Code, Crachá ou CPF.'}), 404


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
    dados_atualizados['tipo_publico'] = tipo_pub

    return jsonify({
        'sucesso': True,
        'mensagem': f'Kit {index_kit + 1} baixado com sucesso! (Modelo: {modelo_baixa})',
        'dados': dados_atualizados
    }), 200