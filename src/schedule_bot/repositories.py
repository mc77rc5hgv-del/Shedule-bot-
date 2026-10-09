from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from schedule_bot.models import Group, Lesson, User


class GroupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self) -> list[Group]:
        result = await self.session.scalars(select(Group).order_by(Group.name))
        return list(result)

    async def get(self, group_id: int) -> Group | None:
        return await self.session.get(Group, group_id)

    async def get_or_create(self, name: str) -> Group:
        group = await self.session.scalar(select(Group).where(Group.name == name))
        if group is None:
            group = Group(name=name)
            self.session.add(group)
            await self.session.flush()
        return group


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def set_group(self, telegram_id: int, group_id: int) -> None:
        user = await self.session.get(User, telegram_id)
        if user is None:
            self.session.add(User(telegram_id=telegram_id, group_id=group_id))
        else:
            user.group_id = group_id

    async def get_with_group(self, telegram_id: int) -> User | None:
        return await self.session.scalar(
            select(User)
            .options(selectinload(User.group))
            .where(User.telegram_id == telegram_id)
        )


class LessonRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def between(self, group_id: int, start: date, end: date) -> list[Lesson]:
        result = await self.session.scalars(
            select(Lesson)
            .where(
                Lesson.group_id == group_id,
                Lesson.lesson_date >= start,
                Lesson.lesson_date <= end,
            )
            .order_by(Lesson.lesson_date, Lesson.start_time)
        )
        return list(result)

    async def upsert(
        self,
        *,
        group_id: int,
        lesson_date: date,
        start_time,
        end_time,
        subject: str,
        teacher: str | None,
        room: str | None,
        lesson_type: str | None,
    ) -> bool:
        lesson = await self.session.scalar(
            select(Lesson).where(
                Lesson.group_id == group_id,
                Lesson.lesson_date == lesson_date,
                Lesson.start_time == start_time,
            )
        )
        created = lesson is None
        if lesson is None:
            lesson = Lesson(group_id=group_id, lesson_date=lesson_date, start_time=start_time)
            self.session.add(lesson)
        lesson.end_time = end_time
        lesson.subject = subject
        lesson.teacher = teacher
        lesson.room = room
        lesson.lesson_type = lesson_type
        return created
