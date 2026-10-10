import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schedule_bot.repositories import UserRepository

logger = logging.getLogger(__name__)


class UserTrackingMiddleware(BaseMiddleware):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is not None and not user.is_bot:
            try:
                async with self.session_factory() as session:
                    await UserRepository(session).touch(
                        user.id, user.username, user.first_name, user.last_name
                    )
                    await session.commit()
            except SQLAlchemyError:
                logger.exception("Could not update user activity")
        return await handler(event, data)
