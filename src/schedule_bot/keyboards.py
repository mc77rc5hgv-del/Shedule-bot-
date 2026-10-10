from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

PAGE_SIZE = 12
FACULTIES = {
    "medical": "Лечебное дело",
    "dentistry": "Стоматология",
    "mpd": "МПД",
}

schedule_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Сегодня"), KeyboardButton(text="➡️ Завтра")],
        [KeyboardButton(text="🗓 Ближайшие 3 дня"), KeyboardButton(text="📆 Неделя")],
        [KeyboardButton(text="🔄 Сменить группу"), KeyboardButton(text="ℹ️ Помощь")],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите период",
)


def faculty_root_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏛 Все факультеты", callback_data="faculty_catalog")]
        ]
    )


def faculties_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code, name in FACULTIES.items():
        builder.button(text=name, callback_data=f"faculty_name:{code}")
    builder.adjust(1)
    return builder.as_markup()


def courses_keyboard(choices: list[tuple[int | None, int]]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for course, representative_id in choices:
        label = f"{course} курс" if course is not None else "Курс не указан"
        builder.button(text=f"🎓 {label}", callback_data=f"course:{representative_id}")
    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(text="⬅️ К факультетам", callback_data="faculty_catalog")
    )
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
    builder.row(InlineKeyboardButton(text="⬅️ К курсам", callback_data=f"faculty:{anchor_id}"))
    return builder.as_markup()
