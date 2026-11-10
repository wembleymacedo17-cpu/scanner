import os
import sys
from dotenv import load_dotenv

# 1. Garante paths corretos
diretorio_atual = os.path.dirname(os.path.abspath(__file__))
raiz_projeto = os.path.abspath(os.path.join(diretorio_atual, '..', '..'))
if raiz_projeto not in sys.path:
    sys.path.insert(0, raiz_projeto)

env_path = os.path.join(raiz_projeto, '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

from app import create_app
from app.models import db
from app.services.seed_data import carregar_dados_iniciais
from sqlalchemy import text
from alembic.config import Config
from alembic import command


def executar_alembic():
    """Aplica o schema versionado via Alembic."""
    print("\n2. Executando migrações do Alembic (alembic upgrade head)...")
    caminho_ini = os.path.join(raiz_projeto, 'alembic.ini')
    caminho_migracoes = os.path.join(raiz_projeto, 'migrations')

    if os.path.exists(caminho_ini):
        cfg = Config(caminho_ini)
    else:
        cfg = Config()
        cfg.set_main_option('script_location', caminho_migracoes)

    command.upgrade(cfg, 'head')
    print("✅ Migrações do Alembic aplicadas e sincronizadas com sucesso!")


def verificar_e_preparar_banco():
    print("=" * 60)
    print("🚀 SETUP UNIFICADO DE INFRAESTRUTURA, BANCO E CARGA (AWS RDS)")
    print("=" * 60)

    app = create_app()

    with app.app_context():
        # 1. Teste de Conexão Física
        try:
            print("\n1. Testando conexão com o Banco de Dados...")
            with db.engine.connect() as conn:
                versao = conn.execute(text("SELECT version();")).scalar()
                max_conn = conn.execute(text("SHOW max_connections;")).scalar()
                lock_t = conn.execute(text("SHOW lock_timeout;")).scalar()
                print(f"✅ Conectado com sucesso!\n   Motor: {versao[:50]}...")
                print(f"   max_connections: {max_conn} | lock_timeout: {lock_t}")
        except Exception as e:
            print(f"❌ Falha fatal ao conectar no banco: {e}")
            sys.exit(1)

        # 2. Executa Migrações Versionadas via Alembic
        try:
            executar_alembic()
        except Exception as e:
            print(f"❌ Falha na execução do Alembic: {e}")
            sys.exit(1)

        # 3. Auditoria dos Índices
        print("\n3. Verificando índices críticos de busca rápida...")
        indices_necessarios = [
            ("retiradas_dependentes", "codigo_retirada"),
            ("retiradas_jovens_aprendizes", "codigo_retirada"),
            ("estoque_kits", "codigo_kit")
        ]
        with db.engine.connect() as conn:
            for tab, _ in indices_necessarios:
                qtd_indices = conn.execute(text(f"SELECT count(*) FROM pg_indexes WHERE tablename = '{tab}';")).scalar()
                print(f"   - Tabela '{tab}': {qtd_indices} índices ativos.")

        # 4. Carga Inicial de Dados e Calibragem de Estoque
        print("\n4. Executando carga inicial de dados e reservas...")
        try:
            carregar_dados_iniciais(limpar_antes=False)
        except Exception as e:
            print(f"❌ Falha durante a carga de dados: {e}")
            sys.exit(1)

    print("\n" + "=" * 60)
    print("🎉 BANCO, SCHEMA E DADOS 100% PRONTOS EM UM ÚNICO PASSO!")
    print("=" * 60)


if __name__ == '__main__':
    verificar_e_preparar_banco()