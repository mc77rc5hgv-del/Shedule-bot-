from schedule_bot.services.importer import (
    ImportValidationError,
    parse_schedule,
    submission_identity,
)


def test_parse_csv_with_structure():
    content = (
        "факультет;направление;курс;группа;дата;начало;конец;предмет;"
        "преподаватель;аудитория;тип\n"
        "3;Лечебное дело;2 курс;ЛД-21;10.10.2026;09:00;10:30;"
        "Математика;Иванов И.И.;203;лекция\n"
    ).encode()

    rows = parse_schedule("schedule.csv", content)

    assert len(rows) == 1
    assert rows[0].faculty == "3"
    assert rows[0].specialty == "Лечебное дело"
    assert rows[0].course == 2
    assert rows[0].group == "ЛД-21"


def test_faculty_without_specialty():
    content = (
        "faculty,course,group,date,start_time,subject\n"
        "5,1,Ф5-11,2026-10-10,09:00,Анатомия\n"
    ).encode()
    assert parse_schedule("schedule.csv", content)[0].specialty is None


def test_rejects_unknown_extension():
    try:
        parse_schedule("schedule.pdf", b"data")
    except ImportValidationError as error:
        assert "xlsx" in str(error)
    else:
        raise AssertionError("ImportValidationError was not raised")


def test_submission_accepts_one_group():
    content = (
        "faculty,course,group,date,start_time,subject\n"
        "5,1,Ф5-11,2026-10-10,09:00,Анатомия\n"
        "5,1,Ф5-11,2026-10-11,10:40,Биология\n"
    ).encode()
    rows = parse_schedule("schedule.csv", content)
    assert submission_identity(rows) == ("Ф5-11", "5", None, 1)


def test_submission_rejects_multiple_groups():
    content = (
        "faculty,course,group,date,start_time,subject\n"
        "5,1,Ф5-11,2026-10-10,09:00,Анатомия\n"
        "5,1,Ф5-12,2026-10-11,10:40,Биология\n"
    ).encode()
    rows = parse_schedule("schedule.csv", content)
    try:
        submission_identity(rows)
    except ImportValidationError as error:
        assert "одной группы" in str(error)
    else:
        raise AssertionError("ImportValidationError was not raised")
