from pathlib import Path

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


async def create_schema(engine: AsyncEngine) -> None:
    from schedule_bot import models  # noqa: F401

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
