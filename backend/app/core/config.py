"""Application settings. Every secret/endpoint comes from the environment."""

from __future__ import annotations

import os
import socket

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "PetCare System"
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://petcare:petcare@localhost:5432/petcare"
    jwt_secret: str = "dev-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    app_tz: str = "Asia/Bangkok"
    cors_origins: str = "http://localhost,http://localhost:5173"
    instance_id: str = Field(
        default_factory=lambda: os.getenv("INSTANCE_ID") or socket.gethostname()
    )
    booking_horizon_days: int = 30
    cancellation_window_hours: int = 2
    reminder_hours_before: int = 1
    worker_poll_seconds: float = 5.0
    heartbeat_file: str = "/tmp/petcare-worker-heartbeat"
    outbox_batch_size: int = 100
    outbox_max_attempts: int = 10
    photo_dir: str = "/data/pet-photos"
    photo_max_bytes: int = 8 * 1024 * 1024
    photo_max_dimension: int = 1024
    photo_quality: int = 82

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
