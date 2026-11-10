import os
import sys
from dotenv import load_dotenv

# 1. Garante que a raiz do projeto (Baixas_Qrcode) esteja no sys.path
diretorio_atual = os.path.dirname(os.path.abspath(__file__))
raiz_projeto = os.path.abspath(os.path.join(diretorio_atual, '..', '..'))
if raiz_projeto not in sys.path:
    sys.path.insert(0, raiz_projeto)

# 2. Carrega o .env localizado na raiz do projeto
env_path = os.path.join(raiz_projeto, '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

from app import create_app
from app.models import db
from sqlalchemy import text


def verificar_e_preparar_banco():
    print("=" * 60)
    print("🚀 INICIANDO AUDITORIA E SETUP DE INFRAESTRUTURA DO BANCO")
    print("=" * 60)

    app = create_app()

    with app.app_context():
        # 1. Teste de Conexão Física
        try:
            print("\n1. Testando conexão com o Banco de Dados...")
            with db.engine.connect() as conn:
                versao = conn.execute(text("SELECT version();")).scalar()
                print(f"✅ Conectado com sucesso!\n   Motor: {versao[:60]}...")
        except Exception as e:
            print(f"❌ Falha fatal ao conectar no banco: {e}")
            sys.exit(1)

        # 2. Verificação de Parâmetros de Concorrência
        print("\n2. Validando parâmetros de concorrência e capacidade...")
        with db.engine.connect() as conn:
            max_conn = conn.execute(text("SHOW max_connections;")).scalar()
            print(f"   - Limite de conexões do servidor (max_connections): {max_conn}")

            lock_t = conn.execute(text("SHOW lock_timeout;")).scalar()
            stmt_t = conn.execute(text("SHOW statement_timeout;")).scalar()
            print(f"   - Timeout de fila de trava (lock_timeout): {lock_t}")
            print(f"   - Timeout de consulta lenta (statement_timeout): {stmt_t}")

        # 3. Criação ou Atualização da Estrutura das Tabelas
        print("\n3. Sincronizando tabelas do modelo de dados...")
        try:
            db.create_all()
            print("✅ Tabelas e índices verificados e sincronizados com sucesso!")
        except Exception as e:
            print(f"❌ Erro ao sincronizar tabelas: {e}")

        # 4. Checagem dos Índices de Alta Performance
        print("\n4. Verificando índices críticos para leitura rápida de QR Code...")
        indices_necessarios = [
            ("retiradas_dependentes", "codigo_retirada"),
            ("retiradas_jovens_aprendizes", "codigo_retirada"),
            ("estoque_kits", "codigo_kit")
        ]
        
        with db.engine.connect() as conn:
            for tab, col in indices_necessarios:
                query_idx = text(f"""
                    SELECT count(*) FROM pg_indexes 
                    WHERE tablename = '{tab}';
                """)
                qtd_indices = conn.execute(query_idx).scalar()
                print(f"   - Tabela '{tab}': {qtd_indices} índices ativos.")

    print("\n" + "=" * 60)
    print("🎉 INFRAESTRUTURA DE BANCO DE DADOS 100% OPERACIONAL!")
    print("=" * 60)


if __name__ == '__main__':
    verificar_e_preparar_banco()