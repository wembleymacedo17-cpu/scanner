import os
import sys
import pandas as pd
from dotenv import load_dotenv

# 1. Garante que a raiz do projeto esteja no path
diretorio_atual = os.path.dirname(os.path.abspath(__file__))
raiz_projeto = os.path.abspath(os.path.join(diretorio_atual, '..', '..'))
if raiz_projeto not in sys.path:
    sys.path.insert(0, raiz_projeto)

env_path = os.path.join(raiz_projeto, '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

from app.models import (
    db, 
    RetiradaDependente, 
    RetiradaJovemAprendiz, 
    Usuario, 
    HistoricoBaixa, 
    EstoqueKit, 
    MovimentacaoEstoque
)
from app.services.estoque_service import recalibrar_estoque


def carregar_dados_iniciais(limpar_antes=False):
    """
    Executa a carga inicial de dados:
    1. Cria Administrador Master do .env
    2. Importa Jovens Aprendizes (CSV)
    3. Importa Dependentes (Excel)
    4. Recalibra as reservas do estoque físico
    """
    if not limpar_antes and (Usuario.query.first() or RetiradaDependente.query.first()):
        print("ℹ️ Banco já possui registros cadastrados. Pulando carga para evitar duplicações.")
        return

    if limpar_antes:
        print("⚠️ Limpando registros antigos das tabelas de negócio...")
        HistoricoBaixa.query.delete()
        MovimentacaoEstoque.query.delete()
        RetiradaDependente.query.delete()
        RetiradaJovemAprendiz.query.delete()
        Usuario.query.delete()
        db.session.commit()

    # -------------------------------------------------------------
    # 1. CRIAÇÃO DO ADMINISTRADOR MASTER (.ENV)
    # -------------------------------------------------------------
    admin_nome = os.getenv('ADMIN_DEFAULT_NOME', 'Administrador Principal')
    admin_email_env = os.getenv('ADMIN_DEFAULT_EMAIL')
    admin_pass = os.getenv('ADMIN_DEFAULT_PASS')

    if admin_email_env and admin_pass:
        admin_email = admin_email_env.lower().strip()
        admin_existente = Usuario.query.filter_by(email=admin_email).first()
        if not admin_existente:
            admin = Usuario(
                nome=admin_nome,
                email=admin_email,
                perfil='ADMIN'
            )
            admin.set_senha(admin_pass)
            db.session.add(admin)
            db.session.commit()
            print(f"✅ Administrador Master criado! (Email: {admin_email})")
    else:
        print("⚠️ Variáveis de ADMIN padrão não encontradas no .env.")

    # -------------------------------------------------------------
    # 2. CARGA DE JOVENS APRENDIZES (CSV)
    # -------------------------------------------------------------
    caminho_csv = os.path.join(raiz_projeto, 'retiradas_jovens.csv')
    if not os.path.exists(caminho_csv):
        caminho_csv = os.path.join(raiz_projeto, '..', 'retiradas_jovens.csv')

    if os.path.exists(caminho_csv):
        print("📦 Processando e importando Jovens Aprendizes (CSV)...")
        df_jovens = pd.read_csv(caminho_csv)
        df_jovens = df_jovens.where(pd.notnull(df_jovens), None)
        
        qtd_jovens = 0
        for _, row in df_jovens.iterrows():
            registro = RetiradaJovemAprendiz(
                id_retirada=int(row['id_retirada']),
                codigo_retirada=str(row['codigo_retirada']),
                id_colaborador=int(row['id_colaborador']),
                email=row.get('email'),
                telefone=str(row['telefone']) if row.get('telefone') else None,
                qtd_kits=int(row['qtd_kits']),
                resumo_kits=str(row['resumo_kits']),
                status=str(row['status']),
                data_geracao=str(row['data_geracao']) if row.get('data_geracao') else None
            )
            db.session.add(registro)
            qtd_jovens += 1
        
        db.session.commit()
        print(f"✅ {qtd_jovens} registros de Jovens Aprendizes inseridos!")
    else:
        print("⚠️ Arquivo 'retiradas_jovens.csv' não foi encontrado.")

    # -------------------------------------------------------------
    # 3. CARGA DE DEPENDENTES (EXCEL)
    # -------------------------------------------------------------
    caminho_excel = os.path.join(raiz_projeto, 'retiradas_padronizada_corrigida.xlsx')
    if not os.path.exists(caminho_excel):
        caminho_excel = os.path.join(raiz_projeto, '..', 'retiradas_padronizada_corrigida.xlsx')

    if os.path.exists(caminho_excel):
        print("📦 Processando e importando Dependentes (Excel)...")
        df_dep = pd.read_excel(caminho_excel)
        df_dep = df_dep.where(pd.notnull(df_dep), None)
        
        qtd_dep = 0
        for _, row in df_dep.iterrows():
            registro = RetiradaDependente(
                id_retirada=int(row['id_retirada']),
                codigo_retirada=str(row['codigo_retirada']),
                id_colaborador=int(row['id_colaborador']),
                nome_colaborador=row.get('nome_colaborador'),
                log_modificacao_cracha=row.get('log_modificacao_cracha'),
                email=row.get('email'),
                telefone=str(row['telefone']) if row.get('telefone') else None,
                qtd_kits=int(row['qtd_kits']),
                resumo_kits=str(row['resumo_kits']),
                status=str(row['status']),
                data_geracao=str(row['data_geracao']) if row.get('data_geracao') else None,
                necessita_recontato=row.get('necessita_recontato'),
                motivo_recontato=row.get('motivo_recontato')
            )
            db.session.add(registro)
            qtd_dep += 1
        
        db.session.commit()
        print(f"✅ {qtd_dep} registros de Dependentes inseridos!")
    else:
        print("⚠️ Arquivo 'retiradas_padronizada_corrigida.xlsx' não foi encontrado.")

    # -------------------------------------------------------------
    # 4. RECALIBRAÇÃO AUTOMÁTICA DAS RESERVAS DE ESTOQUE
    # -------------------------------------------------------------
    print("🔄 Recalibrando reservas por modelo com base nos cartões importados...")
    res_calibragem = recalibrar_estoque()
    print(f"✅ Estoque calibrado! Reservas garantidas: {res_calibragem['total_reservas_garantidas']} un.")


if __name__ == '__main__':
    from app import create_app
    app = create_app()
    with app.app_context():
        carregar_dados_iniciais(limpar_antes=True)