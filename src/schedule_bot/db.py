from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from schedule_bot.config import Settings


class Base(DeclarativeBase):
    pass


def create_engine_and_session(
    settings: Settings,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    if settings.database_url.startswith("sqlite"):
        database_path = settings.database_url.rsplit("///", 1)[-1]
        if database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)

    engine = create_async_engine(settings.database_url)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _add_column(connection: Connection, table: str, name: str, definition: str) -> None:
    columns = {column["name"] for column in inspect(connection).get_columns(table)}
    if name not in columns:
        connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def _migrate(connection: Connection) -> None:
    _add_column(
        connection,
        "groups",
        "faculty",
        "VARCHAR(150) NOT NULL DEFAULT 'Факультет не указан'",
    )
    _add_column(connection, "groups", "specialty", "VARCHAR(100)")
    _add_column(connection, "groups", "course", "INTEGER")
    _add_column(connection, "users", "username", "VARCHAR(64)")
    _add_column(connection, "users", "first_name", "VARCHAR(128)")
    _add_column(connection, "users", "last_name", "VARCHAR(128)")
    _add_column(connection, "users", "created_at", "DATETIME")
    _add_column(connection, "users", "last_seen_at", "DATETIME")
    _add_column(connection, "users", "interactions", "INTEGER NOT NULL DEFAULT 0")
    if "schedule_submissions" in inspect(connection).get_table_names():
        _add_column(connection, "schedule_submissions", "source_filename", "VARCHAR(255)")
        _add_column(connection, "schedule_submissions", "source_file_content", "BLOB")
        _add_column(connection, "schedule_submissions", "source_media_type", "VARCHAR(100)")


async def create_schema(engine: AsyncEngine) -> None:
    from schedule_bot import models  # noqa: F401

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(_migrate)
