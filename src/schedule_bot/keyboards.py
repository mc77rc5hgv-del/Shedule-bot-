from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

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


def groups_keyboard(groups, page: int = 0) -> InlineKeyboardMarkup:
    page_count = max(1, (len(groups) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(max(0, page), page_count - 1)
    builder = InlineKeyboardBuilder()
    for group in groups[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]:
        builder.button(text=group.name, callback_data=f"group:{group.id}")
    builder.adjust(2)
    navigation = []
    if page > 0:
        navigation.append(InlineKeyboardButton(text="⬅️", callback_data=f"groups:{page - 1}"))
    if page + 1 < page_count:
        navigation.append(InlineKeyboardButton(text="➡️", callback_data=f"groups:{page + 1}"))
    if navigation:
        builder.row(*navigation)
    return builder.as_markup()
