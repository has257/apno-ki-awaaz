import logging
import json
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.enums import (
    ReminderEventType,
    ReminderRecurrence,
    ReminderStatus,
)
from app.models.reminder import Reminder
from app.models.reminder_log import ReminderLog
from app.models.reminder_occurrence import ReminderOccurrence
from app.services.gnani_service import GnaniTTSRequestError


logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 15
MAX_ATTEMPTS = 3
RETRY_DELAYS_SECONDS = (30, 120)
PROCESSING_LEASE_SECONDS = 300
MAX_OCCURRENCES_PER_POLL = 25
GENERATED_AUDIO_DIR = Path(__file__).resolve().parents[2] / "generated_audio"

_scheduler: AsyncIOScheduler | None = None
_gnani_service = None


@dataclass(frozen=True)
class ClaimedOccurrence:
    reminder_id: int
    occurrence_id: int
    occurrence_at: datetime
    message: str
    recurrence: ReminderRecurrence
    audio_file_path: str


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _new_audio_relative_path() -> str:
    filename = f"{secrets.token_urlsafe(24)}.wav"
    return (Path("generated_audio") / filename).as_posix()


def _absolute_audio_path(relative_path: str) -> Path:
    root = GENERATED_AUDIO_DIR.resolve()
    path = (root.parent / relative_path).resolve()
    if path.parent != root or path.suffix != ".wav":
        raise ValueError("Invalid generated audio path")
    return path


def next_occurrence_time(
    occurrence_at: datetime,
    recurrence: ReminderRecurrence,
) -> datetime:
    occurrence_at = _utc_datetime(occurrence_at)
    if recurrence == ReminderRecurrence.DAILY:
        return occurrence_at + timedelta(days=1)
    if recurrence == ReminderRecurrence.WEEKLY:
        return occurrence_at + timedelta(weeks=1)
    raise ValueError("ONCE reminders do not have a next occurrence")


