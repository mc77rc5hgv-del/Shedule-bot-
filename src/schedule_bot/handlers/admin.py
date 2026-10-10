import io
import math
from datetime import UTC
from html import escape

from aiogram import F, Bot, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schedule_bot.config import Settings
from schedule_bot.keyboards import admin_back_keyboard, admin_keyboard, admin_users_keyboard
from schedule_bot.repositories import (
    GroupRepository,
    ImportLogRepository,
    StatisticsRepository,
    UserRepository,
)
from schedule_bot.services.importer import ImportValidationError, parse_schedule, save_schedule
from schedule_bot.structure import normalize_faculty, normalize_specialty

router = Router(name="admin")
MAX_FILE_SIZE = 5 * 1024 * 1024
USERS_PAGE_SIZE = 10


def is_admin_id(telegram_id: int, settings: Settings) -> bool:
    return telegram_id in settings.admins


async def _guard(callback: CallbackQuery, settings: Settings) -> bool:
    if not is_admin_id(callback.from_user.id, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return False
    return True


@router.message(Command("admin"))
async def admin_panel(message: Message, settings: Settings) -> None:
    if not is_admin_id(message.from_user.id, settings):
        return
    await message.answer(
        "<b>Админ-панель</b>\nВыберите раздел:",
        reply_markup=admin_keyboard(),
    )


@router.callback_query(F.data == "admin:home")
async def admin_home(callback: CallbackQuery, settings: Settings) -> None:
    if not await _guard(callback, settings):
        return
    await callback.message.edit_text(
        "<b>Админ-панель</b>\nВыберите раздел:",
        reply_markup=admin_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:stats")
async def admin_stats(
    callback: CallbackQuery,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    if not await _guard(callback, settings):
        return
    async with session_factory() as session:
        stats = await StatisticsRepository(session).dashboard()
    text = (
        "<b>Статистика</b>\n\n"
        f"👥 Пользователей: <b>{stats['users']}</b>\n"
        f"• активны за 24 часа: {stats['active_day']}\n"
        f"• за 7 дней: {stats['active_week']}\n"
        f"• за 30 дней: {stats['active_month']}\n\n"
        f"🎓 Групп: <b>{stats['groups']}</b>\n"
        f"📚 Всего занятий: <b>{stats['lessons']}</b>\n"
        f"📅 Предстоящих занятий: <b>{stats['upcoming']}</b>"
    )
    await callback.message.edit_text(text, reply_markup=admin_back_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:users:"))
async def admin_users(
    callback: CallbackQuery,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    if not await _guard(callback, settings):
        return
    page = max(0, int(callback.data.rsplit(":", 1)[1]))
    async with session_factory() as session:
        users, total = await UserRepository(session).page(page, USERS_PAGE_SIZE)
    pages = max(1, math.ceil(total / USERS_PAGE_SIZE))
    page = min(page, pages - 1)
    lines = [f"<b>Пользователи</b> · {total}\n"]
    for user in users:
        username = f"@{escape(user.username)}" if user.username else "без username"
        name = " ".join(
            escape(value) for value in (user.first_name, user.last_name) if value
        ) or "Без имени"
        group = escape(user.group.name) if user.group else "группа не выбрана"
        seen = "—"
        if user.last_seen_at:
            value = user.last_seen_at
            if value.tzinfo is None:
                value = value.replace(tzinfo=UTC)
            seen = value.astimezone(settings.tz).strftime("%d.%m.%Y %H:%M")
        lines.append(
            f"<b>{name}</b> · {username}\n"
            f"<code>{user.telegram_id}</code> · {group}\n"
            f"Был: {seen} · действий: {user.interactions or 0}\n"
        )
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=admin_users_keyboard(page, pages),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:groups")
async def admin_groups(
    callback: CallbackQuery,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    if not await _guard(callback, settings):
        return
    async with session_factory() as session:
        rows = await StatisticsRepository(session).group_breakdown()
    lines = ["<b>Структура групп</b>\n"]
    if not rows:
        lines.append("Группы пока не загружены.")
    for faculty, specialty, course, count in rows:
        title = f"{faculty} факультет"
        if specialty:
            title += f" · {specialty}"
        title += f" · {course or '—'} курс"
        lines.append(f"{escape(title)} — <b>{count}</b>")
    await callback.message.edit_text(
        "\n".join(lines), reply_markup=admin_back_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:imports")
async def admin_imports(
    callback: CallbackQuery,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    if not await _guard(callback, settings):
        return
    async with session_factory() as session:
        imports = await ImportLogRepository(session).recent()
    lines = ["<b>Последние загрузки</b>\n"]
    if not imports:
        lines.append("История пока пуста.")
    for item in imports:
        lines.append(
            f"📄 <b>{escape(item.filename)}</b>\n"
            f"Строк: {item.total_rows}, новых: {item.created_rows}, "
            f"обновлено: {item.updated_rows}"
        )
    await callback.message.edit_text(
        "\n\n".join(lines), reply_markup=admin_back_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:help")
async def admin_help_callback(callback: CallbackQuery, settings: Settings) -> None:
    if not await _guard(callback, settings):
        return
    await callback.message.edit_text(
        "<b>Загрузка расписания</b>\n\n"
        "Отправьте XLSX или CSV как документ. Колонки:\n"
        "<code>faculty, specialty, course, group, date, start_time, end_time, "
        "subject, teacher, room, type</code>\n\n"
        "Обязательны: faculty, course, group, date, start_time, subject. "
        "Для факультетов 2, 3, 4 и 7 обязательно направление.",
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:noop")
async def admin_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.message(Command("setgroup"))
async def set_group_structure(
    message: Message,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    if not is_admin_id(message.from_user.id, settings):
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
    if not is_admin_id(message.from_user.id, settings):
        await message.answer("Загружать расписание может только администратор.")
        return
    document = message.document
    filename = document.file_name or "schedule"
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
            await ImportLogRepository(session).add(
                message.from_user.id,
                filename,
                result.total,
                result.created,
                result.updated,
            )
            await session.commit()
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
