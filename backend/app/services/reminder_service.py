from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from fastapi import HTTPException

from app.enums import ReminderEventType, ReminderStatus, UserRole
from app.models.family_elderly_link import FamilyElderlyLink
from app.models.reminder import Reminder
from app.models.reminder_log import ReminderLog
from app.models.reminder_occurrence import ReminderOccurrence
from app.models.user import User
from app.schemas.reminder import ReminderCreate, ReminderUpdate
from app.schemas.reminder_log import ReminderLogCreate
from app.services.family_link_service import has_approved_link


GENERATED_AUDIO_DIR = Path(__file__).resolve().parents[2] / "generated_audio"


def _validate_users(db: Session, elderly_user_id: int, created_by: int) -> None:
    elderly_user = db.get(User, elderly_user_id)
    if elderly_user is None:
        raise HTTPException(status_code=404, detail="Elderly user not found")
    if elderly_user.role != UserRole.ELDERLY:
        raise HTTPException(
            status_code=422,
            detail="elderly_user_id must belong to an ELDERLY user",
        )

    creator = db.get(User, created_by)
    if creator is None:
        raise HTTPException(status_code=404, detail="Creator user not found")
    if creator.role != UserRole.FAMILY:
        raise HTTPException(
            status_code=422,
            detail="created_by must belong to a FAMILY user",
        )


def _require_family_link(db: Session, family_user_id: int, elderly_user_id: int) -> None:
    if not has_approved_link(db, family_user_id, elderly_user_id):
        raise HTTPException(status_code=403, detail="Approved family access is required")


def _require_view_access(db: Session, reminder: Reminder, current_user: User) -> None:
    if current_user.role == UserRole.ELDERLY:
        if reminder.elderly_user_id == current_user.id:
            return
    elif current_user.role == UserRole.FAMILY:
        if has_approved_link(db, current_user.id, reminder.elderly_user_id):
            return
    raise HTTPException(status_code=404, detail="Reminder not found")


def _require_family_management(db: Session, reminder: Reminder, current_user: User) -> None:
    if current_user.role != UserRole.FAMILY:
        raise HTTPException(status_code=403, detail="Only FAMILY users can manage reminders")
    _require_family_link(db, current_user.id, reminder.elderly_user_id)


def create_reminder(db: Session, payload: ReminderCreate, current_user: User) -> Reminder:
    if current_user.role != UserRole.FAMILY:
        raise HTTPException(status_code=403, detail="Only FAMILY users can create reminders")
    _validate_users(db, payload.elderly_user_id, current_user.id)
    _require_family_link(db, current_user.id, payload.elderly_user_id)

    reminder = Reminder(**payload.model_dump(), created_by=current_user.id)
    db.add(reminder)
    try:
        db.flush()
        created_log = ReminderLogCreate(
            event_type=ReminderEventType.CREATED,
            event_message="Reminder created",
        )
        db.add(
            ReminderLog(
                reminder_id=reminder.id,
                **created_log.model_dump(),
            )
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Reminder could not be saved; verify both user records",
        ) from None

    return get_reminder(db, reminder.id, current_user)


def list_reminders(
    db: Session,
    current_user: User,
    *,
    elderly_user_id: int | None = None,
    status: ReminderStatus | None = None,
    offset: int = 0,
    limit: int = 100,
) -> list[Reminder]:
    statement = select(Reminder).options(selectinload(Reminder.logs))
    if current_user.role == UserRole.ELDERLY:
        if elderly_user_id is not None and elderly_user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Reminders not found")
        statement = statement.where(Reminder.elderly_user_id == current_user.id)
    elif current_user.role == UserRole.FAMILY:
        statement = statement.join(
            FamilyElderlyLink,
            FamilyElderlyLink.elderly_user_id == Reminder.elderly_user_id,
        ).where(
            FamilyElderlyLink.family_user_id == current_user.id,
            FamilyElderlyLink.status == "APPROVED",
        )
        if elderly_user_id is not None:
            statement = statement.where(Reminder.elderly_user_id == elderly_user_id)
    else:
        raise HTTPException(status_code=403, detail="Not authorized")
    if status is not None:
        statement = statement.where(Reminder.status == status)

    results = db.scalars(
        statement.order_by(Reminder.scheduled_at, Reminder.id)
        .offset(offset)
        .limit(limit)
    )
    return list(results.all())


def get_reminder(db: Session, reminder_id: int, current_user: User) -> Reminder:
    reminder = db.scalar(
        select(Reminder)
        .options(selectinload(Reminder.logs))
        .where(Reminder.id == reminder_id)
    )
    if reminder is None:
        raise HTTPException(status_code=404, detail="Reminder not found")
    _require_view_access(db, reminder, current_user)
    return reminder


