import os
import sys
import pandas as pd
from flask import Flask
from dotenv import load_dotenv

# 1. Adiciona a raiz do projeto ao sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load .env
load_dotenv(os.path.join(os.path.dirname(__file__), '../env/.env'))

from app.models import db, RetiradaDependente, RetiradaJovemAprendiz

# Cria um app Flask temporário para o contexto da carga
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def carregar_dados():
    with app.app_context():
        print("🚀 Iniciando carga de dados no Supabase...")

        # -------------------------------------------------------------
        # 1. CARGA DE JOVENS APRENDIZES (CSV)
        # -------------------------------------------------------------
        caminho_csv = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../retiradas_jovens.csv'))
        if not os.path.exists(caminho_csv):
            caminho_csv = os.path.abspath(os.path.join(os.path.dirname(__file__), '../retiradas_jovens.csv'))

        if os.path.exists(caminho_csv):
            print("📦 Processando Jovens Aprendizes...")
            df_jovens = pd.read_csv(caminho_csv)
            df_jovens = df_jovens.where(pd.notnull(df_jovens), None)
            
            qtd_jovens_inseridos = 0
            for _, row in df_jovens.iterrows():
                existente = RetiradaJovemAprendiz.query.filter_by(codigo_retirada=str(row['codigo_retirada'])).first()
                if not existente:
                    registro = RetiradaJovemAprendiz(
                        id_retirada=int(row['id_retirada']),
                        codigo_retirada=str(row['codigo_retirada']),
                        id_colaborador=int(row['id_colaborador']),
                        email=row['email'],
                        telefone=str(row['telefone']) if row['telefone'] else None,
                        qtd_kits=int(row['qtd_kits']),
                        resumo_kits=str(row['resumo_kits']),
                        status=str(row['status']),
                        data_geracao=str(row['data_geracao'])
                    )
                    db.session.add(registro)
                    qtd_jovens_inseridos += 1
            
            db.session.commit()
            print(f"✅ {qtd_jovens_inseridos} registros de Jovens Aprendizes inseridos com sucesso!")
        else:
            print(f"⚠️ Arquivo CSV não encontrado!")

        # -------------------------------------------------------------
        # 2. CARGA DE DEPENDENTES (EXCEL)
        # -------------------------------------------------------------
        caminho_excel = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../retiradas_padronizada_corrigida.xlsx'))
        if not os.path.exists(caminho_excel):
            caminho_excel = os.path.abspath(os.path.join(os.path.dirname(__file__), '../retiradas_padronizada_corrigida.xlsx'))

        if os.path.exists(caminho_excel):
            print("📦 Processando Dependentes...")
            df_dep = pd.read_excel(caminho_excel)
            df_dep = df_dep.where(pd.notnull(df_dep), None)
            
            qtd_dep_inseridos = 0
            for _, row in df_dep.iterrows():
                existente = RetiradaDependente.query.filter_by(codigo_retirada=str(row['codigo_retirada'])).first()
                if not existente:
                    registro = RetiradaDependente(
                        id_retirada=int(row['id_retirada']),
                        codigo_retirada=str(row['codigo_retirada']),
                        id_colaborador=int(row['id_colaborador']),
                        nome_colaborador=row['nome_colaborador'],
                        log_modificacao_cracha=row['log_modificacao_cracha'],
                        email=row['email'],
                        telefone=str(row['telefone']) if row['telefone'] else None,
                        qtd_kits=int(row['qtd_kits']),
                        resumo_kits=str(row['resumo_kits']),
                        status=str(row['status']),
                        data_geracao=str(row['data_geracao']),
                        necessita_recontato=row['necessita_recontato'],
                        motivo_recontato=row['motivo_recontato']
                    )
                    db.session.add(registro)
                    qtd_dep_inseridos += 1
            
            db.session.commit()
            print(f"✅ {qtd_dep_inseridos} registros de Dependentes inseridos com sucesso!")
        else:
            print(f"⚠️ Arquivo Excel não encontrado!")

        print("🎉 Processo de carga finalizado!")

if __name__ == '__main__':
    carregar_dados()