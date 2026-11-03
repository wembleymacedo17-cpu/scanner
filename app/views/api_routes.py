from flask import Blueprint, jsonify, request
from datetime import datetime
from app.models import db, RetiradaDependente, RetiradaJovemAprendiz

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/buscar/<string:codigo_retirada>', methods=['GET'])
def buscar_retirada(codigo_retirada):
    codigo_str = str(codigo_retirada).strip()
    if 'RETIRADA_KIT:' in codigo_str:
        codigo_str = codigo_str.replace('RETIRADA_KIT:', '').strip()
    
    # 1. Tenta Dependentes
    reg_dep = RetiradaDependente.query.filter_by(codigo_retirada=codigo_str).first()
    if reg_dep:
        dados = reg_dep.to_dict()
        dados['tipo_publico'] = 'Dependente'
        return jsonify({'sucesso': True, 'dados': dados}), 200

    # 2. Tenta Jovens Aprendizes
    reg_jovem = RetiradaJovemAprendiz.query.filter_by(codigo_retirada=codigo_str).first()
    if reg_jovem:
        dados = reg_jovem.to_dict()
        dados['tipo_publico'] = 'Jovem Aprendiz'
        return jsonify({'sucesso': True, 'dados': dados}), 200

    return jsonify({'sucesso': False, 'mensagem': 'QR Code não encontrado.'}), 404


@api_bp.route('/dar-baixa-item', methods=['POST'])
def dar_baixa_item():
    data = request.json or {}
    codigo_str = data.get('codigo_retirada', '').strip()
    index_kit = data.get('index_kit')
    modelo_baixa = data.get('modelo_baixa', 'Padrão')

    if 'RETIRADA_KIT:' in codigo_str:
        codigo_str = codigo_str.replace('RETIRADA_KIT:', '').strip()

    if not codigo_str or index_kit is None:
        return jsonify({'sucesso': False, 'mensagem': 'Dados incompletos para baixa.'}), 400

    # Tenta localizar registro em Dependentes ou Jovens
    reg = RetiradaDependente.query.filter_by(codigo_retirada=codigo_str).first()
    tipo_pub = 'Dependente'
    if not reg:
        reg = RetiradaJovemAprendiz.query.filter_by(codigo_retirada=codigo_str).first()
        tipo_pub = 'Jovem Aprendiz'

    if not reg:
        return jsonify({'sucesso': False, 'mensagem': 'Registro não encontrado.'}), 404

    # Recupera o JSON de detalhes de entregas existentes
    detalhes = reg.detalhes_entregas or {}
    chave_item = f"kit_{index_kit}"

    if detalhes.get(chave_item, {}).get('entregue') == True:
        return jsonify({'sucesso': False, 'mensagem': 'Este kit individual já teve baixa realizada.'}), 400

    # Registra a baixa individual do kit
    detalhes[chave_item] = {
        'entregue': True,
        'modelo': modelo_baixa,
        'data_entrega': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # Calcula se todos os kits foram entregues ou se é entrega parcial
    total_kits = reg.qtd_kits
    qtd_entregues = sum(1 for k, v in detalhes.items() if v.get('entregue') == True)

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