def _claim_next_occurrence(
    session_factory: Callable[[], Session],
    now: datetime,
) -> ClaimedOccurrence | None:
    retryable_occurrence = exists(
        select(ReminderOccurrence.id).where(
            ReminderOccurrence.reminder_id == Reminder.id,
            ReminderOccurrence.occurrence_at == Reminder.scheduled_at,
            ReminderOccurrence.status == ReminderStatus.FAILED,
            ReminderOccurrence.attempt_count < MAX_ATTEMPTS,
            ReminderOccurrence.next_retry_at <= now,
        )
    )
    stale_processing_occurrence = exists(
        select(ReminderOccurrence.id).where(
            ReminderOccurrence.reminder_id == Reminder.id,
            ReminderOccurrence.occurrence_at == Reminder.scheduled_at,
            ReminderOccurrence.status == ReminderStatus.PROCESSING,
            ReminderOccurrence.updated_at
            <= now - timedelta(seconds=PROCESSING_LEASE_SECONDS),
        )
    )
    due_statement = (
        select(Reminder)
        .where(
            Reminder.scheduled_at <= now,
            or_(
                Reminder.status == ReminderStatus.PENDING,
                and_(Reminder.status == ReminderStatus.FAILED, retryable_occurrence),
                and_(Reminder.status == ReminderStatus.PROCESSING, stale_processing_occurrence),
            ),
        )
        .order_by(Reminder.scheduled_at, Reminder.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )

    with session_factory() as session:
        reminder = session.scalar(due_statement)
        if reminder is None:
            return None

        occurrence_at = _utc_datetime(reminder.scheduled_at)
        occurrence = session.scalar(
            select(ReminderOccurrence)
            .where(
                ReminderOccurrence.reminder_id == reminder.id,
                ReminderOccurrence.occurrence_at == occurrence_at,
            )
            .with_for_update()
        )
        recover_existing_audio = False

        if occurrence is None:
            occurrence = ReminderOccurrence(
                reminder_id=reminder.id,
                occurrence_at=occurrence_at,
                status=ReminderStatus.PROCESSING,
                attempt_count=1,
                audio_file_path=_new_audio_relative_path(),
            )
            session.add(occurrence)
            session.flush()
            attempt_count = occurrence.attempt_count
        elif occurrence.status == ReminderStatus.PROCESSING:
            if occurrence.audio_file_path:
                existing_audio = _absolute_audio_path(occurrence.audio_file_path)
                recover_existing_audio = existing_audio.is_file() and existing_audio.stat().st_size > 0
            if occurrence.attempt_count >= MAX_ATTEMPTS:
                if recover_existing_audio:
                    attempt_count = occurrence.attempt_count
                else:
                    occurrence.status = ReminderStatus.FAILED
                    occurrence.next_retry_at = None
                    reminder.status = ReminderStatus.FAILED
                    occurrence.audio_file_path = None
                    session.add(
                        ReminderLog(
                            reminder_id=reminder.id,
                            event_type=ReminderEventType.FAILED,
                            event_message="Audio generation stopped after maximum attempts",
                        )
                    )
                    session.commit()
                    return None
            elif recover_existing_audio:
                attempt_count = occurrence.attempt_count
            else:
                occurrence.attempt_count += 1
                occurrence.status = ReminderStatus.PROCESSING
                occurrence.audio_file_path = _new_audio_relative_path()
                attempt_count = occurrence.attempt_count
        elif (
            occurrence.status != ReminderStatus.FAILED
            or occurrence.attempt_count >= MAX_ATTEMPTS
            or occurrence.next_retry_at is None
            or _utc_datetime(occurrence.next_retry_at) > now
        ):
            return None
        else:
            occurrence.status = ReminderStatus.PROCESSING
            occurrence.attempt_count += 1
            occurrence.next_retry_at = None
            occurrence.audio_file_path = _new_audio_relative_path()
            attempt_count = occurrence.attempt_count

        reminder.status = ReminderStatus.PROCESSING
        session.add(
            ReminderLog(
                reminder_id=reminder.id,
                event_type=ReminderEventType.TRIGGERED,
                event_message="Reminder occurrence processing started",
            )
        )
        claimed = ClaimedOccurrence(
            reminder_id=reminder.id,
            occurrence_id=occurrence.id,
            occurrence_at=occurrence_at,
            message=reminder.message,
            recurrence=reminder.recurrence,
            audio_file_path=occurrence.audio_file_path or _new_audio_relative_path(),
        )
        session.commit()

    logger.info(
        "Reminder occurrence claimed",
        extra={
            "reminder_id": claimed.reminder_id,
            "occurrence_id": claimed.occurrence_id,
            "attempt": attempt_count,
        },
    )
    return claimed


def _save_audio(audio: bytes, relative_path: str) -> None:
    _validate_wav(audio)

    GENERATED_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    target_path = _absolute_audio_path(relative_path)
    temporary_path = target_path.with_name(f".{target_path.name}.tmp")
    try:
        with temporary_path.open("xb") as audio_file:
            audio_file.write(audio)
        temporary_path.replace(target_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _validate_wav(audio: bytes) -> None:
    if len(audio) < 12:
        raise ValueError("TTS response is too short to be a WAV file")
    if audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
        raise ValueError("TTS response does not have a WAV container signature")


def _safe_provider_message(exc: Exception, service) -> str | None:
    raw_message = getattr(exc, "provider_message", None)
    if not isinstance(raw_message, str) or not raw_message:
        return None

    message = raw_message
    try:
        payload = json.loads(raw_message)
    except (TypeError, ValueError):
        payload = None

    if isinstance(payload, dict):
        candidates = []
        for key in ("message", "detail", "error", "description"):
            value = payload.get(key)
            if isinstance(value, str):
                candidates.append(value)
            elif isinstance(value, dict):
                nested_message = value.get("message") or value.get("detail")
                if isinstance(nested_message, str):
                    candidates.append(nested_message)
        message = "; ".join(candidates) if candidates else "Provider returned an error response"

    if re.search(r"speaker[_ -]?embedding|voice[_ -]?embedding", message, re.IGNORECASE):
        return "Provider error omitted because it may contain voice embedding data"

    api_key = getattr(service, "api_key", None)
    if isinstance(api_key, str) and api_key:
        message = message.replace(api_key, "[REDACTED]")
    message = re.sub(r"(?i)Bearer\s+[^\s,;]+", "Bearer [REDACTED]", message)
    message = re.sub(
        r"(?i)(api[_ -]?key(?:[_ -]?id)?|authorization)\s*[\"']?\s*[:=]\s*[\"']?[^\s,;\"'}]+",
        r"\1=[REDACTED]",
        message,
    )
    message = re.sub(r"[\r\n\t]+", " ", message)
    message = re.sub(r"\s{2,}", " ", message).strip()
    return message[:300] or "Provider returned an error response"


def _log_occurrence_failure(
    claimed: ClaimedOccurrence,
    stage: str,
    exc: Exception,
    service,
) -> None:
    status_code = getattr(exc, "status_code", None)
    content_type = getattr(exc, "content_type", None)
    provider_message = _safe_provider_message(exc, service)
    logger.warning(
        "Reminder occurrence failed: stage=%s exception=%s http_status=%s content_type=%s provider_error=%s",
        stage,
        type(exc).__name__,
        status_code if isinstance(status_code, int) else "n/a",
        content_type or "n/a",
        provider_message or "n/a",
        extra={
            "reminder_id": claimed.reminder_id,
            "occurrence_id": claimed.occurrence_id,
            "failure_stage": stage,
            "exception_class": type(exc).__name__,
            "http_status": status_code if isinstance(status_code, int) else None,
            "content_type": content_type,
            "provider_error": provider_message,
        },
    )
def _remove_audio(relative_path: str | None) -> None:
    if relative_path is None:
        return
    try:
        _absolute_audio_path(relative_path).unlink(missing_ok=True)
    except ValueError:
        logger.warning("Refusing to remove an invalid generated audio path")


def _record_failure(
    session_factory: Callable[[], Session],
    claimed: ClaimedOccurrence,
    now: datetime,
) -> None:
    with session_factory() as session:
        occurrence = session.scalar(
            select(ReminderOccurrence)
            .where(ReminderOccurrence.id == claimed.occurrence_id)
            .with_for_update()
        )
        reminder = session.scalar(
            select(Reminder)
            .where(Reminder.id == claimed.reminder_id)
            .with_for_update()
        )
        if occurrence is None or reminder is None:
            return
        if (
            occurrence.status != ReminderStatus.PROCESSING
            or reminder.status != ReminderStatus.PROCESSING
        ):
            return

        occurrence.status = ReminderStatus.FAILED
        failed_audio_path = occurrence.audio_file_path
        occurrence.audio_file_path = None
        if occurrence.attempt_count < MAX_ATTEMPTS:
            delay_index = min(occurrence.attempt_count - 1, len(RETRY_DELAYS_SECONDS) - 1)
            occurrence.next_retry_at = now + timedelta(
                seconds=RETRY_DELAYS_SECONDS[delay_index]
            )
            event_message = "Audio generation failed; retry scheduled"
        else:
            occurrence.next_retry_at = None
            event_message = "Audio generation failed after maximum attempts"

        reminder.status = ReminderStatus.FAILED
        session.add(
            ReminderLog(
                reminder_id=reminder.id,
                event_type=ReminderEventType.FAILED,
                event_message=event_message,
            )
        )
        attempt_count = occurrence.attempt_count
        retry_at = occurrence.next_retry_at
        session.commit()

    _remove_audio(failed_audio_path)

    logger.warning(
        "Reminder audio generation failed",
        extra={
            "reminder_id": claimed.reminder_id,
            "occurrence_id": claimed.occurrence_id,
            "attempt": attempt_count,
            "retry_at": retry_at.isoformat() if retry_at else None,
        },
    )


def _record_success(
    session_factory: Callable[[], Session],
    claimed: ClaimedOccurrence,
    relative_audio_path: str,
    now: datetime,
) -> bool:
    with session_factory() as session:
        occurrence = session.scalar(
            select(ReminderOccurrence)
            .where(ReminderOccurrence.id == claimed.occurrence_id)
            .with_for_update()
        )
        reminder = session.scalar(
            select(Reminder)
            .where(Reminder.id == claimed.reminder_id)
            .with_for_update()
        )
        if occurrence is None or reminder is None:
            return False
        if (
            occurrence.status != ReminderStatus.PROCESSING
            or reminder.status != ReminderStatus.PROCESSING
        ):
            return False

        occurrence.status = ReminderStatus.AUDIO_READY
        occurrence.audio_file_path = relative_audio_path
        occurrence.generated_at = now
        occurrence.next_retry_at = None
        if reminder.recurrence == ReminderRecurrence.ONCE:
            reminder.status = ReminderStatus.AUDIO_READY
        else:
            reminder.scheduled_at = next_occurrence_time(
                claimed.occurrence_at,
                reminder.recurrence,
            )
            reminder.status = ReminderStatus.PENDING

        session.add(
            ReminderLog(
                reminder_id=reminder.id,
                event_type=ReminderEventType.AUDIO_GENERATED,
                event_message="Audio generated for reminder occurrence",
            )
        )
        session.commit()
    return True


def process_due_reminders(
    gnani_service=None,
    *,
    session_factory: Callable[[], Session] | None = None,
    now: datetime | None = None,
) -> int:
    service = gnani_service or _gnani_service
    if service is None:
        logger.warning("Reminder scheduler has no Gnani service")
        return 0

    if session_factory is None:
        if engine is None:
            return 0
        session_factory = SessionLocal

    now = _utc_datetime(now or datetime.now(timezone.utc))
    processed = 0
    while processed < MAX_OCCURRENCES_PER_POLL:
        claimed = _claim_next_occurrence(session_factory, now)
        if claimed is None:
            break

        try:
            stage = "audio_file_check"
            target_audio_path = _absolute_audio_path(claimed.audio_file_path)
            if not (target_audio_path.is_file() and target_audio_path.stat().st_size > 0):
                stage = "tts_request"
                audio = service.generate_speech(
                    text=claimed.message,
                    language="te-IN",
                )
                stage = "wav_validation_and_file_write"
                _save_audio(audio, claimed.audio_file_path)
            stage = "database_finalization"
            recorded = _record_success(
                session_factory,
                claimed,
                claimed.audio_file_path,
                datetime.now(timezone.utc),
            )
            if recorded:
                logger.info(
                    "Reminder audio generated",
                    extra={
                        "reminder_id": claimed.reminder_id,
                        "occurrence_id": claimed.occurrence_id,
                        "audio_available": True,
                    },
                )
            else:
                _remove_audio(claimed.audio_file_path)
        except Exception as exc:
            _log_occurrence_failure(claimed, stage, exc, service)
            _record_failure(session_factory, claimed, datetime.now(timezone.utc))
        processed += 1

    if processed:
        logger.info(
            "Due reminder polling completed",
            extra={"occurrences_claimed": processed},
        )
    return processed


def _scheduled_poll() -> None:
    try:
        process_due_reminders()
    except Exception as exc:
        logger.error(
            "Reminder polling failed (%s)",
            type(exc).__name__,
        )


def start_scheduler(gnani_service) -> AsyncIOScheduler:
    global _scheduler, _gnani_service

    _gnani_service = gnani_service
    if _scheduler is not None and _scheduler.running:
        return _scheduler
    if _scheduler is None or not _scheduler.running:
        _scheduler = AsyncIOScheduler(timezone=timezone.utc)

    _scheduler.add_job(
        _scheduled_poll,
        trigger="interval",
        seconds=POLL_INTERVAL_SECONDS,
        id="reminder-polling",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=POLL_INTERVAL_SECONDS,
    )
    _scheduler.start()
    logger.info(
        "Reminder scheduler started",
        extra={"poll_interval_seconds": POLL_INTERVAL_SECONDS},
    )
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler, _gnani_service
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=True)
        logger.info("Reminder scheduler stopped")
    _scheduler = None
    _gnani_service = None


def scheduler_status() -> dict[str, object]:
    running = _scheduler is not None and _scheduler.running
    job = _scheduler.get_job("reminder-polling") if running else None
    next_run_time = job.next_run_time.isoformat() if job and job.next_run_time else None
    return {
        "running": running,
        "poll_interval_seconds": POLL_INTERVAL_SECONDS,
        "next_run_time": next_run_time,
        "max_attempts": MAX_ATTEMPTS,
    }