from datetime import datetime

from pydantic import AliasPath, BaseModel, ConfigDict, Field, field_validator

from app.enums import FamilyElderlyLinkStatus
from app.schemas.common import normalize_output_datetime


class LinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    elderly_user_id: int = Field(gt=0)


class FamilyElderlyLinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_user_id: int
    elderly_user_id: int
    family_name: str = Field(validation_alias=AliasPath("family_user", "full_name"))
    elderly_name: str = Field(validation_alias=AliasPath("elderly_user", "full_name"))
    status: FamilyElderlyLinkStatus
    requested_at: datetime
    responded_at: datetime | None
    created_at: datetime

    @field_validator("requested_at", "responded_at", "created_at", mode="before")
    @classmethod
    def make_timestamps_aware(cls, value: datetime | None) -> datetime | None:
        return normalize_output_datetime(value) if value is not None else None