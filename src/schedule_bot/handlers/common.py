from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schedule_bot.keyboards import (
    courses_keyboard,
    faculties_keyboard,
    groups_keyboard,
    schedule_keyboard,
    specialties_keyboard,
)
from schedule_bot.repositories import GroupRepository, UserRepository
from schedule_bot.structure import FACULTY_SPECIALTIES, SPECIALTY_LABELS

router = Router(name="common")


async def show_faculties(message: Message) -> None:
    await message.answer("Выберите факультет:", reply_markup=faculties_keyboard())


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
        await show_faculties(message)


@router.message(Command("group"))
@router.message(F.text == "🔄 Сменить группу")
async def change_group(message: Message) -> None:
    await show_faculties(message)


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
    course_label = f"{anchor.course} курс" if anchor.course else "Курс не указан"
    title = f"{anchor.faculty} факультет"
    if anchor.specialty:
        title += f" · {anchor.specialty}"
    await callback.message.edit_text(
        f"<b>{escape(title)}</b> · {course_label}\nВыберите группу:",
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
        "Команда /group открывает выбор факультета, направления, курса и группы. "
        "Затем выберите нужный период кнопкой внизу."
    )
