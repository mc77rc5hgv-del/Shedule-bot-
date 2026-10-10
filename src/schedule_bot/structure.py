from typing import Any

FACULTIES = ("2", "3", "4", "5", "7", "8")
SPECIALTY_LABELS = {
    "medical": "Лечебное дело",
    "dentistry": "Стоматология",
    "mpd": "МПД",
}
FACULTY_SPECIALTIES = {
    "2": ("medical",),
    "3": ("mpd", "medical"),
    "4": ("medical", "dentistry"),
    "5": (),
    "7": ("medical", "dentistry", "mpd"),
    "8": (),
}

_SPECIALTY_ALIASES = {
    "лечебное дело": "medical",
    "лечебное": "medical",
    "лд": "medical",
    "стоматология": "dentistry",
    "стоматологическое": "dentistry",
    "мпд": "mpd",
}


def normalize_faculty(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip().lower()
    text = text.replace("факультет", "").replace("фак.", "").strip()
    if text not in FACULTIES:
        allowed = ", ".join(FACULTIES)
        raise ValueError(f"факультет должен быть одним из: {allowed}")
    return text


def normalize_specialty(value: Any, faculty: str) -> str | None:
    allowed = FACULTY_SPECIALTIES[faculty]
    text = str(value).strip().lower() if value not in (None, "") else ""
    if not allowed:
        if text in ("", "-", "нет"):
            return None
        raise ValueError(f"для {faculty} факультета направление заполнять не нужно")
    code = _SPECIALTY_ALIASES.get(text)
    if code not in allowed:
        labels = ", ".join(SPECIALTY_LABELS[item] for item in allowed)
        raise ValueError(f"для {faculty} факультета направление: {labels}")
    return SPECIALTY_LABELS[code]
