from datetime import date, time
from types import SimpleNamespace

from schedule_bot.services.schedule import format_schedule, period_dates


def test_three_day_period():
    start, end, title = period_dates(date(2026, 10, 9), "three")
    assert start == date(2026, 10, 9)
    assert end == date(2026, 10, 11)
    assert "3 дня" in title


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
