import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.enums import ReminderRecurrence, ReminderStatus, UserRole
from app.models.reminder import Reminder
from app.models.reminder_log import ReminderLog
from app.models.reminder_occurrence import ReminderOccurrence
from app.models.user import User
from app.services.gnani_service import GnaniTTSRequestError
from app.services import reminder_scheduler


class MockGnaniService:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.api_key = "mock-api-key-secret"
        self.messages: list[str] = []

    def generate_speech(self, *, text: str, language: str) -> bytes:
        assert language == "te-IN"
        self.messages.append(text)
        if self.fail:
            raise RuntimeError("mock provider failure with secret")
        return b"RIFF\x04\x00\x00\x00WAVE"


@pytest.fixture
def scheduler_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    monkeypatch.setattr(
        reminder_scheduler,
        "GENERATED_AUDIO_DIR",
        tmp_path / "generated_audio",
    )

    def session_factory() -> Session:
        return Session(engine)

    with session_factory() as session:
        family = User(
            full_name="Family",
            phone_number="+919876500001",
            role=UserRole.FAMILY,
        )
        elderly = User(
            full_name="Elderly",
            phone_number="+919876500002",
            role=UserRole.ELDERLY,
        )
        session.add_all([family, elderly])
        session.commit()
        ids = family.id, elderly.id

    yield engine, session_factory, ids
    engine.dispose()


def add_reminder(
    session_factory,
    family_id: int,
    elderly_id: int,
    scheduled_at: datetime,
    recurrence: ReminderRecurrence = ReminderRecurrence.ONCE,
    status: ReminderStatus = ReminderStatus.PENDING,
) -> int:
    with session_factory() as session:
        reminder = Reminder(
            title="Medicine",
            message="Take the evening medicine",
            elderly_user_id=elderly_id,
            created_by=family_id,
            scheduled_at=scheduled_at,
            recurrence=recurrence,
            status=status,
        )
        session.add(reminder)
        session.commit()
        return reminder.id


def test_future_due_and_once_per_occurrence(scheduler_db) -> None:
    _, session_factory, (family_id, elderly_id) = scheduler_db
    now = datetime.now(timezone.utc)
    future_id = add_reminder(
        session_factory, family_id, elderly_id, now + timedelta(hours=1)
    )
    due_id = add_reminder(
        session_factory, family_id, elderly_id, now - timedelta(seconds=1)
    )
    gnani = MockGnaniService()

    first_count = reminder_scheduler.process_due_reminders(
        gnani, session_factory=session_factory, now=now
    )
    second_count = reminder_scheduler.process_due_reminders(
        gnani, session_factory=session_factory, now=now
    )

    with session_factory() as session:
        due = session.get(Reminder, due_id)
        future = session.get(Reminder, future_id)
        occurrence = session.scalar(
            select(ReminderOccurrence).where(
                ReminderOccurrence.reminder_id == due_id
            )
        )
        event_types = list(
            session.scalars(
                select(ReminderLog.event_type)
                .where(ReminderLog.reminder_id == due_id)
                .order_by(ReminderLog.id)
            ).all()
        )

    assert first_count == 1
    assert second_count == 0
    assert gnani.messages == ["Take the evening medicine"]
    assert future.status == ReminderStatus.PENDING
    assert due.status == ReminderStatus.AUDIO_READY
    assert occurrence.status == ReminderStatus.AUDIO_READY
    assert occurrence.audio_file_path.startswith("generated_audio/")
    assert Path(reminder_scheduler.GENERATED_AUDIO_DIR.parent / occurrence.audio_file_path).is_file()
    assert event_types == [ReminderLog.event_type.type.enum_class.TRIGGERED,
                           ReminderLog.event_type.type.enum_class.AUDIO_GENERATED]


