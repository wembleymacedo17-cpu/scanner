import os
from datetime import timedelta
from flask import Flask, render_template, session, redirect, url_for, request
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix
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
    
    # 1. ProxyFix para identificar cabeçalhos de rede no Render e AWS Nginx
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # 2. Configuração estável de Cookies (compatível com HTTP local e HTTPS Render/AWS)
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = False
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError(f"DATABASE_URL não configurada em: {env_path}")

    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    pool_size = int(os.getenv('DB_POOL_SIZE', 5))
    max_overflow = int(os.getenv('DB_MAX_OVERFLOW', 5))
    pool_timeout = int(os.getenv('DB_POOL_TIMEOUT', 10))
    lock_timeout_ms = int(os.getenv('DB_LOCK_TIMEOUT_MS', 4000))
    statement_timeout_ms = int(os.getenv('DB_STATEMENT_TIMEOUT_MS', 10000))

    engine_options = {
        'pool_size': pool_size,
        'max_overflow': max_overflow,
        'pool_recycle': 300,
        'pool_pre_ping': True,
        'pool_timeout': pool_timeout
    }

    if "postgresql" in database_url:
        engine_options['connect_args'] = {
            'options': f'-c lock_timeout={lock_timeout_ms}ms -c statement_timeout={statement_timeout_ms}ms'
        }

    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = engine_options

    db.init_app(app)

    # 3. Impede que o navegador faça cache de redirecionamentos ou telas ao trocar de usuário
    @app.after_request
    def adicionar_cabecalhos_no_cache(response):
        if not request.path.startswith('/static/'):
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response

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
        user_id = session.get('usuario_id')
        token_local = session.get('session_token')

        if user_id and token_local:
            db.session.expire_all()
            user = Usuario.query.get(user_id)
            if user and user.session_token == token_local:
                user.session_token = None
                db.session.commit()

        session.clear()
        return redirect(url_for('login_page'))

    @app.route('/entregar-kit')
    def entregar_kit():
        if 'usuario_id' not in session:
            return redirect(url_for('login_page'))
        return render_template('cartao_retirada.html')

    @app.route('/historico')
    def historico():
        if 'usuario_id' not in session:
            return redirect(url_for('login_page'))
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