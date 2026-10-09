from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from schedule_bot.models import Group, Lesson, UNSPECIFIED_FACULTY, User


class GroupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self) -> list[Group]:
        result = await self.session.scalars(
            select(Group).order_by(Group.faculty, Group.course, Group.name)
        )
        return list(result)

    async def list_faculties(self) -> list[tuple[str, int]]:
        rows = await self.session.execute(
            select(Group.faculty, func.min(Group.id))
            .group_by(Group.faculty)
            .order_by(Group.faculty)
        )
        return [(faculty or UNSPECIFIED_FACULTY, group_id) for faculty, group_id in rows]

    async def list_courses(self, faculty: str) -> list[tuple[int | None, int]]:
        rows = await self.session.execute(
            select(Group.course, func.min(Group.id))
            .where(Group.faculty == faculty)
            .group_by(Group.course)
            .order_by(Group.course)
        )
        return list(rows)

    async def list_by_structure(self, faculty: str, course: int | None) -> list[Group]:
        statement = select(Group).where(Group.faculty == faculty)
        if course is None:
            statement = statement.where(Group.course.is_(None))
        else:
            statement = statement.where(Group.course == course)
        result = await self.session.scalars(statement.order_by(Group.name))
        return list(result)

    async def get(self, group_id: int) -> Group | None:
        return await self.session.get(Group, group_id)

    async def get_by_name(self, name: str) -> Group | None:
        return await self.session.scalar(select(Group).where(Group.name == name))

    async def get_or_create(
        self, name: str, faculty: str | None = None, course: int | None = None
    ) -> Group:
        group = await self.get_by_name(name)
        if group is None:
            group = Group(
                name=name,
                faculty=faculty or UNSPECIFIED_FACULTY,
                course=course,
            )
            self.session.add(group)
            await self.session.flush()
        else:
            if faculty:
                group.faculty = faculty
            if course is not None:
                group.course = course
        return group

    async def set_structure(self, group: Group, faculty: str, course: int) -> None:
        group.faculty = faculty
        group.course = course


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
        start_time: Any,
        end_time: Any,
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