@pytest.mark.parametrize(
    ("recurrence", "delta"),
    [
        (ReminderRecurrence.DAILY, timedelta(days=1)),
        (ReminderRecurrence.WEEKLY, timedelta(weeks=1)),
    ],
)
def test_recurring_reminders_advance_from_occurrence_time(
    scheduler_db,
    recurrence: ReminderRecurrence,
    delta: timedelta,
) -> None:
    _, session_factory, (family_id, elderly_id) = scheduler_db
    now = datetime.now(timezone.utc)
    original_scheduled_at = now - timedelta(seconds=2)
    reminder_id = add_reminder(
        session_factory,
        family_id,
        elderly_id,
        original_scheduled_at,
        recurrence,
    )

    processed = reminder_scheduler.process_due_reminders(
        MockGnaniService(), session_factory=session_factory, now=now
    )

    with session_factory() as session:
        reminder = session.get(Reminder, reminder_id)
        occurrence = session.scalar(
            select(ReminderOccurrence).where(
                ReminderOccurrence.reminder_id == reminder_id
            )
        )
    assert processed == 1
    assert reminder.status == ReminderStatus.PENDING
    assert reminder.scheduled_at.replace(tzinfo=timezone.utc) == original_scheduled_at + delta
    assert occurrence.occurrence_at.replace(tzinfo=timezone.utc) == original_scheduled_at


def test_failed_generation_retries_at_most_three_times(scheduler_db) -> None:
    _, session_factory, (family_id, elderly_id) = scheduler_db
    now = datetime.now(timezone.utc)
    reminder_id = add_reminder(
        session_factory, family_id, elderly_id, now - timedelta(seconds=1)
    )
    gnani = MockGnaniService(fail=True)

    assert reminder_scheduler.process_due_reminders(
        gnani, session_factory=session_factory, now=now
    ) == 1
    with session_factory() as session:
        occurrence = session.scalar(
            select(ReminderOccurrence).where(
                ReminderOccurrence.reminder_id == reminder_id
            )
        )
        first_retry = occurrence.next_retry_at
    assert first_retry is not None

    assert reminder_scheduler.process_due_reminders(
        gnani,
        session_factory=session_factory,
        now=first_retry.replace(tzinfo=timezone.utc) + timedelta(seconds=1),
    ) == 1
    with session_factory() as session:
        occurrence = session.scalar(
            select(ReminderOccurrence).where(
                ReminderOccurrence.reminder_id == reminder_id
            )
        )
        second_retry = occurrence.next_retry_at
    assert second_retry is not None

    assert reminder_scheduler.process_due_reminders(
        gnani,
        session_factory=session_factory,
        now=second_retry.replace(tzinfo=timezone.utc) + timedelta(seconds=1),
    ) == 1
    assert reminder_scheduler.process_due_reminders(
        gnani,
        session_factory=session_factory,
        now=datetime.now(timezone.utc) + timedelta(days=1),
    ) == 0

    with session_factory() as session:
        occurrence = session.scalar(
            select(ReminderOccurrence).where(
                ReminderOccurrence.reminder_id == reminder_id
            )
        )
        reminder = session.get(Reminder, reminder_id)
        failed_logs = session.scalars(
            select(ReminderLog).where(
                ReminderLog.reminder_id == reminder_id,
                ReminderLog.event_type == "FAILED",
            )
        ).all()

    assert len(gnani.messages) == 3
    assert occurrence.attempt_count == 3
    assert occurrence.status == ReminderStatus.FAILED
    assert occurrence.next_retry_at is None
    assert reminder.status == ReminderStatus.FAILED
    assert len(failed_logs) == 3


