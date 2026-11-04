import os
from flask import Flask, render_template, session, redirect, url_for
from dotenv import load_dotenv
from app.models import db, Usuario

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
    app.secret_key = os.getenv('SECRET_KEY', 'chave_secreta_funfarme_2026')
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError(f"DATABASE_URL não configurada em: {env_path}")

    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 10,
        'max_overflow': 20,
        'pool_recycle': 300,
        'pool_pre_ping': True
    }

    db.init_app(app)

    @app.route('/')
    def index():
        if 'usuario_id' not in session:
            return redirect(url_for('login_page'))
        return render_template('index.html', usuario=session.get('usuario_nome'), perfil=session.get('usuario_perfil'))

    @app.route('/login')
    def login_page():
        return render_template('login.html')

    @app.route('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login_page'))

    @app.route('/entregar-kit')
    def entregar_kit():
        return render_template('cartao_retirada.html')

    @app.route('/historico')
    def historico():
        return render_template('historico.html')

    @app.route('/gerar-acesso')
    def gerar_acesso():
        if session.get('usuario_perfil') != 'ADMIN':
            return redirect(url_for('index'))
        return render_template('gerar_acesso.html')

    @app.route('/dashboard')
    def dashboard():
        if session.get('usuario_perfil') != 'ADMIN':
            return redirect(url_for('index'))
        return render_template('dashboard.html')

    @app.route('/estoque')
    def estoque():
        if session.get('usuario_perfil') != 'ADMIN':
            return redirect(url_for('index'))
        return render_template('estoque.html')

    from app.views.api_routes import api_bp
    app.register_blueprint(api_bp)

    return app