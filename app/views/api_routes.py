from flask import Blueprint, jsonify, request
from datetime import datetime
from app.models import db, RetiradaDependente, RetiradaJovemAprendiz

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/buscar/<string:codigo_retirada>', methods=['GET'])
def buscar_retirada(codigo_retirada):
    # Remove prefixos e espaços extras (ex: "RETIRADA_KIT:uuid")
    codigo_str = str(codigo_retirada).strip()
    if 'RETIRADA_KIT:' in codigo_str:
        codigo_str = codigo_str.replace('RETIRADA_KIT:', '').strip()
    
    # 1. Tenta buscar na tabela de Dependentes
    reg_dep = RetiradaDependente.query.filter_by(codigo_retirada=codigo_str).first()
    if reg_dep:
        dados = reg_dep.to_dict()
        dados['tipo_publico'] = 'Dependente'
        return jsonify({
            'sucesso': True,
            'dados': dados
        }), 200

    # 2. Tenta buscar na tabela de Jovens Aprendizes
    reg_jovem = RetiradaJovemAprendiz.query.filter_by(codigo_retirada=codigo_str).first()
    if reg_jovem:
        dados = reg_jovem.to_dict()
        dados['tipo_publico'] = 'Jovem Aprendiz'
        return jsonify({
            'sucesso': True,
            'dados': dados
        }), 200

    return jsonify({
        'sucesso': False,
        'mensagem': 'QR Code / Código de retirada não encontrado.'
    }), 404


@api_bp.route('/dar-baixa', methods=['POST'])
def dar_baixa():
    data = request.json or {}
    codigo_str = data.get('codigo_retirada', '').strip()
    
    if 'RETIRADA_KIT:' in codigo_str:
        codigo_str = codigo_str.replace('RETIRADA_KIT:', '').strip()
    
    if not codigo_str:
        return jsonify({'sucesso': False, 'mensagem': 'Código de retirada não informado.'}), 400

    # Tenta atualizar em Dependentes
    reg_dep = RetiradaDependente.query.filter_by(codigo_retirada=codigo_str).first()
    if reg_dep:
        if reg_dep.status == 'ENTREGUE':
            data_str = reg_dep.data_entrega.strftime("%d/%m/%Y às %H:%M") if reg_dep.data_entrega else ""
            return jsonify({
                'sucesso': False, 
                'mensagem': f'Kit já retirado em {data_str}'
            }), 400
            
        reg_dep.status = 'ENTREGUE'
        reg_dep.data_entrega = datetime.now()
        db.session.commit()
        return jsonify({'sucesso': True, 'mensagem': 'Baixa confirmada com sucesso (Dependente)!'}), 200

    # Tenta atualizar em Jovens Aprendizes
    reg_jovem = RetiradaJovemAprendiz.query.filter_by(codigo_retirada=codigo_str).first()
    if reg_jovem:
        if reg_jovem.status == 'ENTREGUE':
            data_str = reg_jovem.data_entrega.strftime("%d/%m/%Y às %H:%M") if reg_jovem.data_entrega else ""
            return jsonify({
                'sucesso': False, 
                'mensagem': f'Kit já retirado em {data_str}'
            }), 400

        reg_jovem.status = 'ENTREGUE'
        reg_jovem.data_entrega = datetime.now()
        db.session.commit()
        return jsonify({'sucesso': True, 'mensagem': 'Baixa confirmada com sucesso (Jovem Aprendiz)!'}), 200

    return jsonify({'sucesso': False, 'mensagem': 'Registro não encontrado.'}), 404