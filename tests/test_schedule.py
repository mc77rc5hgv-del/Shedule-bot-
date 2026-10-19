from datetime import date, time
from types import SimpleNamespace

from schedule_bot.services.schedule import (
    format_month_by_weeks,
    format_schedule,
    period_dates,
)


def test_three_day_period():
    start, end, title = period_dates(date(2026, 10, 9), "three")
    assert start == date(2026, 10, 9)
    assert end == date(2026, 10, 11)
    assert "3 дня" in title


def test_month_period_is_thirty_days():
    start, end, title = period_dates(date(2026, 10, 19), "month")
    assert start == date(2026, 10, 19)
    assert end == date(2026, 11, 17)
    assert "30 дней" in title


def test_format_escapes_html():
    lesson = SimpleNamespace(
        lesson_date=date(2026, 10, 9),
        start_time=time(9),
        end_time=time(10, 30),
        subject="<Алгебра>",
        teacher="Иванов",
        room="101",
        lesson_type="лекция",
    )
    messages = format_schedule("ИС-21", date(2026, 10, 9), date(2026, 10, 9), [lesson])
    assert "&lt;Алгебра&gt;" in messages[0]
    assert "09:00–10:30" in messages[0]


def test_month_is_split_into_weeks():
    messages = format_month_by_weeks(
        "ИС-21", date(2026, 10, 19), date(2026, 11, 17), []
    )
    assert len(messages) == 5
    assert "Неделя 1" in messages[0]
    assert "Неделя 5" in messages[-1]
