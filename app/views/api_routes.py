from flask import Blueprint, jsonify, request
from datetime import datetime
from app.models import db, RetiradaDependente, RetiradaJovemAprendiz

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/buscar/<uuid:codigo_retirada>', methods=['GET'])
def buscar_retirada(codigo_retirada):
    codigo_str = str(codigo_retirada)
    
    # 1. Tenta buscar na tabela de Dependentes
    reg_dep = RetiradaDependente.query.filter_by(codigo_retirada=codigo_str).first()
    if reg_dep:
        return jsonify({
            'sucesso': True,
            'dados': reg_dep.to_dict()
        }), 200

    # 2. Tenta buscar na tabela de Jovens Aprendizes
    reg_jovem = RetiradaJovemAprendiz.query.filter_by(codigo_retirada=codigo_str).first()
    if reg_jovem:
        return jsonify({
            'sucesso': True,
            'dados': reg_jovem.to_dict()
        }), 200

    return jsonify({
        'sucesso': False,
        'mensagem': 'QR Code / Código de retirada não encontrado.'
    }), 404


@api_bp.route('/dar-baixa', methods=['POST'])
def dar_baixa():
    data = request.json or {}
    codigo_str = data.get('codigo_retirada')
    
    if not codigo_str:
        return jsonify({'sucesso': False, 'mensagem': 'Código de retirada não informado.'}), 400

    # Tenta atualizar em Dependentes
    reg_dep = RetiradaDependente.query.filter_by(codigo_retirada=codigo_str).first()
    if reg_dep:
        if reg_dep.status == 'ENTREGUE':
            return jsonify({
                'sucesso': False, 
                'mensagem': f'Kit já retirado em {reg_dep.data_entrega.strftime("%d/%m/%Y às %H:%M")}'
            }), 400
            
        reg_dep.status = 'ENTREGUE'
        reg_dep.data_entrega = datetime.now()
        db.session.commit()
        return jsonify({'sucesso': True, 'mensagem': 'Baixa confirmada com sucesso (Dependente)!'}), 200

    # Tenta atualizar em Jovens Aprendizes
    reg_jovem = RetiradaJovemAprendiz.query.filter_by(codigo_retirada=codigo_str).first()
    if reg_jovem:
        if reg_jovem.status == 'ENTREGUE':
            return jsonify({
                'sucesso': False, 
                'mensagem': f'Kit já retirado em {reg_jovem.data_entrega.strftime("%d/%m/%Y às %H:%M")}'
            }), 400

        reg_jovem.status = 'ENTREGUE'
        reg_jovem.data_entrega = datetime.now()
        db.session.commit()
        return jsonify({'sucesso': True, 'mensagem': 'Baixa confirmada com sucesso (Jovem Aprendiz)!'}), 200

    return jsonify({'sucesso': False, 'mensagem': 'Registro não encontrado.'}), 404