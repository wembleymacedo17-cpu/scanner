import re
from app.models import db, EstoqueKit, RetiradaDependente, RetiradaJovemAprendiz

# Regex para identificar cadastros Órfãos
RE_ORFAOS = re.compile(r'ÓRFÃOS|ORFAOS|AUTOMÁTICOS|AUTOMATICOS', re.IGNORECASE)

# Lista completa de modelos oficiais de kits
MODELOS_OFICIAIS = [
    "Abelha", "Unicornio", "Borboleta", "Cachorro", "Dinossauro",
    "EFI-1", "EFI-2", "EFI-3", "EFI-4", "EFI-5", "EFI-6", "EFI-7", "EFI-8", "EFI-9", "EFI-10", "EFI-11",
    "EFII-1", "EFII-2", "EFII-3", "EFII-4", "EFII-5", "EFII-6", "EFII-7", "EFII-8", "EFII-9", "EFII-10", "EFII-11", "EFII-12", "EFII-13", "EFII-14", "EFII-15", "EFII-16",
    "EM-1", "EM-2", "EM-3", "EM-4", "EM-5", "EM-6", "EM-7", "EM-8", "EM-9", "EM-10", "EM-11", "EM-12", "EM-13"
]

def recalibrar_estoque():
    """
    Calcula de forma ultrarrápida e exata as Reservas Garantidas por modelo 
    e o total de Órfãos (sem escolha) da base de dados.
    """
    # 1. Carrega todos os estoques de uma só vez
    estoques = EstoqueKit.query.filter_by(ativo=True).all()
    mapa_estoque = {e.codigo_kit: e for e in estoques}
    
    contagem_escolhas = {m: 0 for m in MODELOS_OFICIAIS}
    total_orfaos = 0

    # 2. Processa Dependentes (Consultando apenas os campos estritamente necessários)
    deps = db.session.query(RetiradaDependente.resumo_kits, RetiradaDependente.qtd_kits, RetiradaDependente.detalhes_entregas).all()
    for resumo_raw, qtd_kits, detalhes_raw in deps:
        resumo = str(resumo_raw or "")
        
        if RE_ORFAOS.search(resumo):
            total_orfaos += (qtd_kits or 1)
        else:
            # Separa cada dependente/kit individualmente por '|' para contagem exata 1x1
            partes = resumo.split('|')
            for p in partes:
                for m in MODELOS_OFICIAIS:
                    if re.search(r'\b' + re.escape(m) + r'\b', p, re.IGNORECASE):
                        contagem_escolhas[m] += 1
                        break

    # 3. Processa Jovens Aprendizes
    jovens = db.session.query(RetiradaJovemAprendiz.resumo_kits, RetiradaJovemAprendiz.qtd_kits).all()
    for resumo_raw, qtd_kits in jovens:
        resumo = str(resumo_raw or "")
        if RE_ORFAOS.search(resumo):
            total_orfaos += (qtd_kits or 1)
        else:
            partes = resumo.split('|')
            for p in partes:
                for m in MODELOS_OFICIAIS:
                    if re.search(r'\b' + re.escape(m) + r'\b', p, re.IGNORECASE):
                        contagem_escolhas[m] += 1
                        break

    # 4. Atualização em Lote da tabela EstoqueKit
    total_reservas_garantidas = 0
    for m in MODELOS_OFICIAIS:
        qtd_reserva = contagem_escolhas.get(m, 0)
        total_reservas_garantidas += qtd_reserva
        if m in mapa_estoque:
            mapa_estoque[m].quantidade_reservada = qtd_reserva

    db.session.commit()

    return {
        'sucesso': True,
        'orfaos_pendentes': total_orfaos,
        'total_reservas_garantidas': total_reservas_garantidas,
        'reservas_por_modelo': contagem_escolhas
    }