from datetime import date, datetime, time

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, String, Time, UniqueConstraint, func
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
