from schedule_bot.services.importer import ImportValidationError, parse_schedule


def test_parse_csv_with_russian_headers():
    content = (
        "группа;дата;начало;конец;предмет;преподаватель;аудитория;тип\n"
        "ИС-21;10.10.2026;09:00;10:30;Математика;Иванов И.И.;203;лекция\n"
    ).encode()

    rows = parse_schedule("schedule.csv", content)

    assert len(rows) == 1
    assert rows[0].group == "ИС-21"
    assert rows[0].subject == "Математика"
    assert rows[0].start_time.hour == 9


def test_rejects_unknown_extension():
    try:
        parse_schedule("schedule.pdf", b"data")
    except ImportValidationError as error:
        assert "xlsx" in str(error)
    else:
        raise AssertionError("ImportValidationError was not raised")
