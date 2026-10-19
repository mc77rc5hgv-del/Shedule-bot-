from functools import cached_property
from zoneinfo import ZoneInfo

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str = Field(min_length=10)
    admin_ids: str = ""
    database_url: str = "sqlite+aiosqlite:///data/schedule.db"
    timezone: str = "Europe/Moscow"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @cached_property
    def admins(self) -> frozenset[int]:
        return frozenset(int(value.strip()) for value in self.admin_ids.split(",") if value.strip())

    @cached_property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)
