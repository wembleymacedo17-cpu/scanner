import os
import sys
import pandas as pd
from flask import Flask
from dotenv import load_dotenv

# 1. Adiciona a raiz do projeto ao sys.path
raiz_projeto = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, raiz_projeto)

# Tenta carregar o .env da raiz do projeto ou da pasta env/
env_path = os.path.join(raiz_projeto, '.env')
if not os.path.exists(env_path):
    env_path = os.path.join(os.path.dirname(__file__), '../env/.env')

load_dotenv(env_path)

from app.models import db, RetiradaDependente, RetiradaJovemAprendiz, Usuario

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def carregar_dados():
    with app.app_context():
        db.create_all()
        print("🚀 Criando tabelas e buscando credenciais do Administrador no .env...")

        # -------------------------------------------------------------
        # BUSCA DE CREDENCIAIS DO ADMINISTRADOR A PARTIR DO .ENV
        # -------------------------------------------------------------
        admin_nome = os.getenv('ADMIN_DEFAULT_NOME')
        admin_email = os.getenv('ADMIN_DEFAULT_EMAIL').lower().strip()
        admin_pass = os.getenv('ADMIN_DEFAULT_PASS')

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
            print(f"✅ Administrador criado a partir do .env! (Email: {admin_email})")
        else:
            print(f"ℹ️ Administrador ({admin_email}) já cadastrado na base de dados.")

        print("🎉 Processo de inicialização finalizado com sucesso!")

if __name__ == '__main__':
    carregar_dados()