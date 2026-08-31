from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TSYNCER_",
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    basic_user: str
    basic_password: str
    sqlite_db_path: str = "tsyncer.db"
    host: str = "127.0.0.1"
    port: int = 7100
    reload: bool = False
    log_level: str = "INFO"
