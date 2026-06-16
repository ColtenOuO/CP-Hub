from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    discord_token: str = Field(..., validation_alias="DISCORD_TOKEN")
    gemini_api_key: str = Field(default="", validation_alias="GEMINI_API_KEY")
    database_url: str = Field(default="postgresql+asyncpg://cphub:cphub@localhost:5432/cphub", validation_alias="DATABASE_URL")
    admin_discord_ids: list[int] = Field(default=[], validation_alias="ADMIN_DISCORD_IDS")

    @field_validator("admin_discord_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: object) -> list[int]:
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        return v  # type: ignore[return-value]


settings = Settings()