def update_reminder(
    db: Session,
    reminder_id: int,
    payload: ReminderUpdate,
    current_user: User,
) -> Reminder:
    reminder = get_reminder(db, reminder_id, current_user)
    _require_family_management(db, reminder, current_user)
    if reminder.status != ReminderStatus.PENDING:
        raise HTTPException(
            status_code=409,
            detail="Only pending reminders can be updated",
        )

    elderly_user = db.get(User, payload.elderly_user_id)
    if elderly_user is None:
        raise HTTPException(status_code=404, detail="Elderly user not found")
    if elderly_user.role != UserRole.ELDERLY:
        raise HTTPException(
            status_code=422,
            detail="elderly_user_id must belong to an ELDERLY user",
        )
    _require_family_link(db, current_user.id, payload.elderly_user_id)

    for field, value in payload.model_dump().items():
        setattr(reminder, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Reminder could not be updated") from None

    return get_reminder(db, reminder.id, current_user)


def complete_reminder(db: Session, reminder_id: int, current_user: User) -> Reminder:
    reminder = get_reminder(db, reminder_id, current_user)
    if reminder.status == ReminderStatus.CANCELLED:
        raise HTTPException(
            status_code=409,
            detail="Cancelled reminders cannot be completed",
        )
    if reminder.status == ReminderStatus.PROCESSING:
        raise HTTPException(
            status_code=409,
            detail="Reminder audio is currently being generated",
        )
    if reminder.status == ReminderStatus.COMPLETED:
        return reminder

    reminder.status = ReminderStatus.COMPLETED
    latest_ready_occurrence = db.scalar(
        select(ReminderOccurrence)
        .where(
            ReminderOccurrence.reminder_id == reminder.id,
            ReminderOccurrence.status == ReminderStatus.AUDIO_READY,
        )
        .order_by(ReminderOccurrence.occurrence_at.desc())
        .limit(1)
        .with_for_update()
    )
    if latest_ready_occurrence is not None:
        latest_ready_occurrence.status = ReminderStatus.COMPLETED

    completed_log = ReminderLogCreate(
        event_type=ReminderEventType.COMPLETED,
        event_message="Reminder completed",
    )
    reminder.logs.append(ReminderLog(**completed_log.model_dump()))
    db.commit()
    return get_reminder(db, reminder.id, current_user)


def get_audio_metadata(db: Session, reminder_id: int, current_user: User) -> dict:
    reminder = get_reminder(db, reminder_id, current_user)

    occurrences = db.scalars(
        select(ReminderOccurrence)
        .where(ReminderOccurrence.reminder_id == reminder_id)
        .order_by(ReminderOccurrence.occurrence_at.desc())
    ).all()
    return {
        "reminder_id": reminder_id,
        "occurrences": [
            {
                "occurrence_at": occurrence.occurrence_at,
                "status": occurrence.status,
                "audio_available": (
                    occurrence.status
                    in [ReminderStatus.AUDIO_READY, ReminderStatus.COMPLETED]
                    and bool(occurrence.audio_file_path)
                ),
                "generated_at": occurrence.generated_at,
                "attempt_count": occurrence.attempt_count,
            }
            for occurrence in occurrences
        ],
    }


def get_audio_file(db: Session, reminder_id: int, current_user: User) -> Path:
    reminder = get_reminder(db, reminder_id, current_user)
    if current_user.role == UserRole.FAMILY:
        if reminder.created_by != current_user.id:
            raise HTTPException(status_code=404, detail="Audio not found")
        _require_family_link(db, current_user.id, reminder.elderly_user_id)

    occurrence = db.scalar(
        select(ReminderOccurrence)
        .where(
            ReminderOccurrence.reminder_id == reminder.id,
            ReminderOccurrence.status == ReminderStatus.AUDIO_READY,
            ReminderOccurrence.audio_file_path.is_not(None),
        )
        .order_by(ReminderOccurrence.generated_at.desc())
        .limit(1)
    )
    if occurrence is None or occurrence.audio_file_path is None:
        raise HTTPException(status_code=404, detail="Audio is not available")

    root = GENERATED_AUDIO_DIR.resolve()
    resolved_path = (root.parent / occurrence.audio_file_path).resolve()
    if not resolved_path.is_relative_to(root) or not resolved_path.is_file():
        raise HTTPException(status_code=404, detail="Audio is not available")
    return resolved_path


def delete_reminder(db: Session, reminder_id: int, current_user: User) -> None:
    reminder = get_reminder(db, reminder_id, current_user)
    _require_family_management(db, reminder, current_user)
    if reminder.status == ReminderStatus.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail="Completed reminders cannot be cancelled",
        )
    if reminder.status == ReminderStatus.CANCELLED:
        return

    active_occurrence = db.scalar(
        select(ReminderOccurrence)
        .where(
            ReminderOccurrence.reminder_id == reminder.id,
            ReminderOccurrence.occurrence_at == reminder.scheduled_at,
            ReminderOccurrence.status.in_(
                [ReminderStatus.PROCESSING, ReminderStatus.FAILED]
            ),
        )
        .with_for_update()
    )
    if active_occurrence is not None:
        active_occurrence.status = ReminderStatus.CANCELLED
        active_occurrence.next_retry_at = None
        active_occurrence.audio_file_path = None

    reminder.status = ReminderStatus.CANCELLED
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Reminder could not be cancelled") from None