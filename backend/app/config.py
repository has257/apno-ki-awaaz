
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Apno Ki Awaaz"
    app_env: str = "development"

    gnani_api_key: str
    database_url: str | None = None
    jwt_secret: str | None = None
    jwt_access_token_expire_minutes: int = Field(default=30, ge=1, le=1440)

    gnani_tts_model: str = "timbre-v2.5"
    gnani_tts_voice: str = "Yashvi"
    gnani_tts_language: str = "te-IN"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
