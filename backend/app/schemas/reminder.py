from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.enums import ReminderRecurrence, ReminderStatus
from app.schemas.common import normalize_output_datetime, require_aware_utc
from app.schemas.reminder_log import ReminderLogRead


class ReminderFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=150)
    message: str = Field(min_length=1, max_length=2000)
    elderly_user_id: int = Field(gt=0)
    scheduled_at: datetime
    recurrence: ReminderRecurrence = ReminderRecurrence.ONCE

    @field_validator("title", "message", mode="before")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @field_validator("scheduled_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        return require_aware_utc(value)


class ReminderCreate(ReminderFields):
    pass


class ReminderUpdate(ReminderFields):
    pass


class ReminderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    message: str
    elderly_user_id: int
    created_by: int
    scheduled_at: datetime
    recurrence: ReminderRecurrence
    status: ReminderStatus
    created_at: datetime
    updated_at: datetime
    logs: list[ReminderLogRead] = Field(default_factory=list)

    @field_validator("scheduled_at", "created_at", "updated_at", mode="before")
    @classmethod
    def make_timestamps_aware(cls, value: datetime) -> datetime:
        return normalize_output_datetime(value)


class ReminderAudioOccurrenceRead(BaseModel):
    occurrence_at: datetime
    status: ReminderStatus
    audio_available: bool
    generated_at: datetime | None
    attempt_count: int

    @field_validator("occurrence_at", "generated_at", mode="before")
    @classmethod
    def make_timestamps_aware(cls, value: datetime | None) -> datetime | None:
        return normalize_output_datetime(value) if value is not None else None


class ReminderAudioMetadataRead(BaseModel):
    reminder_id: int
    occurrences: list[ReminderAudioOccurrenceRead]