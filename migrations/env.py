import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context
from dotenv import load_dotenv

# 1. Adiciona a raiz do projeto ao sys.path para conseguir importar o pacote 'app'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 2. Carrega as variáveis de ambiente a partir da pasta env/.env
load_dotenv(os.path.join(os.path.dirname(__file__), '../env/.env'))

# Configuração do objeto Alembic Config
config = context.config

# Configuração do sistema de logs do Python
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 3. Define a URL da base de dados do Supabase dinamicamente a partir do .env
database_url = os.getenv("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

# 4. Importa o objeto db do teu pacote app.models e define os metadados para autogenerate
from app.models import db
target_metadata = db.metadata


def run_migrations_offline() -> None:
    """Executa as migrações no modo 'offline'."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Executa as migrações no modo 'online'."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()