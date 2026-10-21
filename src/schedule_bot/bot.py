import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy import func, select

from schedule_bot.models import Group, Lesson

from schedule_bot.config import Settings
from schedule_bot.db import create_engine_and_session, create_schema
from schedule_bot.handlers import setup_router
from schedule_bot.middleware import UserTrackingMiddleware


logger = logging.getLogger(__name__)


async def _log_schedule_storage(session_factory) -> None:
    async with session_factory() as session:
        rows = await session.execute(
            select(
                Group.id,
                Group.name,
                Group.faculty,
                Group.specialty,
                Group.course,
                func.count(Lesson.id),
                func.min(Lesson.lesson_date),
                func.max(Lesson.lesson_date),
            )
            .outerjoin(Lesson, Lesson.group_id == Group.id)
            .group_by(Group.id)
            .order_by(Group.faculty, Group.specialty, Group.course, Group.name)
        )
        items = list(rows)
    logger.info("Schedule storage diagnostic: groups=%s", len(items))
    for group_id, name, faculty, specialty, course, count, first_date, last_date in items:
        logger.info(
            "Schedule group: id=%s name=%r faculty=%r specialty=%r course=%r "
            "lessons=%s dates=%s..%s",
            group_id,
            name,
            faculty,
            specialty,
            course,
            count,
            first_date,
            last_date,
        )


async def run() -> None:
    settings = Settings()
    engine, session_factory = create_engine_and_session(settings)
    await create_schema(engine)
    await _log_schedule_storage(session_factory)

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
