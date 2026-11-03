import os
from flask import Flask, render_template
from dotenv import load_dotenv
from app.models import db

load_dotenv(os.path.join(os.path.dirname(__file__), '../env/.env'))

def create_app():
    base_dir = os.path.abspath(os.path.dirname(__file__))
    template_dir = os.path.join(base_dir, 'views', 'html')
    static_dir = os.path.join(base_dir, 'views')

    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    # 1. Rota principal para carregar o HTML da câmera
    @app.route('/')
    def index():
        return render_template('scanner.html')

    # 2. Registra as APIs de busca e baixa
    from app.views.api_routes import api_bp
    app.register_blueprint(api_bp)

    return app