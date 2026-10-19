from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from schedule_bot.models import (
    Group,
    ImportLog,
    Lesson,
    ScheduleSubmission,
    UNSPECIFIED_FACULTY,
    User,
)


class GroupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self) -> list[Group]:
        result = await self.session.scalars(
            select(Group).order_by(Group.faculty, Group.specialty, Group.course, Group.name)
        )
        return list(result)

    async def list_courses(
        self, faculty: str, specialty: str | None
    ) -> list[tuple[int | None, int]]:
        statement = select(Group.course, func.min(Group.id)).where(Group.faculty == faculty)
        if specialty is None:
            statement = statement.where(Group.specialty.is_(None))
        else:
            statement = statement.where(Group.specialty == specialty)
        rows = await self.session.execute(statement.group_by(Group.course).order_by(Group.course))
        return list(rows)

    async def list_by_structure(
        self, faculty: str, specialty: str | None, course: int | None
    ) -> list[Group]:
        statement = select(Group).where(Group.faculty == faculty)
        statement = (
            statement.where(Group.specialty.is_(None))
            if specialty is None
            else statement.where(Group.specialty == specialty)
        )
        statement = (
            statement.where(Group.course.is_(None))
            if course is None
            else statement.where(Group.course == course)
        )
        result = await self.session.scalars(statement.order_by(Group.name))
        return list(result)

    async def get(self, group_id: int) -> Group | None:
        return await self.session.get(Group, group_id)

    async def get_by_name(self, name: str) -> Group | None:
        return await self.session.scalar(select(Group).where(Group.name == name))

    async def get_or_create(
        self,
        name: str,
        faculty: str | None = None,
        specialty: str | None = None,
        course: int | None = None,
    ) -> Group:
        group = await self.get_by_name(name)
        if group is None:
            group = Group(
                name=name,
                faculty=faculty or UNSPECIFIED_FACULTY,
                specialty=specialty,
                course=course,
            )
            self.session.add(group)
            await self.session.flush()
        else:
            if faculty:
                group.faculty = faculty
            group.specialty = specialty
            if course is not None:
                group.course = course
        return group

    async def set_structure(
        self, group: Group, faculty: str, specialty: str | None, course: int
    ) -> None:
        group.faculty = faculty
        group.specialty = specialty
        group.course = course


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def touch(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> None:
        now = datetime.now(UTC)
        user = await self.session.get(User, telegram_id)
        if user is None:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                created_at=now,
                last_seen_at=now,
                interactions=1,
            )
            self.session.add(user)
        else:
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
            user.last_seen_at = now
            user.interactions = (user.interactions or 0) + 1

    async def set_group(self, telegram_id: int, group_id: int) -> None:
        user = await self.session.get(User, telegram_id)
        if user is None:
            now = datetime.now(UTC)
            self.session.add(
                User(
                    telegram_id=telegram_id,
                    group_id=group_id,
                    created_at=now,
                    last_seen_at=now,
                    interactions=1,
                )
            )
        else:
            user.group_id = group_id

    async def get_with_group(self, telegram_id: int) -> User | None:
        return await self.session.scalar(
            select(User)
            .options(selectinload(User.group))
            .where(User.telegram_id == telegram_id)
        )

    async def page(self, page: int, page_size: int = 10) -> tuple[list[User], int]:
        total = await self.session.scalar(select(func.count()).select_from(User)) or 0
        users = await self.session.scalars(
            select(User)
            .options(selectinload(User.group))
            .order_by(User.last_seen_at.desc(), User.telegram_id)
            .offset(page * page_size)
            .limit(page_size)
        )
        return list(users), total


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

    async def next_lesson(
        self, group_id: int, current_date: date, current_time: time
    ) -> Lesson | None:
        return await self.session.scalar(
            select(Lesson)
            .where(
                Lesson.group_id == group_id,
                Lesson.lesson_date <= current_date + timedelta(days=30),
                (
                    (Lesson.lesson_date > current_date)
                    | (
                        (Lesson.lesson_date == current_date)
                        & (Lesson.start_time >= current_time)
                    )
                ),
            )
            .order_by(Lesson.lesson_date, Lesson.start_time)
            .limit(1)
        )

    async def future_subjects(
        self, group_id: int, current_date: date, current_time: time
    ) -> list[tuple[str, int]]:
        future = (
            (Lesson.lesson_date > current_date)
            | (
                (Lesson.lesson_date == current_date)
                & (Lesson.start_time >= current_time)
            )
        )
        rows = await self.session.execute(
            select(Lesson.subject, func.min(Lesson.id))
            .where(Lesson.group_id == group_id, future)
            .group_by(Lesson.subject)
            .order_by(func.lower(Lesson.subject))
        )
        return list(rows)

    async def get(self, lesson_id: int) -> Lesson | None:
        return await self.session.get(Lesson, lesson_id)

    async def next_subject(
        self,
        group_id: int,
        subject: str,
        current_date: date,
        current_time: time,
    ) -> Lesson | None:
        return await self.session.scalar(
            select(Lesson)
            .where(
                Lesson.group_id == group_id,
                Lesson.subject == subject,
                (
                    (Lesson.lesson_date > current_date)
                    | (
                        (Lesson.lesson_date == current_date)
                        & (Lesson.start_time >= current_time)
                    )
                ),
            )
            .order_by(Lesson.lesson_date, Lesson.start_time)
            .limit(1)
        )

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


class SubmissionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        *,
        user_telegram_id: int,
        username: str | None,
        filename: str,
        file_content: bytes,
        source_filename: str | None = None,
        source_file_content: bytes | None = None,
        source_media_type: str | None = None,
        faculty: str,
        specialty: str | None,
        course: int,
        group_name: str,
        total_rows: int,
    ) -> ScheduleSubmission:
        item = ScheduleSubmission(
            user_telegram_id=user_telegram_id,
            username=username,
            filename=filename[:255],
            file_content=file_content,
            source_filename=source_filename[:255] if source_filename else None,
            source_file_content=source_file_content,
            source_media_type=source_media_type,
            faculty=faculty,
            specialty=specialty,
            course=course,
            group_name=group_name,
            total_rows=total_rows,
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def get(self, submission_id: int) -> ScheduleSubmission | None:
        return await self.session.get(ScheduleSubmission, submission_id)

    async def pending(self, limit: int = 20) -> list[ScheduleSubmission]:
        result = await self.session.scalars(
            select(ScheduleSubmission)
            .where(ScheduleSubmission.status == "pending")
            .order_by(ScheduleSubmission.created_at, ScheduleSubmission.id)
            .limit(limit)
        )
        return list(result)

    async def pending_count(self) -> int:
        return (
            await self.session.scalar(
                select(func.count())
                .select_from(ScheduleSubmission)
                .where(ScheduleSubmission.status == "pending")
            )
            or 0
        )

    async def review(
        self, item: ScheduleSubmission, status: str, admin_telegram_id: int
    ) -> None:
        item.status = status
        item.reviewed_by = admin_telegram_id
        item.reviewed_at = datetime.now(UTC)


class StatisticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def dashboard(self) -> dict[str, int]:
        now = datetime.now(UTC)
        today = now.date()
        result = {}
        result["users"] = await self.session.scalar(select(func.count()).select_from(User)) or 0
        for key, delta in (("active_day", 1), ("active_week", 7), ("active_month", 30)):
            result[key] = (
                await self.session.scalar(
                    select(func.count())
                    .select_from(User)
                    .where(User.last_seen_at >= now - timedelta(days=delta))
                )
                or 0
            )
        result["groups"] = await self.session.scalar(select(func.count()).select_from(Group)) or 0
        result["lessons"] = await self.session.scalar(select(func.count()).select_from(Lesson)) or 0
        result["pending_submissions"] = await SubmissionRepository(self.session).pending_count()
        result["upcoming"] = (
            await self.session.scalar(
                select(func.count()).select_from(Lesson).where(Lesson.lesson_date >= today)
            )
            or 0
        )
        return result

    async def group_breakdown(self) -> list[tuple[str, str | None, int | None, int]]:
        rows = await self.session.execute(
            select(Group.faculty, Group.specialty, Group.course, func.count(Group.id))
            .group_by(Group.faculty, Group.specialty, Group.course)
            .order_by(Group.faculty, Group.specialty, Group.course)
        )
        return list(rows)


class ImportLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        admin_telegram_id: int,
        filename: str,
        total_rows: int,
        created_rows: int,
        updated_rows: int,
    ) -> None:
        self.session.add(
            ImportLog(
                admin_telegram_id=admin_telegram_id,
                filename=filename[:255],
                total_rows=total_rows,
                created_rows=created_rows,
                updated_rows=updated_rows,
            )
        )

    async def recent(self, limit: int = 10) -> list[ImportLog]:
        result = await self.session.scalars(
            select(ImportLog).order_by(ImportLog.imported_at.desc()).limit(limit)
        )
        return list(result)
