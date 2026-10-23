"""One-time migration: copy all rows from SQLite into Postgres.

Usage:
    uv run python scripts/migrate_sqlite_to_postgres.py \
        sqlite+aiosqlite:////path/to/messenger.db \
        postgresql+asyncpg://messenger:messenger@localhost:5432/messenger

- Copies every table in foreign-key order, preserving IDs.
- Target tables are truncated first (safe to re-run).
- Postgres sequences are advanced past the copied ids.
- The source SQLite file is never modified.
"""
import asyncio
import sys
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

TABLES = [
    "users",
    "otp_codes",
    "refresh_sessions",
    "contacts",
    "blocked_users",
    "chats",
    "chat_members",
    "group_invites",
    "messages",
    "artifacts",
    "message_reactions",
]


async def _datetime_columns(conn, table: str) -> set[str]:
    """SQLite column names whose declared type looks like a timestamp."""
    rows = (await conn.execute(text(f'PRAGMA table_info("{table}")'))).all()
    return {
        row[1]
        for row in rows
        if "date" in (row[2] or "").lower() or "time" in (row[2] or "").lower()
    }


def _row_to_postgres(table: str, row: dict, datetime_cols: set[str]) -> dict:
    # SQLite returns timestamps as strings; asyncpg needs datetime objects
    for col in datetime_cols:
        value = row.get(col)
        if isinstance(value, str):
            row[col] = datetime.fromisoformat(value)
    # SQLite returns 0/1 for booleans; asyncpg needs real bools
    if table == "chats":
        row["is_public"] = bool(row["is_public"])
    return row


async def migrate(sqlite_url: str, pg_url: str) -> None:
    source = create_async_engine(sqlite_url)
    target = create_async_engine(pg_url)
    try:
        async with source.begin() as src, target.begin() as dst:
            existing = {
                row[0]
                for row in (
                    await dst.execute(
                        text(
                            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                        )
                    )
                ).all()
            }
            for table in reversed(TABLES):
                if table in existing:
                    await dst.execute(text(f'TRUNCATE "{table}" RESTART IDENTITY CASCADE'))
            for table in TABLES:
                rows = (await src.execute(text(f'SELECT * FROM "{table}"'))).mappings().all()
                if not rows:
                    continue
                columns = list(rows[0].keys())
                placeholders = ", ".join(f":{c}" for c in columns)
                datetime_cols = await _datetime_columns(src, table)
                values = [_row_to_postgres(table, dict(r), datetime_cols) for r in rows]
                await dst.execute(
                    text(
                        f'INSERT INTO "{table}" ({", ".join(columns)}) '
                        f"VALUES ({placeholders})"
                    ),
                    values,
                )
                print(f"{table}: {len(values)} rows")
            for table in TABLES:
                await dst.execute(
                    text(
                        f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                        f'COALESCE(MAX(id), 1)) FROM "{table}"'
                    )
                )
    finally:
        await source.dispose()
        await target.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    asyncio.run(migrate(sys.argv[1], sys.argv[2]))
