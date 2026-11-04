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