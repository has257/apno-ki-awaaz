from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import FamilyElderlyLinkStatus
from app.models.user import utc_now


class FamilyElderlyLink(Base):
    __tablename__ = "family_elderly_links"
    __table_args__ = (
        UniqueConstraint(
            "family_user_id",
            "elderly_user_id",
            name="uq_family_elderly_link_pair",
        ),
        Index("ix_family_elderly_links_family_status", "family_user_id", "status"),
        Index("ix_family_elderly_links_elderly_status", "elderly_user_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    family_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    elderly_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[FamilyElderlyLinkStatus] = mapped_column(
        Enum(
            FamilyElderlyLinkStatus,
            name="family_elderly_link_status",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
        default=FamilyElderlyLinkStatus.PENDING,
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )

    family_user: Mapped["User"] = relationship(
        "User", back_populates="family_links", foreign_keys=[family_user_id]
    )
    elderly_user: Mapped["User"] = relationship(
        "User", back_populates="elderly_links", foreign_keys=[elderly_user_id]
    )