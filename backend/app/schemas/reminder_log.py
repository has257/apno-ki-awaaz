from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.enums import ReminderEventType
from app.schemas.common import normalize_output_datetime


class ReminderLogCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: ReminderEventType
    event_message: str | None = Field(default=None, max_length=1000)


class ReminderLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reminder_id: int
    event_type: ReminderEventType
    event_message: str | None
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def make_created_at_aware(cls, value: datetime) -> datetime:
        return normalize_output_datetime(value)