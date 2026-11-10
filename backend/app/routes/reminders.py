from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.enums import ReminderStatus
from app.models.user import User
from app.schemas.reminder import (
    ReminderAudioMetadataRead,
    ReminderCreate,
    ReminderRead,
    ReminderUpdate,
)
from app.services import reminder_service


router = APIRouter(prefix="/reminders", tags=["Reminders"])


@router.post("", response_model=ReminderRead, status_code=status.HTTP_201_CREATED)
def create_reminder(
    payload: ReminderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return reminder_service.create_reminder(db, payload, current_user)


@router.get("", response_model=list[ReminderRead])
def list_reminders(
    elderly_user_id: int | None = Query(default=None, gt=0),
    reminder_status: ReminderStatus | None = Query(default=None, alias="status"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return reminder_service.list_reminders(
        db,
        current_user,
        elderly_user_id=elderly_user_id,
        status=reminder_status,
        offset=offset,
        limit=limit,
    )


@router.get("/{reminder_id}", response_model=ReminderRead)
def get_reminder(
    reminder_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return reminder_service.get_reminder(db, reminder_id, current_user)


@router.put("/{reminder_id}", response_model=ReminderRead)
def update_reminder(
    reminder_id: int,
    payload: ReminderUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return reminder_service.update_reminder(db, reminder_id, payload, current_user)


@router.delete("/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reminder(
    reminder_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    reminder_service.delete_reminder(db, reminder_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{reminder_id}/complete", response_model=ReminderRead)
def complete_reminder(
    reminder_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return reminder_service.complete_reminder(db, reminder_id, current_user)


@router.get("/{reminder_id}/audio", response_model=ReminderAudioMetadataRead)
def get_audio_metadata(
    reminder_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return reminder_service.get_audio_metadata(db, reminder_id, current_user)


@router.get("/{reminder_id}/audio/content", response_class=FileResponse)
def get_audio_content(
    reminder_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    audio_path = reminder_service.get_audio_file(db, reminder_id, current_user)
    return FileResponse(
        path=audio_path,
        media_type="audio/wav",
        filename="reminder.wav",
    )