"""Application configuration settings for the Unified Ayo's Den & IoChat Engine."""

from __future__ import annotations

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Configuration settings loaded from environment variables with safe defaults."""

    # Project Information
    app_name: str = "Ayo's Den Studio Command Deck"
    app_version: str = "2.0.0"
    target_channel: str = "Ayo's Den"

    # Google Cloud & Vertex AI / Gemini
    google_cloud_project: str = "yt-ayochat-prod"
    google_cloud_location: str = "us-central1"
    gemini_model_name: str = "gemini-2.5-flash"

    # YouTube Data API v3
    youtube_api_key: str = ""
    client_secret_path: str = "client_secret.json"
    token_path: str = "token.json"
    target_video_ids: str = "M1G92FWmdJw,wJph6fDaJuk"
    dispatch_dry_run: bool = True

    # State & Persistence Files
    db_path: Path = Path("app/data/ayos_den_studio.db")
    queue_json_path: Path = Path("queue.json")
    competitor_insights_path: Path = Path("competitor_insights.json")

    # WebMCP & WebSocket Bridge
    ws_host: str = "0.0.0.0"
    ws_port: int = 8000
    cors_allowed_origins: list[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def target_video_id_list(self) -> list[str]:
        return [vid.strip() for vid in self.target_video_ids.split(",") if vid.strip()]


config = AppConfig()
