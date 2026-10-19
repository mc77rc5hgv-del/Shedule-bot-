from collections import defaultdict
from datetime import date, timedelta
from html import escape

from schedule_bot.models import Lesson

WEEKDAYS = (
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
)
MONTHS = (
    "",
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)
MONTHS_TITLES = (
    "",
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
)


def period_dates(today: date, period: str) -> tuple[date, date, str]:
    if period == "month":
        start = today.replace(day=1)
        next_month = (
            start.replace(year=start.year + 1, month=1)
            if start.month == 12
            else start.replace(month=start.month + 1)
        )
        end = next_month - timedelta(days=1)
        return start, end, f"Расписание на {MONTHS[start.month]}"

    periods = {
        "today": (0, 0, "Расписание на сегодня"),
        "tomorrow": (1, 1, "Расписание на завтра"),
        "three": (0, 2, "Расписание на ближайшие 3 дня"),
        "week": (0, 6, "Расписание на ближайшие 7 дней"),
    }
    if period not in periods:
        raise ValueError("Неизвестный период")
    start_delta, end_delta, title = periods[period]
    return today + timedelta(days=start_delta), today + timedelta(days=end_delta), title


def calendar_weeks(start: date, end: date) -> list[tuple[date, date]]:
    weeks = []
    cursor = start
    while cursor <= end:
        days_until_sunday = 6 - cursor.weekday()
        week_end = min(cursor + timedelta(days=days_until_sunday), end)
        weeks.append((cursor, week_end))
        cursor = week_end + timedelta(days=1)
    return weeks


def format_schedule(group_name: str, start: date, end: date, lessons: list[Lesson]) -> list[str]:
    by_date = _group_by_date(lessons)
    header = f"<b>{escape(group_name)}</b> · {start:%d.%m}–{end:%d.%m.%Y}"
    blocks = []
    current = start
    while current <= end:
        blocks.append(_day_block(current, by_date[current], show_empty=True))
        current += timedelta(days=1)
    return _split_blocks(header, blocks)


def format_month_by_weeks(
    group_name: str, start: date, end: date, lessons: list[Lesson]
) -> list[str]:
    by_date = _group_by_date(lessons)
    weeks = calendar_weeks(start, end)
    pages = []
    for index, (week_start, week_end) in enumerate(weeks, start=1):
        header = (
            f"<b>{escape(group_name)}</b>\n"
            f"<b>{MONTHS_TITLES[start.month]} {start.year}</b> · "
            f"неделя {index}/{len(weeks)}\n"
            f"{week_start.day} {MONTHS[week_start.month]} — "
            f"{week_end.day} {MONTHS[week_end.month]}"
        )
        blocks = []
        current = week_start
        while current <= week_end:
            if by_date[current]:
                blocks.append(_day_block(current, by_date[current], show_empty=False))
            current += timedelta(days=1)
        if not blocks:
            blocks = ["Занятий на этой неделе нет"]
        pages.append(_split_blocks(header, blocks)[0])
    return pages


def _group_by_date(lessons: list[Lesson]) -> dict[date, list[Lesson]]:
    by_date = defaultdict(list)
    for lesson in lessons:
        by_date[lesson.lesson_date].append(lesson)
    return by_date


def _day_block(current: date, lessons: list[Lesson], *, show_empty: bool) -> str:
    lines = [f"<b>{WEEKDAYS[current.weekday()]}, {current:%d.%m}</b>"]
    if not lessons and show_empty:
        lines.append("Занятий нет")
    for lesson in lessons:
        time_range = lesson.start_time.strftime("%H:%M")
        if lesson.end_time:
            time_range += "–" + lesson.end_time.strftime("%H:%M")
        details = [value for value in (lesson.lesson_type, lesson.teacher, lesson.room) if value]
        lines.append(f"🕘 {time_range}  <b>{escape(lesson.subject)}</b>")
        if details:
            lines.append("   " + " · ".join(escape(value) for value in details))
    return "\n".join(lines)


def _split_blocks(header: str, blocks: list[str], limit: int = 4000) -> list[str]:
    messages: list[str] = []
    current = header
    for block in blocks:
        candidate = current + "\n\n" + block
        if len(candidate) > limit and current != header:
            messages.append(current)
            current = header + "\n\n" + block
        else:
            current = candidate
    messages.append(current)
    return messages
