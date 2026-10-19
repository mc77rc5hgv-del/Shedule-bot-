from datetime import date, time
from types import SimpleNamespace

from schedule_bot.services.schedule import (
    calendar_weeks,
    format_month_by_weeks,
    format_schedule,
    period_dates,
)


def test_three_day_period():
    start, end, title = period_dates(date(2026, 10, 9), "three")
    assert start == date(2026, 10, 9)
    assert end == date(2026, 10, 11)
    assert "3 дня" in title


def test_month_period_is_current_calendar_month():
    start, end, title = period_dates(date(2026, 10, 19), "month")
    assert start == date(2026, 10, 1)
    assert end == date(2026, 10, 31)
    assert "октября" in title


def test_calendar_weeks_are_monday_to_sunday():
    weeks = calendar_weeks(date(2026, 10, 1), date(2026, 10, 31))
    assert weeks[0] == (date(2026, 10, 1), date(2026, 10, 4))
    assert weeks[1] == (date(2026, 10, 5), date(2026, 10, 11))
    assert weeks[-1] == (date(2026, 10, 26), date(2026, 10, 31))


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


def test_month_has_one_page_per_calendar_week():
    pages = format_month_by_weeks(
        "ИС-21", date(2026, 10, 1), date(2026, 10, 31), []
    )
    assert len(pages) == 5
    assert "неделя 1/5" in pages[0]
    assert "неделя 5/5" in pages[-1]
