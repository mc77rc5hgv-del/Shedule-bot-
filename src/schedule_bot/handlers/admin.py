import io
import logging
import math
from datetime import UTC
from html import escape

from aiogram import F, Bot, Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schedule_bot.config import Settings
from schedule_bot.keyboards import (
    admin_back_keyboard,
    admin_keyboard,
    admin_submissions_keyboard,
    admin_users_keyboard,
    submission_review_keyboard,
)
from schedule_bot.repositories import (
    GroupRepository,
    ImportLogRepository,
    StatisticsRepository,
    SubmissionRepository,
    UserRepository,
)
from schedule_bot.services.importer import (
    ImportValidationError,
    parse_schedule,
    save_schedule,
    submission_identity,
)
from schedule_bot.structure import normalize_faculty, normalize_specialty

router = Router(name="admin")
MAX_FILE_SIZE = 5 * 1024 * 1024
USERS_PAGE_SIZE = 10
logger = logging.getLogger(__name__)


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
        f"📅 Предстоящих занятий: <b>{stats['upcoming']}</b>\n"
        f"📨 Заявок на проверку: <b>{stats['pending_submissions']}</b>"
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


def _submission_details(item) -> str:
    specialty = f" · {escape(item.specialty)}" if item.specialty else ""
    username = f"@{escape(item.username)}" if item.username else "без username"
    return (
        f"<b>Заявка #{item.id}</b>\n"
        f"От: {username} · <code>{item.user_telegram_id}</code>\n"
        f"Группа: <b>{escape(item.group_name)}</b>\n"
        f"{escape(item.faculty)} факультет{specialty} · {item.course} курс\n"
        f"Занятий: {item.total_rows}\n"
        f"Файл: {escape(item.filename)}"
    )


