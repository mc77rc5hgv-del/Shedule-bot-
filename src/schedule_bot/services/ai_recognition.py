import base64
import csv
import io
import json
import logging
from dataclasses import dataclass

import aiohttp

from schedule_bot.services.importer import ImportValidationError, LessonRow, parse_schedule, submission_identity

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
logger = logging.getLogger(__name__)
SYSTEM_PROMPT = """Распознай расписание медицинского вуза и верни только JSON без Markdown:
{"status":"ready|needs_info","missing_fields":[],"questions":[],"warnings":[],
"schedule":{"faculty":"2|3|4|5|7|8","specialty":"Лечебное дело|Стоматология|МПД|null",
"course":1,"group":"название","lessons":[{"date":"ДД.ММ.ГГГГ","start_time":"ЧЧ:ММ",
"end_time":"ЧЧ:ММ|null","subject":"предмет","teacher":"...|null","room":"...|null",
"type":"...|null"}]}}
Не выдумывай данные. Обязательны faculty, course, group, date, start_time, subject.
2 факультет: Лечебное дело; 3: МПД или Лечебное дело; 4: Лечебное дело или
Стоматология; 7: все три направления; 5 и 8: specialty=null.
Если данных недостаточно, status=needs_info, перечисли поля и задай короткие вопросы.
Обрабатывай только одну группу. Учитывай подпись пользователя как уточнение.
Если нет конкретных календарных дат, запроси дату начала или привязку недель к датам."""


class AIRecognitionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RecognitionResult:
    rows: list[LessonRow]
    missing_fields: list[str]
    questions: list[str]
    warnings: list[str]

    @property
    def needs_info(self) -> bool:
        return bool(self.missing_fields or self.questions)


async def recognize_schedule(
    *, content: bytes, media_type: str, user_context: str | None,
    api_key: str, model: str,
) -> RecognitionResult:
    if not api_key:
        raise AIRecognitionError("AI-распознавание пока не настроено.")
    allowed = {"image/jpeg", "image/png", "image/gif", "image/webp", "application/pdf"}
    if media_type not in allowed:
        raise AIRecognitionError("Поддерживаются PDF, JPG, PNG, GIF и WEBP.")
    source = {
        "type": "base64", "media_type": media_type,
        "data": base64.b64encode(content).decode("ascii"),
    }
    file_block = {"type": "document" if media_type == "application/pdf" else "image", "source": source}
    prompt = "Распознай приложенное расписание."
    if user_context and user_context.strip():
        prompt += "\nУточнение пользователя:\n" + user_context.strip()
    payload = {
        "model": model, "max_tokens": 12000, "temperature": 0, "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": [file_block, {"type": "text", "text": prompt}]}],
    }
    try:
        timeout = aiohttp.ClientTimeout(total=180)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                ANTHROPIC_URL,
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                json=payload,
            ) as response:
                data = await response.json(content_type=None)
                if response.status >= 400:
                    error_data = data.get("error", {})
                    detail = error_data.get("message", "ошибка AI-сервиса")
                    logger.warning(
                        "Anthropic request failed: status=%s type=%s message=%s request_id=%s",
                        response.status,
                        error_data.get("type"),
                        detail,
                        response.headers.get("request-id"),
                    )
                    raise AIRecognitionError("AI не смог обработать файл: " + detail)
    except TimeoutError as error:
        raise AIRecognitionError("AI не успел обработать файл. Попробуйте ещё раз.") from error
    except aiohttp.ClientError as error:
        raise AIRecognitionError("Не удалось связаться с AI-сервисом.") from error

    answer = "".join(
        block.get("text", "") for block in data.get("content", [])
        if block.get("type") == "text"
    )
    parsed = _parse_json(answer)
    missing = [str(item) for item in parsed.get("missing_fields") or []]
    questions = [str(item) for item in parsed.get("questions") or []]
    warnings = [str(item) for item in parsed.get("warnings") or []]
    if parsed.get("status") == "needs_info" or missing or questions:
        return RecognitionResult([], missing, questions, warnings)

    content_csv = _schedule_to_csv(parsed.get("schedule") or {})
    try:
        rows = parse_schedule("recognized_schedule.csv", content_csv)
        submission_identity(rows)
    except ImportValidationError as error:
        raise AIRecognitionError("Результат не прошёл проверку: " + str(error)) from error
    return RecognitionResult(rows, [], [], warnings)


def rows_to_csv(rows: list[LessonRow]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["faculty", "specialty", "course", "group", "date", "start_time",
                     "end_time", "subject", "teacher", "room", "type"])
    for row in rows:
        writer.writerow([
            row.faculty, row.specialty or "", row.course, row.group,
            row.lesson_date.strftime("%d.%m.%Y"), row.start_time.strftime("%H:%M"),
            row.end_time.strftime("%H:%M") if row.end_time else "",
            row.subject, row.teacher or "", row.room or "", row.lesson_type or "",
        ])
    return buffer.getvalue().encode("utf-8-sig")


def _schedule_to_csv(schedule: dict) -> bytes:
    lessons = schedule.get("lessons")
    if not isinstance(lessons, list) or not lessons:
        raise AIRecognitionError("AI не нашёл занятий в файле.")
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["faculty", "specialty", "course", "group", "date", "start_time",
                     "end_time", "subject", "teacher", "room", "type"])
    for lesson in lessons:
        writer.writerow([
            schedule.get("faculty", ""), schedule.get("specialty") or "",
            schedule.get("course", ""), schedule.get("group", ""),
            lesson.get("date", ""), lesson.get("start_time", ""),
            lesson.get("end_time") or "", lesson.get("subject", ""),
            lesson.get("teacher") or "", lesson.get("room") or "", lesson.get("type") or "",
        ])
    return buffer.getvalue().encode("utf-8-sig")


def _parse_json(text: str) -> dict:
    value = text.strip()
    fence = chr(96) * 3
    if value.startswith(fence):
        value = value.split("\n", 1)[-1].rsplit(fence, 1)[0].strip()
    try:
        result = json.loads(value)
    except json.JSONDecodeError:
        start, end = value.find("{"), value.rfind("}")
        if start < 0 or end <= start:
            raise AIRecognitionError("AI вернул ответ в неизвестном формате.")
        try:
            result = json.loads(value[start:end + 1])
        except json.JSONDecodeError as error:
            raise AIRecognitionError("AI вернул повреждённые данные.") from error
    if not isinstance(result, dict):
        raise AIRecognitionError("AI вернул ответ в неизвестном формате.")
    return result
