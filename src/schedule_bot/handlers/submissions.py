import io
import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schedule_bot.config import Settings
from schedule_bot.services.ai_recognition import (
    AIRecognitionError,
    recognize_schedule,
    rows_to_csv,
)

from schedule_bot.keyboards import submission_help_keyboard

router = Router(name="submissions")
logger = logging.getLogger(__name__)

TEMPLATE = (
    "faculty,specialty,course,group,date,start_time,end_time,subject,teacher,room,type\n"
    "3,Лечебное дело,2,ЛД-21,01.09.2026,09:00,10:30,Анатомия,Иванов И.И.,203,лекция\n"
).encode("utf-8-sig")

PROMPT = """Преобразуй приложенное расписание учебной группы в CSV-файл UTF-8.

Требования:
1. Верни готовый CSV-файл, не таблицу в Markdown и не пояснение.
2. Первая строка строго:
faculty,specialty,course,group,date,start_time,end_time,subject,teacher,room,type
3. Одна строка — одно занятие. Во всех строках должна быть только одна группа.
4. faculty: только 2, 3, 4, 5, 7 или 8.
5. specialty: «Лечебное дело», «Стоматология» или «МПД». Для факультетов 5 и 8 оставь пустым.
6. course: число от 1 до 6. group: точное название группы.
7. date: ДД.ММ.ГГГГ. Время: ЧЧ:ММ.
8. Обязательны faculty, course, group, date, start_time и subject.
9. Если преподаватель, аудитория, тип занятия или время окончания не указаны, оставь ячейку пустой.
10. Ничего не выдумывай. Неразборчивые данные оставляй пустыми.

Перед созданием файла проверь даты, время и одинаковость факультета, направления, курса и группы во всех строках."""


@router.callback_query(F.data == "submission:help")
async def submission_help(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "<b>Добавить расписание своей группы</b>\n\n"
        "1. Просто отправьте фото, скриншот или PDF — ИИ распознает расписание.\n"
        "2. В подписи желательно указать факультет, направление, курс и группу.\n"
        "3. Также можно отправить готовый XLSX/CSV или скачать шаблон.\n"
        "4. Если данных не хватит, бот напишет, что нужно уточнить.\n"
        "5. Результат уйдет администратору и появится в общем списке после одобрения.\n\n"
        "Обязательные колонки: факультет, курс, группа, дата, начало и предмет. "
        "Максимальный размер — 5 МБ.",
        reply_markup=submission_help_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "submission:template")
async def submission_template(callback: CallbackQuery) -> None:
    await callback.message.answer_document(
        BufferedInputFile(TEMPLATE, filename="schedule_template.csv"),
        caption="Заполните шаблон расписанием одной группы и отправьте его обратно боту.",
    )
    await callback.answer("Шаблон отправлен")


@router.callback_query(F.data == "submission:prompt")
async def submission_prompt(callback: CallbackQuery) -> None:
    await callback.message.answer(
        "<b>Промпт для нейросети</b>\n\n"
        "Скопируйте текст ниже и приложите к нему исходное расписание:\n\n"
        f"<pre>{escape(PROMPT)}</pre>"
    )
    await callback.answer("Промпт отправлен")


AI_MEDIA_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}
AI_MAX_FILE_SIZE = 10 * 1024 * 1024


@router.message(F.photo)
async def recognize_photo(
    message: Message,
    bot: Bot,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    photo = message.photo[-1]
    await _recognize_media(
        message=message,
        bot=bot,
        settings=settings,
        session_factory=session_factory,
        file_id=photo.file_id,
        file_size=photo.file_size,
        filename="schedule_photo.jpg",
        media_type="image/jpeg",
    )


@router.message(F.document.mime_type.in_(AI_MEDIA_TYPES))
async def recognize_document(
    message: Message,
    bot: Bot,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    document = message.document
    await _recognize_media(
        message=message,
        bot=bot,
        settings=settings,
        session_factory=session_factory,
        file_id=document.file_id,
        file_size=document.file_size,
        filename=document.file_name or "schedule_source",
        media_type=document.mime_type,
    )


async def _recognize_media(
    *,
    message: Message,
    bot: Bot,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    file_id: str,
    file_size: int | None,
    filename: str,
    media_type: str,
) -> None:
    if file_size and file_size > AI_MAX_FILE_SIZE:
        await message.answer("Файл слишком большой. Максимальный размер для AI — 10 МБ.")
        return
    status = await message.answer(
        "🤖 Распознаю расписание. Это может занять до двух минут…"
    )
    try:
        telegram_file = await bot.get_file(file_id)
        buffer = io.BytesIO()
        await bot.download_file(telegram_file.file_path, destination=buffer)
        source_content = buffer.getvalue()
        result = await recognize_schedule(
            content=source_content,
            media_type=media_type,
            user_context=message.caption,
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
        )
        if result.needs_info:
            lines = [
                "<b>Нужно уточнить данные</b>",
                "",
                *[f"• {escape(value)}" for value in result.questions],
            ]
            if result.missing_fields:
                lines.extend(
                    [
                        "",
                        "Не удалось определить: "
                        + ", ".join(escape(value) for value in result.missing_fields),
                    ]
                )
            lines.extend(
                [
                    "",
                    "Отправьте файл повторно и добавьте подпись, например:",
                    "<code>3 факультет, Лечебное дело, 2 курс, группа ЛД-21</code>",
                ]
            )
            await status.edit_text("\n".join(lines))
            return

        csv_content = rows_to_csv(result.rows)
        from schedule_bot.handlers.admin import store_user_submission

        await store_user_submission(
            message=message,
            bot=bot,
            settings=settings,
            session_factory=session_factory,
            status=status,
            filename="recognized_schedule.csv",
            content=csv_content,
            rows=result.rows,
            source_filename=filename,
            source_content=source_content,
            source_media_type=media_type,
        )
        if result.warnings:
            await message.answer(
                "<b>Замечания AI:</b>\n"
                + "\n".join(f"• {escape(value)}" for value in result.warnings)
            )
    except AIRecognitionError as error:
        logger.warning("Schedule recognition rejected: %s", error)
        await status.edit_text(
            "<b>Не удалось распознать расписание</b>\n\n"
            f"{escape(str(error))}\n\n"
            "Попробуйте более четкое изображение или добавьте факультет, курс и группу "
            "в подпись."
        )
    except Exception:
        await status.edit_text("Произошла внутренняя ошибка при распознавании.")
        raise
