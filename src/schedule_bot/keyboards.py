from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from schedule_bot.structure import FACULTIES, FACULTY_SPECIALTIES, SPECIALTY_LABELS

PAGE_SIZE = 12

schedule_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Сегодня"), KeyboardButton(text="➡️ Завтра")],
        [KeyboardButton(text="🗓 Ближайшие 3 дня"), KeyboardButton(text="📆 Неделя")],
        [KeyboardButton(text="🔄 Сменить группу"), KeyboardButton(text="ℹ️ Помощь")],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите период",
)


def faculties_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for faculty in FACULTIES:
        builder.button(
            text=f"🏛 {faculty} факультет", callback_data=f"faculty_number:{faculty}"
        )
    builder.adjust(2)
    return builder.as_markup()


def specialties_keyboard(faculty: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code in FACULTY_SPECIALTIES[faculty]:
        builder.button(
            text=SPECIALTY_LABELS[code],
            callback_data=f"specialty:{faculty}:{code}",
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="⬅️ К факультетам", callback_data="faculties"))
    return builder.as_markup()


def courses_keyboard(
    choices: list[tuple[int | None, int]], faculty: str
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for course, representative_id in choices:
        label = f"{course} курс" if course is not None else "Курс не указан"
        builder.button(text=f"🎓 {label}", callback_data=f"course:{representative_id}")
    builder.adjust(2)
    back_callback = (
        f"faculty_number:{faculty}" if FACULTY_SPECIALTIES[faculty] else "faculties"
    )
    back_text = "⬅️ К направлениям" if FACULTY_SPECIALTIES[faculty] else "⬅️ К факультетам"
    builder.row(InlineKeyboardButton(text=back_text, callback_data=back_callback))
    return builder.as_markup()


def groups_keyboard(groups, anchor_id: int, page: int = 0) -> InlineKeyboardMarkup:
    page_count = max(1, (len(groups) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(max(0, page), page_count - 1)
    builder = InlineKeyboardBuilder()
    for group in groups[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]:
        builder.button(text=group.name, callback_data=f"group:{group.id}")
    builder.adjust(2)
    navigation = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(text="⬅️", callback_data=f"groups:{anchor_id}:{page - 1}")
        )
    if page + 1 < page_count:
        navigation.append(
            InlineKeyboardButton(text="➡️", callback_data=f"groups:{anchor_id}:{page + 1}")
        )
    if navigation:
        builder.row(*navigation)
    builder.row(InlineKeyboardButton(text="⬅️ К курсам", callback_data=f"back_courses:{anchor_id}"))
    return builder.as_markup()
