from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import ReminderRecurrence, ReminderStatus
from app.models.user import utc_now


class Reminder(Base):
    __tablename__ = "reminders"
    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="ck_reminders_title"),
        Index("ix_reminders_elderly_status", "elderly_user_id", "status"),
        Index("ix_reminders_status_scheduled", "status", "scheduled_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    message: Mapped[str] = mapped_column(String(2000), nullable=False)
    elderly_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    recurrence: Mapped[ReminderRecurrence] = mapped_column(
        Enum(
            ReminderRecurrence,
            name="reminder_recurrence",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
        default=ReminderRecurrence.ONCE,
    )
    status: Mapped[ReminderStatus] = mapped_column(
        Enum(
            ReminderStatus,
            name="reminder_status",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
        default=ReminderStatus.PENDING,
        server_default=ReminderStatus.PENDING.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )

    elderly_user: Mapped["User"] = relationship(
        "User",
        back_populates="reminders_received",
        foreign_keys=[elderly_user_id],
    )
    creator: Mapped["User"] = relationship(
        "User",
        back_populates="reminders_created",
        foreign_keys=[created_by],
    )
    logs: Mapped[list["ReminderLog"]] = relationship(
        "ReminderLog",
        back_populates="reminder",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ReminderLog.created_at",
    )
    occurrences: Mapped[list["ReminderOccurrence"]] = relationship(
        "ReminderOccurrence",
        back_populates="reminder",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ReminderOccurrence.occurrence_at",
    )