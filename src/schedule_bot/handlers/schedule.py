from datetime import datetime

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schedule_bot.config import Settings
from schedule_bot.keyboards import (
    schedule_periods_keyboard,
    schedule_result_keyboard,
    subject_result_keyboard,
    subjects_keyboard,
)
from schedule_bot.repositories import LessonRepository, UserRepository
from schedule_bot.services.schedule import (
    format_month_by_weeks,
    format_schedule,
    period_dates,
)

router = Router(name="schedule")

BUTTON_PERIODS = {
    "📅 Сегодня": "today",
    "➡️ Завтра": "tomorrow",
    "🗓 Ближайшие 3 дня": "three",
    "📆 Неделя": "week",
}


@router.callback_query(F.data == "schedule:menu")
async def schedule_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "<b>Расписание</b>\nВыберите действие:",
        reply_markup=schedule_periods_keyboard(),
    )
    await callback.answer()


@router.callback_query(
    F.data.in_(
        {
            "schedule:today",
            "schedule:tomorrow",
            "schedule:three",
            "schedule:week",
            "schedule:month",
        }
    )
)
async def schedule_callback(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    period = callback.data.split(":", 1)[1]
    await _send_period(
        callback.message,
        callback.from_user.id,
        period,
        session_factory,
        settings,
        edit=True,
    )
    await callback.answer()


@router.callback_query(F.data == "schedule:next")
async def next_lesson(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    now = datetime.now(settings.tz)
    async with session_factory() as session:
        user = await UserRepository(session).get_with_group(callback.from_user.id)
        if user is None or user.group is None:
            await callback.answer("Сначала выберите группу", show_alert=True)
            return
        lesson = await LessonRepository(session).next_lesson(
            user.group.id, now.date(), now.time().replace(tzinfo=None)
        )
        if lesson is None:
            await callback.message.edit_text(
                "На ближайшие 30 дней занятий не найдено.",
                reply_markup=schedule_result_keyboard(),
            )
        else:
            text = format_schedule(
                user.group.name, lesson.lesson_date, lesson.lesson_date, [lesson]
            )[0]
            await callback.message.edit_text(
                "<b>Следующая пара</b>\n\n" + text,
                reply_markup=schedule_result_keyboard(),
            )
    await callback.answer()


@router.callback_query(F.data == "schedule:subject")
async def subject_menu(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    await _show_subjects(callback, session_factory, settings, page=0)


@router.callback_query(F.data.startswith("subjects:"))
async def subject_page(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    page = int(callback.data.split(":", 1)[1])
    await _show_subjects(callback, session_factory, settings, page=page)


async def _show_subjects(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    page: int,
) -> None:
    now = datetime.now(settings.tz)
    async with session_factory() as session:
        user = await UserRepository(session).get_with_group(callback.from_user.id)
        if user is None or user.group is None:
            await callback.answer("Сначала выберите группу", show_alert=True)
            return
        choices = await LessonRepository(session).future_subjects(
            user.group.id, now.date(), now.time().replace(tzinfo=None)
        )
    if not choices:
        await callback.answer("Предстоящих предметов не найдено", show_alert=True)
        return
    await callback.message.edit_text(
        "<b>Когда будет предмет?</b>\n"
        "Выберите предмет из расписания вашей группы:",
        reply_markup=subjects_keyboard(choices, page),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("subject:"))
async def subject_next_date(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    value = callback.data.split(":", 1)[1]
    if value == "noop":
        await callback.answer()
        return
    lesson_id = int(value)
    now = datetime.now(settings.tz)
    async with session_factory() as session:
        users = UserRepository(session)
        lessons = LessonRepository(session)
        user = await users.get_with_group(callback.from_user.id)
        source = await lessons.get(lesson_id)
        if user is None or user.group is None:
            await callback.answer("Сначала выберите группу", show_alert=True)
            return
        if source is None or source.group_id != user.group.id:
            await callback.answer("Предмет больше не доступен", show_alert=True)
            return
        lesson = await lessons.next_subject(
            user.group.id,
            source.subject,
            now.date(),
            now.time().replace(tzinfo=None),
        )
    if lesson is None:
        await callback.answer("Следующее занятие не найдено", show_alert=True)
        return
    text = format_schedule(
        user.group.name, lesson.lesson_date, lesson.lesson_date, [lesson]
    )[0]
    await callback.message.edit_text(
        f"<b>Ближайшее занятие по предмету</b>\n\n{text}",
        reply_markup=subject_result_keyboard(),
    )
    await callback.answer()


@router.message(F.text.in_(BUTTON_PERIODS))
async def send_schedule(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    await _send_period(
        message,
        message.from_user.id,
        BUTTON_PERIODS[message.text],
        session_factory,
        settings,
        edit=False,
    )


async def _send_period(
    message: Message,
    telegram_id: int,
    period: str,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    *,
    edit: bool,
) -> None:
    today = datetime.now(settings.tz).date()
    try:
        start, end, _ = period_dates(today, period)
    except ValueError:
        return

    async with session_factory() as session:
        user = await UserRepository(session).get_with_group(telegram_id)
        if user is None or user.group is None:
            if edit:
                await message.edit_text("Сначала выберите группу: /group")
            else:
                await message.answer("Сначала выберите группу: /group")
            return
        lessons = await LessonRepository(session).between(user.group.id, start, end)
        messages = (
            format_month_by_weeks(user.group.name, start, end, lessons)
            if period == "month"
            else format_schedule(user.group.name, start, end, lessons)
        )

    if edit:
        await message.edit_text(messages[0])
        for text in messages[1:-1]:
            await message.answer(text)
        if len(messages) > 1:
            await message.answer(messages[-1], reply_markup=schedule_result_keyboard())
        else:
            await message.edit_reply_markup(reply_markup=schedule_result_keyboard())
    else:
        for index, text in enumerate(messages):
            await message.answer(
                text,
                reply_markup=schedule_result_keyboard() if index == len(messages) - 1 else None,
            )
