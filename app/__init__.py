import os
from flask import Flask, render_template
from dotenv import load_dotenv
from app.models import db

# 1. Carrega o .env localizado na RAIZ do projeto (Baixas_Qrcode/.env)
raiz_projeto = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
env_path = os.path.join(raiz_projeto, '.env')

if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

def create_app():
    base_dir = os.path.abspath(os.path.dirname(__file__))
    template_dir = os.path.join(base_dir, 'views', 'html')
    static_dir = os.path.join(base_dir, 'views')

    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    
    # 2. Busca a URL do banco
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        raise ValueError(
            f"A variável 'DATABASE_URL' não foi encontrada! "
            f"Verifique se o arquivo .env existe em: {env_path}"
        )

    # Garante compatibilidade do prefixo da URL com o SQLAlchemy
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    # Rota raiz do HTML
    @app.route('/')
    def index():
        return render_template('cartao_retirada.html')

    # REGISTRO DAS ROTAS DA API (Faltava esta parte)
    from app.views.api_routes import api_bp
    app.register_blueprint(api_bp)

    return app