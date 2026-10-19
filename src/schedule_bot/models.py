from datetime import date, datetime, time

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, LargeBinary, String, Time, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from schedule_bot.db import Base

UNSPECIFIED_FACULTY = "Факультет не указан"


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    faculty: Mapped[str] = mapped_column(
        String(150), default=UNSPECIFIED_FACULTY, server_default=UNSPECIFIED_FACULTY, index=True
    )
    specialty: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    course: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    lessons: Mapped[list["Lesson"]] = relationship(back_populates="group", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id", ondelete="SET NULL"))
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    interactions: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    group: Mapped[Group | None] = relationship()


class Lesson(Base):
    __tablename__ = "lessons"
    __table_args__ = (
        UniqueConstraint("group_id", "lesson_date", "start_time", name="uq_lesson_slot"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    lesson_date: Mapped[date] = mapped_column(Date, index=True)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    subject: Mapped[str] = mapped_column(String(255))
    teacher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    room: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lesson_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    group: Mapped[Group] = relationship(back_populates="lessons")


class ImportLog(Base):
    __tablename__ = "import_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_telegram_id: Mapped[int] = mapped_column(BigInteger)
    filename: Mapped[str] = mapped_column(String(255))
    total_rows: Mapped[int] = mapped_column(Integer)
    created_rows: Mapped[int] = mapped_column(Integer)
    updated_rows: Mapped[int] = mapped_column(Integer)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class ScheduleSubmission(Base):
    __tablename__ = "schedule_submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_content: Mapped[bytes] = mapped_column(LargeBinary)
    faculty: Mapped[str] = mapped_column(String(150), index=True)
    specialty: Mapped[str | None] = mapped_column(String(100), nullable=True)
    course: Mapped[int] = mapped_column(Integer)
    group_name: Mapped[str] = mapped_column(String(100), index=True)
    total_rows: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
