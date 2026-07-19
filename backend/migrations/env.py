"""Configuration Alembic — réutilise la même DATABASE_URL et les mêmes
modèles SQLAlchemy que l'application (app/database.py, app/models.py), pour
éviter toute divergence entre le schéma "vivant" (create_all, dev) et les
migrations versionnées (prod).
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Rend `app` importable quand alembic est lancé depuis la racine du projet
# (prepend_sys_path = . dans alembic.ini s'en charge normalement, ceci est
# une sécurité supplémentaire).
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, DATABASE_URL  # noqa: E402
from app import models  # noqa: E402,F401  (import nécessaire pour peupler Base.metadata)

config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Génère le SQL sans se connecter à une base (`alembic upgrade --sql`)."""
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
    """Applique les migrations directement sur la base connectée."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
