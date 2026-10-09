from datetime import datetime

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schedule_bot.config import Settings
from schedule_bot.repositories import LessonRepository, UserRepository
from schedule_bot.services.schedule import format_schedule, period_dates

router = Router(name="schedule")

BUTTON_PERIODS = {
    "📅 Сегодня": "today",
    "➡️ Завтра": "tomorrow",
    "🗓 Ближайшие 3 дня": "three",
    "📆 Неделя": "week",
}


@router.message(F.text.in_(BUTTON_PERIODS))
async def send_schedule(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    period = BUTTON_PERIODS[message.text]
    today = datetime.now(settings.tz).date()
    start, end, _ = period_dates(today, period)

    async with session_factory() as session:
        user = await UserRepository(session).get_with_group(message.from_user.id)
        if user is None or user.group is None:
            await message.answer("Сначала выберите группу: /group")
            return
        lessons = await LessonRepository(session).between(user.group.id, start, end)
        messages = format_schedule(user.group.name, start, end, lessons)

    for text in messages:
        await message.answer(text)
