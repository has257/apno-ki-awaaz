from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.enums import UserRole
from app.schemas.common import normalize_output_datetime, normalize_phone_number


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=1, max_length=120)
    phone_number: str = Field(
        min_length=7,
        max_length=16,
        pattern=r"^\+?[0-9]{7,15}$",
    )
    role: UserRole

    @field_validator("full_name", mode="before")
    @classmethod
    def trim_full_name(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @field_validator("phone_number", mode="before")
    @classmethod
    def clean_phone_number(cls, value: str) -> str:
        return normalize_phone_number(value) if isinstance(value, str) else value


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    phone_number: str
    role: UserRole
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def make_created_at_aware(cls, value: datetime) -> datetime:
        return normalize_output_datetime(value)