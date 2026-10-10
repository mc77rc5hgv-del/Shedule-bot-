from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schedule_bot.config import Settings
from schedule_bot.keyboards import (
    courses_keyboard,
    faculties_keyboard,
    groups_keyboard,
    home_keyboard,
    home_reply_keyboard,
    specialties_keyboard,
)
from schedule_bot.repositories import GroupRepository, UserRepository
from schedule_bot.structure import FACULTY_SPECIALTIES, SPECIALTY_LABELS

router = Router(name="common")


def _group_details(group) -> str:
    parts = [f"{group.faculty} факультет"]
    if group.specialty:
        parts.append(group.specialty)
    if group.course:
        parts.append(f"{group.course} курс")
    parts.append(group.name)
    return " · ".join(escape(str(part)) for part in parts)


async def _home_text(
    telegram_id: int, session_factory: async_sessionmaker[AsyncSession]
) -> str:
    async with session_factory() as session:
        user = await UserRepository(session).get_with_group(telegram_id)
    if user and user.group:
        return (
            "<b>Главное меню</b>\n"
            f"Ваша группа: {_group_details(user.group)}\n\n"
            "Выберите нужный раздел:"
        )
    return (
        "<b>Добро пожаловать в Shedule BOT</b>\n\n"
        "Сначала выберите свою группу, затем вам станет доступно расписание."
    )


@router.message(CommandStart())
@router.message(Command("menu"))
@router.message(F.text == "🏠 Главное меню")
async def home(
    message: Message,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    text = await _home_text(message.from_user.id, session_factory)
    await message.answer(
        text,
        reply_markup=home_keyboard(message.from_user.id in settings.admins),
    )
    await message.answer("Быстрый доступ:", reply_markup=home_reply_keyboard)


@router.callback_query(F.data == "nav:home")
async def home_callback(
    callback: CallbackQuery,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    text = await _home_text(callback.from_user.id, session_factory)
    await callback.message.edit_text(
        text,
        reply_markup=home_keyboard(callback.from_user.id in settings.admins),
    )
    await callback.answer()


@router.callback_query(F.data == "nav:groups")
@router.message(Command("group"))
async def change_group(
    event: Message | CallbackQuery,
) -> None:
    text = "Выберите факультет:"
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=faculties_keyboard())
        await event.answer()
    else:
        await event.answer(text, reply_markup=faculties_keyboard())


@router.callback_query(F.data == "nav:my_group")
async def my_group(
    callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    async with session_factory() as session:
        user = await UserRepository(session).get_with_group(callback.from_user.id)
    if not user or not user.group:
        await callback.message.edit_text(
            "Группа еще не выбрана.", reply_markup=faculties_keyboard()
        )
    else:
        await callback.message.edit_text(
            "<b>Моя группа</b>\n\n" + _group_details(user.group),
            reply_markup=home_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == "nav:help")
@router.message(Command("help"))
async def help_message(event: Message | CallbackQuery) -> None:
    text = (
        "<b>Как пользоваться ботом</b>\n\n"
        "1. Выберите факультет, направление, курс и группу.\n"
        "2. Откройте «Расписание» и укажите период.\n"
        "3. Кнопка «Следующая пара» сразу покажет ближайшее занятие.\n\n"
        "Сменить группу можно в главном меню. Бот запомнит ваш выбор."
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=home_keyboard())
        await event.answer()
    else:
        await event.answer(text)


@router.callback_query(F.data == "faculties")
async def return_to_faculties(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "Выберите факультет:", reply_markup=faculties_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("faculty_number:"))
async def select_faculty(
    callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    faculty = callback.data.split(":", 1)[1]
    specialties = FACULTY_SPECIALTIES.get(faculty)
    if specialties is None:
        await callback.answer("Факультет не найден", show_alert=True)
        return
    if specialties:
        await callback.message.edit_text(
            f"<b>{faculty} факультет</b>\nВыберите направление:",
            reply_markup=specialties_keyboard(faculty),
        )
        await callback.answer()
        return
    await _show_courses(callback, session_factory, faculty, None)


@router.callback_query(F.data.startswith("specialty:"))
async def select_specialty(
    callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _, faculty, code = callback.data.split(":")
    if code not in FACULTY_SPECIALTIES.get(faculty, ()):
        await callback.answer("Направление не найдено", show_alert=True)
        return
    await _show_courses(callback, session_factory, faculty, SPECIALTY_LABELS[code])


async def _show_courses(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    faculty: str,
    specialty: str | None,
) -> None:
    async with session_factory() as session:
        choices = await GroupRepository(session).list_courses(faculty, specialty)
    if not choices:
        await callback.answer("Для этого раздела расписание пока не загружено", show_alert=True)
        return
    title = f"{faculty} факультет"
    if specialty:
        title += f" · {specialty}"
    await callback.message.edit_text(
        f"<b>{escape(title)}</b>\nВыберите курс:",
        reply_markup=courses_keyboard(choices, faculty),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("back_courses:"))
async def return_to_courses(
    callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    group_id = int(callback.data.split(":")[1])
    async with session_factory() as session:
        group = await GroupRepository(session).get(group_id)
    if group is None:
        await callback.answer("Раздел больше не доступен", show_alert=True)
        return
    await _show_courses(callback, session_factory, group.faculty, group.specialty)


@router.callback_query(F.data.startswith("course:"))
async def select_course(
    callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    representative_id = int(callback.data.split(":")[1])
    async with session_factory() as session:
        repository = GroupRepository(session)
        anchor = await repository.get(representative_id)
        if anchor is None:
            await callback.answer("Курс больше не доступен", show_alert=True)
            return
        groups = await repository.list_by_structure(
            anchor.faculty, anchor.specialty, anchor.course
        )
    title = f"{anchor.faculty} факультет"
    if anchor.specialty:
        title += f" · {anchor.specialty}"
    await callback.message.edit_text(
        f"<b>{escape(title)}</b> · {anchor.course} курс\nВыберите группу:",
        reply_markup=groups_keyboard(groups, anchor.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("groups:"))
async def paginate_groups(
    callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _, anchor_text, page_text = callback.data.split(":")
    anchor_id, page = int(anchor_text), int(page_text)
    async with session_factory() as session:
        repository = GroupRepository(session)
        anchor = await repository.get(anchor_id)
        if anchor is None:
            await callback.answer("Список больше не доступен", show_alert=True)
            return
        groups = await repository.list_by_structure(
            anchor.faculty, anchor.specialty, anchor.course
        )
    await callback.message.edit_reply_markup(
        reply_markup=groups_keyboard(groups, anchor_id, page)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("group:"))
async def select_group(
    callback: CallbackQuery,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    group_id = int(callback.data.split(":")[1])
    async with session_factory() as session:
        group = await GroupRepository(session).get(group_id)
        if group is None:
            await callback.answer("Группа не найдена", show_alert=True)
            return
        await UserRepository(session).set_group(callback.from_user.id, group_id)
        await session.commit()
    await callback.message.edit_text(
        "✅ Группа сохранена\n\n" + _group_details(group),
        reply_markup=home_keyboard(callback.from_user.id in settings.admins),
    )
    await callback.answer("Группа сохранена")
