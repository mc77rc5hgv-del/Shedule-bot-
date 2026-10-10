import io
from html import escape

from aiogram import F, Bot, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schedule_bot.config import Settings
from schedule_bot.repositories import GroupRepository
from schedule_bot.services.importer import ImportValidationError, parse_schedule, save_schedule
from schedule_bot.structure import normalize_faculty, normalize_specialty

router = Router(name="admin")
MAX_FILE_SIZE = 5 * 1024 * 1024


def is_admin(message: Message, settings: Settings) -> bool:
    return bool(message.from_user and message.from_user.id in settings.admins)


@router.message(Command("admin"))
async def admin_help(message: Message, settings: Settings) -> None:
    if not is_admin(message, settings):
        return
    await message.answer(
        "<b>Загрузка расписания</b>\n\n"
        "Колонки XLSX/CSV:\n"
        "<code>faculty, specialty, course, group, date, start_time, end_time, "
        "subject, teacher, room, type</code>\n\n"
        "Обязательны: faculty, course, group, date, start_time, subject. "
        "Для факультетов 2, 3, 4 и 7 также обязательно направление. "
        "Русские названия колонок поддерживаются.\n\n"
        "Ручная настройка: "
        "<code>/setgroup Группа | 3 | Лечебное дело | 2</code>. "
        "Для 5 и 8 факультетов вместо направления укажите дефис."
    )


@router.message(Command("setgroup"))
async def set_group_structure(
    message: Message,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    if not is_admin(message, settings):
        return
    parts = [part.strip() for part in message.text.partition(" ")[2].split("|")]
    if len(parts) != 4 or not parts[3].isdigit() or not 1 <= int(parts[3]) <= 9:
        await message.answer(
            "Формат: <code>/setgroup Группа | 3 | Лечебное дело | 2</code>"
        )
        return
    group_name, faculty_raw, specialty_raw, course_text = parts
    try:
        faculty = normalize_faculty(faculty_raw)
        specialty = normalize_specialty(specialty_raw, faculty)
    except ValueError as error:
        await message.answer(str(error))
        return
    async with session_factory() as session:
        repository = GroupRepository(session)
        group = await repository.get_by_name(group_name)
        if group is None:
            await message.answer("Такая группа не найдена.")
            return
        await repository.set_structure(group, faculty, specialty, int(course_text))
        await session.commit()
    details = f"{faculty} факультет"
    if specialty:
        details += f", {specialty}"
    await message.answer(
        f"Группа <b>{escape(group_name)}</b>: {escape(details)}, {int(course_text)} курс."
    )


@router.message(F.document)
async def import_document(
    message: Message,
    bot: Bot,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    if not is_admin(message, settings):
        await message.answer("Загружать расписание может только администратор.")
        return
    document = message.document
    filename = document.file_name or ""
    if document.file_size and document.file_size > MAX_FILE_SIZE:
        await message.answer("Файл слишком большой. Максимальный размер — 5 МБ.")
        return

    status = await message.answer("Проверяю и загружаю расписание…")
    try:
        file = await bot.get_file(document.file_id)
        buffer = io.BytesIO()
        await bot.download_file(file.file_path, destination=buffer)
        rows = parse_schedule(filename, buffer.getvalue())
        async with session_factory() as session:
            result = await save_schedule(session, rows)
    except ImportValidationError as error:
        await status.edit_text(f"Файл не загружен.\n\n{error}")
        return
    except Exception:
        await status.edit_text("Не удалось загрузить файл из-за внутренней ошибки.")
        raise

    await status.edit_text(
        "<b>Расписание загружено</b>\n"
        f"Строк: {result.total}\n"
        f"Добавлено: {result.created}\n"
        f"Обновлено: {result.updated}\n"
        f"Групп в файле: {result.groups}"
    )
