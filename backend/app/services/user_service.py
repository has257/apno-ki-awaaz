from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.user import User
from app.enums import FamilyElderlyLinkStatus, UserRole
from app.models.family_elderly_link import FamilyElderlyLink

def list_users(
    db: Session,
    current_user: User,
    *,
    offset: int = 0,
    limit: int = 100,
) -> list[User]:
    if current_user.role != UserRole.FAMILY:
        return [current_user]
    linked_users = list(
        db.scalars(
            select(User)
            .join(FamilyElderlyLink, FamilyElderlyLink.elderly_user_id == User.id)
            .where(
                FamilyElderlyLink.family_user_id == current_user.id,
                FamilyElderlyLink.status == FamilyElderlyLinkStatus.APPROVED,
            )
            .order_by(User.created_at.desc(), User.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return [current_user, *linked_users][offset : offset + limit]


def get_user(db: Session, user_id: int, current_user: User) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id != current_user.id:
        approved = db.scalar(
            select(FamilyElderlyLink.id).where(
                FamilyElderlyLink.family_user_id == current_user.id,
                FamilyElderlyLink.elderly_user_id == user.id,
                FamilyElderlyLink.status == FamilyElderlyLinkStatus.APPROVED,
            )
        )
        if (
            current_user.role != UserRole.FAMILY
            or user.role != UserRole.ELDERLY
            or approved is None
        ):
            raise HTTPException(status_code=404, detail="User not found")
    return user