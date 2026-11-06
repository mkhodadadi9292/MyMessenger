from logging.config import fileConfig
from alembic import context
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from data.models.user_model import Base

config = context.config

if "DATABASE_URL" in os.environ:
    config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    from sqlalchemy import create_engine
    connectable = create_engine(
        config.get_main_option("sqlalchemy.url"),
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()