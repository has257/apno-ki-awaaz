from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.enums import FamilyElderlyLinkStatus, UserRole
from app.models.family_elderly_link import FamilyElderlyLink
from app.models.user import User


def has_approved_link(db: Session, family_user_id: int, elderly_user_id: int) -> bool:
    return (
        db.scalar(
            select(FamilyElderlyLink.id).where(
                FamilyElderlyLink.family_user_id == family_user_id,
                FamilyElderlyLink.elderly_user_id == elderly_user_id,
                FamilyElderlyLink.status == FamilyElderlyLinkStatus.APPROVED,
            )
        )
        is not None
    )


def request_link(db: Session, family_user: User, elderly_user_id: int) -> FamilyElderlyLink:
    if family_user.role != UserRole.FAMILY:
        raise HTTPException(status_code=403, detail="Only FAMILY users can request access")
    if family_user.id == elderly_user_id:
        raise HTTPException(status_code=422, detail="Users cannot link to themselves")

    elderly_user = db.get(User, elderly_user_id)
    if elderly_user is None:
        raise HTTPException(status_code=404, detail="ELDERLY user not found")
    if elderly_user.role != UserRole.ELDERLY:
        raise HTTPException(status_code=422, detail="Target user must have the ELDERLY role")

    link = db.scalar(
        select(FamilyElderlyLink)
        .where(
            FamilyElderlyLink.family_user_id == family_user.id,
            FamilyElderlyLink.elderly_user_id == elderly_user_id,
        )
        .with_for_update()
    )
    if link is not None:
        if link.status in (
            FamilyElderlyLinkStatus.PENDING,
            FamilyElderlyLinkStatus.APPROVED,
        ):
            raise HTTPException(status_code=409, detail="An active link already exists")
        link.status = FamilyElderlyLinkStatus.PENDING
        link.requested_at = datetime.now(timezone.utc)
        link.responded_at = None
    else:
        link = FamilyElderlyLink(
            family_user_id=family_user.id,
            elderly_user_id=elderly_user.id,
            status=FamilyElderlyLinkStatus.PENDING,
        )
        db.add(link)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An active link already exists") from None
    db.refresh(link)
    return link


def list_received(db: Session, elderly_user: User) -> list[FamilyElderlyLink]:
    if elderly_user.role != UserRole.ELDERLY:
        raise HTTPException(status_code=403, detail="Only ELDERLY users can view received requests")
    return list(
        db.scalars(
            select(FamilyElderlyLink)
                .options(
                    joinedload(FamilyElderlyLink.family_user),
                    joinedload(FamilyElderlyLink.elderly_user),
                )
            .where(FamilyElderlyLink.elderly_user_id == elderly_user.id)
            .order_by(FamilyElderlyLink.requested_at.desc(), FamilyElderlyLink.id.desc())
        ).all()
    )


def list_sent(db: Session, family_user: User) -> list[FamilyElderlyLink]:
    if family_user.role != UserRole.FAMILY:
        raise HTTPException(status_code=403, detail="Only FAMILY users can view sent requests")
    return list(
        db.scalars(
            select(FamilyElderlyLink)
            .options(
                joinedload(FamilyElderlyLink.family_user),
                joinedload(FamilyElderlyLink.elderly_user),
            )
            .where(FamilyElderlyLink.family_user_id == family_user.id)
            .order_by(FamilyElderlyLink.requested_at.desc(), FamilyElderlyLink.id.desc())
        ).all()
    )


def _decide(
    db: Session,
    elderly_user: User,
    link_id: int,
    *,
    expected: FamilyElderlyLinkStatus,
    target: FamilyElderlyLinkStatus,
) -> FamilyElderlyLink:
    if elderly_user.role != UserRole.ELDERLY:
        raise HTTPException(status_code=403, detail="Only ELDERLY users can decide link requests")
    link = db.scalar(
        select(FamilyElderlyLink)
        .where(
            FamilyElderlyLink.id == link_id,
            FamilyElderlyLink.elderly_user_id == elderly_user.id,
        )
        .with_for_update()
    )
    if link is None:
        raise HTTPException(status_code=404, detail="Link request not found")
    if link.status != expected:
        raise HTTPException(status_code=409, detail="Link request is not in the required state")

    link.status = target
    link.responded_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(link)
    return link


def approve_link(db: Session, elderly_user: User, link_id: int) -> FamilyElderlyLink:
    return _decide(
        db,
        elderly_user,
        link_id,
        expected=FamilyElderlyLinkStatus.PENDING,
        target=FamilyElderlyLinkStatus.APPROVED,
    )


def reject_link(db: Session, elderly_user: User, link_id: int) -> FamilyElderlyLink:
    return _decide(
        db,
        elderly_user,
        link_id,
        expected=FamilyElderlyLinkStatus.PENDING,
        target=FamilyElderlyLinkStatus.REJECTED,
    )


def revoke_link(db: Session, elderly_user: User, link_id: int) -> FamilyElderlyLink:
    return _decide(
        db,
        elderly_user,
        link_id,
        expected=FamilyElderlyLinkStatus.APPROVED,
        target=FamilyElderlyLinkStatus.REVOKED,
    )