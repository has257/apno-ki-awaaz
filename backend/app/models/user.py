from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Enum, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import UserRole


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("length(trim(full_name)) > 0", name="ck_users_full_name"),
        Index("ix_users_role_created_at", "role", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone_number: Mapped[str] = mapped_column(
        String(16), nullable=False, unique=True, index=True
    )
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=False, create_constraint=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )

    reminders_received: Mapped[list["Reminder"]] = relationship(
        "Reminder",
        back_populates="elderly_user",
        foreign_keys="Reminder.elderly_user_id",
    )
    reminders_created: Mapped[list["Reminder"]] = relationship(
        "Reminder",
        back_populates="creator",
        foreign_keys="Reminder.created_by",
    )
    family_links: Mapped[list["FamilyElderlyLink"]] = relationship(
        "FamilyElderlyLink",
        back_populates="family_user",
        foreign_keys="FamilyElderlyLink.family_user_id",
    )
    elderly_links: Mapped[list["FamilyElderlyLink"]] = relationship(
        "FamilyElderlyLink",
        back_populates="elderly_user",
        foreign_keys="FamilyElderlyLink.elderly_user_id",
    )