@router.callback_query(F.data == "admin:submissions")
async def admin_submissions(
    callback: CallbackQuery,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    if not await _guard(callback, settings):
        return
    async with session_factory() as session:
        items = await SubmissionRepository(session).pending()
    if not items:
        text = "<b>Заявки на расписание</b>\n\nНовых заявок нет."
    else:
        text = "<b>Заявки на расписание</b>\n\n" + "\n\n".join(
            _submission_details(item) for item in items
        )
    await callback.message.edit_text(text, reply_markup=admin_submissions_keyboard(items))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:submission:file:"))
async def admin_submission_file(
    callback: CallbackQuery,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    if not await _guard(callback, settings):
        return
    submission_id = int(callback.data.rsplit(":", 1)[1])
    async with session_factory() as session:
        item = await SubmissionRepository(session).get(submission_id)
    if item is None:
        await callback.answer("Заявка не найдена", show_alert=True)
        return
    if item.source_file_content and item.source_filename:
        await callback.message.answer_document(
            BufferedInputFile(item.source_file_content, filename=item.source_filename),
            caption=f"Исходный файл заявки #{item.id}",
        )
    await callback.message.answer_document(
        BufferedInputFile(item.file_content, filename=item.filename),
        caption=_submission_details(item),
        reply_markup=submission_review_keyboard(item.id)
        if item.status == "pending"
        else None,
    )
    await callback.answer("Файл отправлен")


@router.callback_query(F.data.startswith("admin:submission:approve:"))
@router.callback_query(F.data.startswith("admin:submission:reject:"))
async def review_submission(
    callback: CallbackQuery,
    bot: Bot,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    if not await _guard(callback, settings):
        return
    _, _, action, submission_text = callback.data.split(":")
    submission_id = int(submission_text)
    async with session_factory() as session:
        submissions = SubmissionRepository(session)
        item = await submissions.get(submission_id)
        if item is None:
            await callback.answer("Заявка не найдена", show_alert=True)
            return
        if item.status != "pending":
            await callback.answer("Эта заявка уже обработана", show_alert=True)
            return

        if action == "reject":
            await submissions.review(item, "rejected", callback.from_user.id)
            await session.commit()
            result_text = "❌ Заявка отклонена."
            user_text = (
                "❌ Администратор отклонил расписание группы "
                f"<b>{escape(item.group_name)}</b>.\n"
                "Проверьте данные и отправьте исправленный файл повторно."
            )
        else:
            try:
                rows = parse_schedule(item.filename, item.file_content)
                submission_identity(rows)
                result = await save_schedule(session, rows)
                group = await GroupRepository(session).get_by_name(item.group_name)
                if group is not None:
                    await UserRepository(session).set_group(item.user_telegram_id, group.id)
                await submissions.review(item, "approved", callback.from_user.id)
                await ImportLogRepository(session).add(
                    callback.from_user.id,
                    item.filename,
                    result.total,
                    result.created,
                    result.updated,
                )
                await session.commit()
            except ImportValidationError as error:
                await callback.answer(f"Файл больше не проходит проверку: {error}", show_alert=True)
                return
            result_text = (
                "✅ Заявка одобрена.\n"
                f"Добавлено занятий: {result.created}, обновлено: {result.updated}."
            )
            user_text = (
                "✅ Расписание группы "
                f"<b>{escape(item.group_name)}</b> одобрено и опубликовано.\n"
                "Группа уже выбрана в вашем профиле — откройте главное меню."
            )

    try:
        await bot.send_message(item.user_telegram_id, user_text)
    except Exception:
        logger.exception("Could not notify submission author %s", item.user_telegram_id)
    reviewed_text = _submission_details(item) + "\n\n" + result_text
    if callback.message.document:
        await callback.message.edit_caption(caption=reviewed_text, reply_markup=None)
    else:
        await callback.message.edit_text(reviewed_text, reply_markup=admin_back_keyboard())
    await callback.answer("Заявка обработана")


async def _download_document(message: Message, bot: Bot) -> tuple[str, bytes]:
    document = message.document
    filename = document.file_name or "schedule"
    if document.file_size and document.file_size > MAX_FILE_SIZE:
        raise ImportValidationError("Файл слишком большой. Максимальный размер — 5 МБ.")
    file = await bot.get_file(document.file_id)
    buffer = io.BytesIO()
    await bot.download_file(file.file_path, destination=buffer)
    return filename, buffer.getvalue()


async def store_user_submission(
    *,
    message: Message,
    bot: Bot,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    status: Message,
    filename: str,
    content: bytes,
    rows,
    source_filename: str | None = None,
    source_content: bytes | None = None,
    source_media_type: str | None = None,
) -> None:
    group_name, faculty, specialty, course = submission_identity(rows)
    async with session_factory() as session:
        item = await SubmissionRepository(session).add(
            user_telegram_id=message.from_user.id,
            username=message.from_user.username,
            filename=filename,
            file_content=content,
            source_filename=source_filename,
            source_file_content=source_content,
            source_media_type=source_media_type,
            faculty=faculty,
            specialty=specialty,
            course=course,
            group_name=group_name,
            total_rows=len(rows),
        )
        await session.commit()

    delivered = 0
    for admin_id in settings.admins:
        try:
            if source_content and source_filename:
                await bot.send_document(
                    admin_id,
                    BufferedInputFile(source_content, filename=source_filename),
                    caption=f"Исходник для заявки #{item.id}",
                )
            await bot.send_document(
                admin_id,
                BufferedInputFile(content, filename=filename),
                caption=_submission_details(item),
                reply_markup=submission_review_keyboard(item.id),
            )
            delivered += 1
        except Exception:
            logger.exception("Could not deliver submission %s to admin %s", item.id, admin_id)

    if source_content:
        await message.answer_document(
            BufferedInputFile(content, filename=filename),
            caption="ИИ подготовил этот CSV. Окончательную проверку выполнит администратор.",
        )
    await status.edit_text(
        "<b>✅ Заявка отправлена</b>\n\n"
        f"Группа: <b>{escape(group_name)}</b>\n"
        f"Занятий в файле: {len(rows)}\n\n"
        "Администратор проверит расписание. После решения бот пришлет уведомление."
        + ("" if delivered else "\n\nЗаявка сохранена и доступна в админ-панели.")
    )


async def _submit_user_schedule(
    message: Message,
    bot: Bot,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    status = await message.answer("Проверяю файл перед отправкой администратору…")
    try:
        filename, content = await _download_document(message, bot)
        rows = parse_schedule(filename, content)
        await store_user_submission(
            message=message,
            bot=bot,
            settings=settings,
            session_factory=session_factory,
            status=status,
            filename=filename,
            content=content,
            rows=rows,
        )
    except ImportValidationError as error:
        await status.edit_text(
            "<b>Файл не принят</b>\n\n"
            f"{escape(str(error))}\n\n"
            "Можно отправить фото или PDF — ИИ попробует распознать расписание."
        )
    except Exception:
        await status.edit_text("Не удалось обработать файл из-за внутренней ошибки.")
        raise


@router.message(F.document)
async def import_document(
    message: Message,
    bot: Bot,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    if not is_admin_id(message.from_user.id, settings):
        await _submit_user_schedule(message, bot, settings, session_factory)
        return

    status = await message.answer("Проверяю и загружаю расписание…")
    try:
        filename, content = await _download_document(message, bot)
        rows = parse_schedule(filename, content)
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
        await status.edit_text(f"Файл не загружен.\n\n{escape(str(error))}")
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
