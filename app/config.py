from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "multi-agent-productivity-assistant"
    app_env: str = "development"
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "INFO"

    google_api_key: Optional[str] = None
    google_genai_model: str = "gemini-2.5-flash"
    google_use_vertex_ai: bool = False
    google_cloud_project: Optional[str] = None
    google_cloud_location: str = "us-central1"
    google_calendar_client_id: Optional[str] = None
    google_calendar_client_secret: Optional[str] = None
    google_calendar_refresh_token: Optional[str] = None
    google_calendar_id: str = "primary"
    google_calendar_timezone: str = "Asia/Kolkata"

    database_url: str = "sqlite:///./data/app.db"
    allowed_origins: List[str] = Field(default_factory=lambda: ["*"])

    mcp_servers_json: Optional[str] = None
    mcp_servers_file: Optional[str] = None
    mcp_protocol_version: str = "2025-11-25"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def resolved_mcp_servers_json(self) -> Optional[str]:
        if self.mcp_servers_json:
            return self.mcp_servers_json
        if self.mcp_servers_file:
            return Path(self.mcp_servers_file).read_text(encoding="utf-8")
        return None

    def google_calendar_configured(self) -> bool:
        return bool(
            self.google_calendar_client_id
            and self.google_calendar_client_secret
            and self.google_calendar_refresh_token
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
