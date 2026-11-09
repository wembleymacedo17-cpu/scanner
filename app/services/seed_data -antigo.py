import os
import sys
import pandas as pd
from flask import Flask
from dotenv import load_dotenv


raiz_projeto = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.insert(0, raiz_projeto)

# Carrega o .env da raiz do projeto
env_path = os.path.join(raiz_projeto, '.env')
if not os.path.exists(env_path):
    env_path = os.path.join(raiz_projeto, 'env/.env')

load_dotenv(env_path)

# Importa os models mapeados do projeto
from app.models import db, RetiradaDependente, RetiradaJovemAprendiz, Usuario, HistoricoBaixa, EstoqueKit, MovimentacaoEstoque

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def limpar_e_carregar_dados():
    with app.app_context():
        print("⚠️ ATENÇÃO: Removendo (DROP) todas as tabelas e dados antigos do banco...")
        db.drop_all()  # Limpa tudo do banco de dados para testar do zero
        
        print("🚀 Criando a estrutura limpa das tabelas via models.py...")
        db.create_all()

        # -------------------------------------------------------------
        # 1. CRIAÇÃO DO ADMINISTRADOR MASTER (.ENV)
        # -------------------------------------------------------------
        admin_nome = os.getenv('ADMIN_DEFAULT_NOME', 'Administrador Principal')
        admin_email_env = os.getenv('ADMIN_DEFAULT_EMAIL')
        admin_pass = os.getenv('ADMIN_DEFAULT_PASS')

        if admin_email_env and admin_pass:
            admin_email = admin_email_env.lower().strip()
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
        # Procurando o arquivo na raiz do projeto ou diretórios acima
        # -------------------------------------------------------------
        caminho_csv = os.path.join(raiz_projeto, 'retiradas_jovens.csv')
        if not os.path.exists(caminho_csv):
            caminho_csv = os.path.join(raiz_projeto, '../retiradas_jovens.csv')

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
            print(f"✅ {qtd_jovens} registros de Jovens Aprendizes inseridos com sucesso!")
        else:
            print(f"⚠️ Arquivo 'retiradas_jovens.csv' não foi encontrado na raiz.")

        # -------------------------------------------------------------
        # 3. CARGA DE DEPENDENTES (EXCEL)
        # -------------------------------------------------------------
        caminho_excel = os.path.join(raiz_projeto, 'retiradas_padronizada_corrigida.xlsx')
        if not os.path.exists(caminho_excel):
            caminho_excel = os.path.join(raiz_projeto, '../retiradas_padronizada_corrigida.xlsx')

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
            print(f"✅ {qtd_dep} registros de Dependentes inseridos com sucesso!")
        else:
            print(f"⚠️ Arquivo 'retiradas_padronizada_corrigida.xlsx' não foi encontrado na raiz.")

        print("🎉 Banco limpo e populado do zero com sucesso!")

if __name__ == '__main__':
    limpar_e_carregar_dados()