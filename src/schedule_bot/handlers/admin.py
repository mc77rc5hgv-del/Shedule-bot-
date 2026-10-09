import io

from aiogram import F, Bot, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schedule_bot.config import Settings
from schedule_bot.services.importer import ImportValidationError, parse_schedule, save_schedule

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
        "Отправьте XLSX или CSV как документ. Первая строка — заголовки:\n"
        "<code>group, date, start_time, end_time, subject, teacher, room, type</code>\n\n"
        "Обязательные поля: group, date, start_time, subject. "
        "Русские названия колонок тоже поддерживаются. Повторная загрузка обновляет занятие."
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
