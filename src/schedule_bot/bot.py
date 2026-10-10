import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from schedule_bot.config import Settings
from schedule_bot.db import create_engine_and_session, create_schema
from schedule_bot.handlers import setup_router
from schedule_bot.middleware import UserTrackingMiddleware


async def run() -> None:
    settings = Settings()
    engine, session_factory = create_engine_and_session(settings)
    await create_schema(engine)

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dispatcher = Dispatcher()
    dispatcher.update.outer_middleware(UserTrackingMiddleware(session_factory))
    dispatcher.include_router(setup_router())

    try:
        await bot.delete_webhook(drop_pending_updates=False)
        await dispatcher.start_polling(
            bot,
            settings=settings,
            session_factory=session_factory,
            allowed_updates=dispatcher.resolve_used_update_types(),
        )
    finally:
        await bot.session.close()
        await engine.dispose()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    asyncio.run(run())
