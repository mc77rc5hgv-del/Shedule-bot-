from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schedule_bot.keyboards import (
    FACULTIES,
    courses_keyboard,
    faculties_keyboard,
    faculty_root_keyboard,
    groups_keyboard,
    schedule_keyboard,
)
from schedule_bot.repositories import GroupRepository, UserRepository

router = Router(name="common")


async def show_faculty_root(
    message: Message, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    async with session_factory() as session:
        groups = await GroupRepository(session).list()
    if not groups:
        await message.answer("Расписание пока не загружено. Попробуйте позже.")
        return
    await message.answer(
        "Откройте список факультетов:", reply_markup=faculty_root_keyboard()
    )


@router.message(CommandStart())
async def start(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        user = await UserRepository(session).get_with_group(message.from_user.id)
    if user and user.group:
        await message.answer(
            f"С возвращением! Ваша группа: <b>{escape(user.group.name)}</b>",
            reply_markup=schedule_keyboard,
        )
    else:
        await show_faculty_root(message, session_factory)


@router.message(Command("group"))
@router.message(F.text == "🔄 Сменить группу")
async def change_group(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await show_faculty_root(message, session_factory)


@router.callback_query(F.data == "faculty_catalog")
async def show_faculty_catalog(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "Выберите факультет:", reply_markup=faculties_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("faculty_name:"))
async def select_named_faculty(
    callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    code = callback.data.split(":", 1)[1]
    faculty = FACULTIES.get(code)
    if faculty is None:
        await callback.answer("Факультет не найден", show_alert=True)
        return
    async with session_factory() as session:
        choices = await GroupRepository(session).list_courses(faculty)
    if not choices:
        await callback.answer(
            f"Для «{faculty}» расписание пока не загружено", show_alert=True
        )
        return
    await callback.message.edit_text(
        f"<b>{escape(faculty)}</b>\nВыберите курс:",
        reply_markup=courses_keyboard(choices),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("faculty:"))
async def return_to_courses(
    callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    representative_id = int(callback.data.split(":")[1])
    async with session_factory() as session:
        repository = GroupRepository(session)
        group = await repository.get(representative_id)
        if group is None:
            await callback.answer("Факультет больше не доступен", show_alert=True)
            return
        choices = await repository.list_courses(group.faculty)
    await callback.message.edit_text(
        f"<b>{escape(group.faculty)}</b>\nВыберите курс:",
        reply_markup=courses_keyboard(choices),
    )
    await callback.answer()


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
        groups = await repository.list_by_structure(anchor.faculty, anchor.course)
    course_label = f"{anchor.course} курс" if anchor.course else "Курс не указан"
    await callback.message.edit_text(
        f"<b>{escape(anchor.faculty)}</b> · {course_label}\nВыберите группу:",
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
        groups = await repository.list_by_structure(anchor.faculty, anchor.course)
    await callback.message.edit_reply_markup(
        reply_markup=groups_keyboard(groups, anchor_id, page)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("group:"))
async def select_group(
    callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    group_id = int(callback.data.split(":")[1])
    async with session_factory() as session:
        group = await GroupRepository(session).get(group_id)
        if group is None:
            await callback.answer("Группа не найдена", show_alert=True)
            return
        await UserRepository(session).set_group(callback.from_user.id, group_id)
        await session.commit()
    await callback.message.edit_text(f"Вы выбрали группу <b>{escape(group.name)}</b>.")
    await callback.message.answer("Что показать?", reply_markup=schedule_keyboard)
    await callback.answer()


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Помощь")
async def help_message(message: Message) -> None:
    await message.answer(
        "Выберите период кнопкой внизу. Команда /group меняет факультет, курс и группу. "
        "Если расписание выглядит неверно, сообщите администратору."
    )
