from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.family_link import FamilyElderlyLinkRead, LinkRequest
from app.services import family_link_service


router = APIRouter(prefix="/links", tags=["Family links"])


@router.post("/request", response_model=FamilyElderlyLinkRead, status_code=status.HTTP_201_CREATED)
def request_link(
    payload: LinkRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return family_link_service.request_link(db, current_user, payload.elderly_user_id)


@router.get("/received", response_model=list[FamilyElderlyLinkRead])
def received_links(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return family_link_service.list_received(db, current_user)


@router.get("/sent", response_model=list[FamilyElderlyLinkRead])
def sent_links(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return family_link_service.list_sent(db, current_user)


@router.patch("/{link_id}/approve", response_model=FamilyElderlyLinkRead)
def approve_link(
    link_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return family_link_service.approve_link(db, current_user, link_id)


@router.patch("/{link_id}/reject", response_model=FamilyElderlyLinkRead)
def reject_link(
    link_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return family_link_service.reject_link(db, current_user, link_id)


@router.patch("/{link_id}/revoke", response_model=FamilyElderlyLinkRead)
def revoke_link(
    link_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return family_link_service.revoke_link(db, current_user, link_id)