import asyncio
from alembic import command
from alembic.config import Config
import os

async def run_migrations():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    alembic_ini_path = os.path.join(base_dir, "alembic.ini")

    config = Config(alembic_ini_path)
    config.set_main_option("script_location", os.path.join(base_dir, "migrations"))

    command.upgrade(config, "head")

if __name__ == "__main__":
    asyncio.run(run_migrations())