from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schedule_bot.keyboards import groups_keyboard, schedule_keyboard
from schedule_bot.repositories import GroupRepository, UserRepository

router = Router(name="common")


async def show_groups(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        groups = await GroupRepository(session).list()
    if not groups:
        await message.answer("Расписание пока не загружено. Попробуйте позже.")
        return
    await message.answer("Выберите свою группу:", reply_markup=groups_keyboard(groups))


@router.message(CommandStart())
async def start(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        user = await UserRepository(session).get_with_group(message.from_user.id)
    if user and user.group:
        await message.answer(
            f"С возвращением! Ваша группа: <b>{escape(user.group.name)}</b>",
            reply_markup=schedule_keyboard,
        )
    else:
        await show_groups(message, session_factory)


@router.message(Command("group"))
@router.message(F.text == "🔄 Сменить группу")
async def change_group(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await show_groups(message, session_factory)


@router.callback_query(F.data.startswith("groups:"))
async def paginate_groups(
    callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    page = int(callback.data.split(":")[1])
    async with session_factory() as session:
        groups = await GroupRepository(session).list()
    await callback.message.edit_reply_markup(reply_markup=groups_keyboard(groups, page))
    await callback.answer()


@router.callback_query(F.data.startswith("group:"))
async def select_group(
    callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    group_id = int(callback.data.split(":")[1])
    async with session_factory() as session:
        group = await GroupRepository(session).get(group_id)
        if group is None:
            await callback.answer("Группа не найдена", show_alert=True)
            return
        await UserRepository(session).set_group(callback.from_user.id, group_id)
        await session.commit()
    await callback.message.edit_text(f"Вы выбрали группу <b>{escape(group.name)}</b>.")
    await callback.message.answer("Что показать?", reply_markup=schedule_keyboard)
    await callback.answer()


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Помощь")
async def help_message(message: Message) -> None:
    await message.answer(
        "Выберите период кнопкой внизу. Команда /group меняет группу. "
        "Если расписание выглядит неверно, сообщите администратору."
    )