def test_provider_diagnostic_is_redacted_and_includes_status(
    scheduler_db,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _, session_factory, (family_id, elderly_id) = scheduler_db
    now = datetime.now(timezone.utc)
    add_reminder(
        session_factory, family_id, elderly_id, now - timedelta(seconds=1)
    )
    gnani = MockGnaniService()

    def fail_with_provider_response(*, text: str, language: str) -> bytes:
        gnani.messages.append(text)
        raise GnaniTTSRequestError(
            status_code=401,
            provider_message='{"message":"Invalid api key: mock-api-key-secret"}',
            content_type="application/json",
        )

    gnani.generate_speech = fail_with_provider_response

    with caplog.at_level("WARNING", logger=reminder_scheduler.__name__):
        reminder_scheduler.process_due_reminders(
            gnani,
            session_factory=session_factory,
            now=now,
        )

    assert "http_status=401" in caplog.text
    assert "stage=tts_request" in caplog.text
    assert "content_type=application/json" in caplog.text
    assert "Invalid api key=[REDACTED]" in caplog.text
    assert gnani.api_key not in caplog.text
    assert "mock-api-key-secret" not in caplog.text


def test_invalid_audio_response_is_logged_at_validation_stage(
    scheduler_db,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _, session_factory, (family_id, elderly_id) = scheduler_db
    now = datetime.now(timezone.utc)
    reminder_id = add_reminder(
        session_factory, family_id, elderly_id, now - timedelta(seconds=1)
    )

    class InvalidAudioService(MockGnaniService):
        def generate_speech(self, *, text: str, language: str) -> bytes:
            self.messages.append(text)
            return b"not-a-wav"

    with caplog.at_level("WARNING", logger=reminder_scheduler.__name__):
        reminder_scheduler.process_due_reminders(
            InvalidAudioService(),
            session_factory=session_factory,
            now=now,
        )

    assert "stage=wav_validation_and_file_write" in caplog.text
    with session_factory() as session:
        occurrence = session.scalar(
            select(ReminderOccurrence).where(
                ReminderOccurrence.reminder_id == reminder_id
            )
        )
    assert occurrence.status == ReminderStatus.FAILED
    assert occurrence.audio_file_path is None


def test_cancelled_reminders_are_ignored(scheduler_db) -> None:
    _, session_factory, (family_id, elderly_id) = scheduler_db
    reminder_id = add_reminder(
        session_factory,
        family_id,
        elderly_id,
        datetime.now(timezone.utc) - timedelta(seconds=1),
        status=ReminderStatus.CANCELLED,
    )
    gnani = MockGnaniService()

    processed = reminder_scheduler.process_due_reminders(
        gnani,
        session_factory=session_factory,
        now=datetime.now(timezone.utc),
    )

    assert processed == 0
    assert gnani.messages == []
    with session_factory() as session:
        assert session.scalar(
            select(ReminderOccurrence).where(
                ReminderOccurrence.reminder_id == reminder_id
            )
        ) is None


def test_restart_recovers_written_audio_without_regenerating(scheduler_db) -> None:
    _, session_factory, (family_id, elderly_id) = scheduler_db
    now = datetime.now(timezone.utc)
    scheduled_at = now - timedelta(minutes=10)
    reminder_id = add_reminder(
        session_factory,
        family_id,
        elderly_id,
        scheduled_at,
        status=ReminderStatus.PROCESSING,
    )
    relative_audio_path = "generated_audio/recovered-audio.wav"
    audio_path = reminder_scheduler.GENERATED_AUDIO_DIR.parent / relative_audio_path
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(b"RIFF-recovered-wav")
    with session_factory() as session:
        occurrence = ReminderOccurrence(
            reminder_id=reminder_id,
            occurrence_at=scheduled_at,
            status=ReminderStatus.PROCESSING,
            attempt_count=1,
            audio_file_path=relative_audio_path,
            updated_at=now - timedelta(
                seconds=reminder_scheduler.PROCESSING_LEASE_SECONDS + 1
            ),
        )
        session.add(occurrence)
        session.commit()
    gnani = MockGnaniService()

    processed = reminder_scheduler.process_due_reminders(
        gnani, session_factory=session_factory, now=now
    )

    with session_factory() as session:
        occurrence = session.scalar(
            select(ReminderOccurrence).where(
                ReminderOccurrence.reminder_id == reminder_id
            )
        )
        reminder = session.get(Reminder, reminder_id)
    assert processed == 1
    assert gnani.messages == []
    assert occurrence.status == ReminderStatus.AUDIO_READY
    assert reminder.status == ReminderStatus.AUDIO_READY


def test_scheduler_is_singleton_and_shuts_down_cleanly() -> None:
    gnani = MockGnaniService()

    async def exercise_lifecycle() -> None:
        first = reminder_scheduler.start_scheduler(gnani)
        second = reminder_scheduler.start_scheduler(gnani)
        assert first is second
        assert reminder_scheduler.scheduler_status()["running"] is True
        reminder_scheduler.stop_scheduler()
        assert reminder_scheduler.scheduler_status()["running"] is False

    asyncio.run(exercise_lifecycle())