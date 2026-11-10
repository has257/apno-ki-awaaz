from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import ReminderEventType
from app.models.user import utc_now


class ReminderLog(Base):
    __tablename__ = "reminder_logs"
    __table_args__ = (
        Index("ix_reminder_logs_reminder_created", "reminder_id", "created_at"),
        Index("ix_reminder_logs_event_type", "event_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reminder_id: Mapped[int] = mapped_column(
        ForeignKey("reminders.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[ReminderEventType] = mapped_column(
        Enum(
            ReminderEventType,
            name="reminder_event_type",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
    )
    event_message: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )

    reminder: Mapped["Reminder"] = relationship(
        "Reminder", back_populates="logs"
    )