from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from schedule_bot.structure import FACULTIES, FACULTY_SPECIALTIES, SPECIALTY_LABELS

PAGE_SIZE = 12

home_reply_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🏠 Главное меню")]],
    resize_keyboard=True,
    input_field_placeholder="Откройте главное меню",
)


def home_keyboard(is_admin: bool = False, has_group: bool = True) -> InlineKeyboardMarkup:
    if has_group:
        rows = [
            [
                InlineKeyboardButton(text="📅 Расписание", callback_data="schedule:menu"),
                InlineKeyboardButton(text="⏭ Следующая пара", callback_data="schedule:next"),
            ],
            [
                InlineKeyboardButton(text="👤 Моя группа", callback_data="nav:my_group"),
                InlineKeyboardButton(text="🔄 Сменить группу", callback_data="nav:groups"),
            ],
            [InlineKeyboardButton(text="➕ Добавить расписание", callback_data="submission:help")],
            [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="nav:help")],
        ]
    else:
        rows = [
            [InlineKeyboardButton(text="🔎 Найти своё расписание", callback_data="nav:groups")],
            [InlineKeyboardButton(text="➕ Добавить своё расписание", callback_data="submission:help")],
            [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="nav:help")],
        ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="🛠 Админ-панель", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def schedule_periods_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Сегодня", callback_data="schedule:today"),
                InlineKeyboardButton(text="Завтра", callback_data="schedule:tomorrow"),
            ],
            [
                InlineKeyboardButton(text="Ближайшие 3 дня", callback_data="schedule:three"),
                InlineKeyboardButton(text="7 дней", callback_data="schedule:week"),
            ],
            [
                InlineKeyboardButton(
                    text="🗓 Месяц по неделям", callback_data="schedule:month"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔎 Когда будет предмет?", callback_data="schedule:subject"
                )
            ],
            [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="nav:home")],
        ]
    )

def schedule_result_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Другой период", callback_data="schedule:menu")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="nav:home")],
        ]
    )


def month_pages_keyboard(page: int, pages: int) -> InlineKeyboardMarkup:
    navigation = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(text="⬅️", callback_data=f"month:{page - 1}")
        )
    navigation.append(
        InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="month:noop")
    )
    if page + 1 < pages:
        navigation.append(
            InlineKeyboardButton(text="➡️", callback_data=f"month:{page + 1}")
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            navigation,
            [InlineKeyboardButton(text="⬅️ К расписанию", callback_data="schedule:menu")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="nav:home")],
        ]
    )


def subjects_keyboard(
    choices: list[tuple[str, int]], page: int = 0, page_size: int = 8
) -> InlineKeyboardMarkup:
    pages = max(1, (len(choices) + page_size - 1) // page_size)
    page = min(max(page, 0), pages - 1)
    builder = InlineKeyboardBuilder()
    for subject, lesson_id in choices[page * page_size : (page + 1) * page_size]:
        label = subject if len(subject) <= 45 else subject[:42] + "…"
        builder.button(text=label, callback_data=f"subject:{lesson_id}")
    builder.adjust(1)
    navigation = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(text="⬅️", callback_data=f"subjects:{page - 1}")
        )
    navigation.append(
        InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="subject:noop")
    )
    if page + 1 < pages:
        navigation.append(
            InlineKeyboardButton(text="➡️", callback_data=f"subjects:{page + 1}")
        )
    if len(choices) > page_size:
        builder.row(*navigation)
    builder.row(
        InlineKeyboardButton(text="⬅️ К расписанию", callback_data="schedule:menu")
    )
    return builder.as_markup()


def subject_result_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔎 Другой предмет", callback_data="schedule:subject"
                )
            ],
            [InlineKeyboardButton(text="⬅️ Расписание", callback_data="schedule:menu")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="nav:home")],
        ]
    )


def faculties_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for faculty in FACULTIES:
        builder.button(
            text=f"🏛 {faculty} факультет", callback_data=f"faculty_number:{faculty}"
        )
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="⬅️ Главное меню", callback_data="nav:home"))
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
    builder.row(
        InlineKeyboardButton(
            text="➕ Нет моего курса", callback_data="submission:help"
        )
    )
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
    builder.row(
        InlineKeyboardButton(
            text="➕ Нет моей группы", callback_data="submission:help"
        )
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ К курсам", callback_data=f"back_courses:{anchor_id}")
    )
    return builder.as_markup()


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats"),
                InlineKeyboardButton(text="👥 Пользователи", callback_data="admin:users:0"),
            ],
            [
                InlineKeyboardButton(text="🎓 Структура групп", callback_data="admin:groups"),
                InlineKeyboardButton(text="🕘 История загрузок", callback_data="admin:imports"),
            ],
            [InlineKeyboardButton(text="📨 Заявки на расписание", callback_data="admin:submissions")],
            [InlineKeyboardButton(text="📥 Как загрузить файл", callback_data="admin:help")],
            [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="nav:home")],
        ]
    )


def admin_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Админ-панель", callback_data="admin:home")]
        ]
    )


def admin_users_keyboard(page: int, pages: int) -> InlineKeyboardMarkup:
    navigation = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(text="⬅️", callback_data=f"admin:users:{page - 1}")
        )
    navigation.append(
        InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="admin:noop")
    )
    if page + 1 < pages:
        navigation.append(
            InlineKeyboardButton(text="➡️", callback_data=f"admin:users:{page + 1}")
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            navigation,
            [InlineKeyboardButton(text="⬅️ Админ-панель", callback_data="admin:home")],
        ]
    )


def submission_help_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📄 Скачать CSV-шаблон", callback_data="submission:template")],
            [InlineKeyboardButton(text="🤖 Промпт для нейросети", callback_data="submission:prompt")],
            [InlineKeyboardButton(text="🔎 Найти расписание", callback_data="nav:groups")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="nav:home")],
        ]
    )


def missing_schedule_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить расписание", callback_data="submission:help")],
            [InlineKeyboardButton(text="⬅️ К факультетам", callback_data="faculties")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="nav:home")],
        ]
    )


def submission_review_keyboard(submission_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Одобрить", callback_data=f"admin:submission:approve:{submission_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить", callback_data=f"admin:submission:reject:{submission_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📄 Получить файл",
                    callback_data=f"admin:submission:file:{submission_id}",
                )
            ],
        ]
    )


def admin_submissions_keyboard(items) -> InlineKeyboardMarkup:
    rows = []
    for item in items:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"📄 #{item.id}", callback_data=f"admin:submission:file:{item.id}"
                ),
                InlineKeyboardButton(
                    text="✅", callback_data=f"admin:submission:approve:{item.id}"
                ),
                InlineKeyboardButton(
                    text="❌", callback_data=f"admin:submission:reject:{item.id}"
                ),
            ]
        )
    rows.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:submissions")])
    rows.append([InlineKeyboardButton(text="⬅️ Админ-панель", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
