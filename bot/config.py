from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", 
        env_file_encoding="utf-8",
        extra="ignore"
    )

    discord_token: str = Field(..., validation_alias="DISCORD_TOKEN")
    gemini_api_key: str = Field(default="", validation_alias="GEMINI_API_KEY")
    database_url: str = Field(default="sqlite+aiosqlite:///data/cphub.db", validation_alias="DATABASE_URL")

# 實例化
settings = Settings()