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


def period_dates(today: date, period: str) -> tuple[date, date, str]:
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


def format_schedule(group_name: str, start: date, end: date, lessons: list[Lesson]) -> list[str]:
    by_date = defaultdict(list)
    for lesson in lessons:
        by_date[lesson.lesson_date].append(lesson)

    header = f"<b>{escape(group_name)}</b> · {start:%d.%m}–{end:%d.%m.%Y}"
    day_blocks = []
    current = start
    while current <= end:
        items = by_date[current]
        lines = [f"<b>{WEEKDAYS[current.weekday()]}, {current:%d.%m}</b>"]
        if not items:
            lines.append("Занятий нет")
        for lesson in items:
            time_range = lesson.start_time.strftime("%H:%M")
            if lesson.end_time:
                time_range += "–" + lesson.end_time.strftime("%H:%M")
            details = [value for value in (lesson.lesson_type, lesson.teacher, lesson.room) if value]
            lines.append(f"🕘 {time_range}  <b>{escape(lesson.subject)}</b>")
            if details:
                lines.append("   " + " · ".join(escape(value) for value in details))
        day_blocks.append("\n".join(lines))
        current += timedelta(days=1)

    return _split_blocks(header, day_blocks)


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
