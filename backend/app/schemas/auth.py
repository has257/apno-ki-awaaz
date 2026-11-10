from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserCreate, UserRead


class RegisterRequest(UserCreate):
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone_number: str = Field(min_length=7, max_length=16)
    password: str = Field(min_length=1, max_length=128)


class PasswordSetupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    setup_token: str = Field(min_length=1, max_length=4096)
    new_password: str = Field(min_length=12, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead