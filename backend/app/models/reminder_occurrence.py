from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import ReminderStatus
from app.models.user import utc_now


class ReminderOccurrence(Base):
    __tablename__ = "reminder_occurrences"
    __table_args__ = (
        UniqueConstraint(
            "reminder_id",
            "occurrence_at",
            name="uq_reminder_occurrence_time",
        ),
        CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= 3",
            name="ck_reminder_occurrences_attempt_count",
        ),
        Index("ix_reminder_occurrences_status_retry", "status", "next_retry_at"),
        Index("ix_reminder_occurrences_reminder_status", "reminder_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reminder_id: Mapped[int] = mapped_column(
        ForeignKey("reminders.id", ondelete="CASCADE"), nullable=False
    )
    occurrence_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[ReminderStatus] = mapped_column(
        Enum(
            ReminderStatus,
            name="reminder_occurrence_status",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    audio_file_path: Mapped[str | None] = mapped_column(String(500))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )

    reminder: Mapped["Reminder"] = relationship("Reminder", back_populates="occurrences")