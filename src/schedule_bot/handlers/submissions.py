from html import escape

from aiogram import F, Router
from aiogram.types import BufferedInputFile, CallbackQuery

from schedule_bot.keyboards import submission_help_keyboard

router = Router(name="submissions")

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
        "1. Скачайте CSV-шаблон или подготовьте XLSX/CSV с помощью нейросети.\n"
        "2. Заполните расписание только одной группы.\n"
        "3. Отправьте готовый файл этому боту как документ.\n"
        "4. Бот проверит файл и отправит заявку администратору.\n"
        "5. После одобрения группа появится в общем списке, а вы получите уведомление.\n\n"
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
