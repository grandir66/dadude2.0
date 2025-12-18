"""
DaDude v2.0 - Configuration Settings
Supports PostgreSQL + Redis (v2) or SQLite (legacy)
"""
from pydantic_settings import BaseSettings
from pydantic import Field, computed_field
from typing import Optional
from functools import lru_cache
import os


class Settings(BaseSettings):
    """Configurazione applicazione DaDude"""

    # Dude Server
    dude_host: str = Field(default="192.168.1.1", description="Dude Server IP/hostname")
    dude_api_port: int = Field(default=8728, description="RouterOS API port")
    dude_use_ssl: bool = Field(default=False, description="Use SSL for API connection")
    dude_username: str = Field(default="admin", description="RouterOS username")
    dude_password: str = Field(default="", description="RouterOS password")

    # DaDude Server
    dadude_host: str = Field(default="0.0.0.0", description="DaDude bind host")
    dadude_port: int = Field(default=8000, description="DaDude port")
    dadude_api_key: str = Field(default="", description="API key for authentication")

    # Database - PostgreSQL (v2) or SQLite (legacy)
    database_url: str = Field(
        default="postgresql+asyncpg://dadude:dadude_secret@localhost:5432/dadude",
        description="Database connection URL (PostgreSQL async)"
    )
    database_url_sync: Optional[str] = Field(
        default=None,
        description="Database connection URL (sync, for migrations/tooling)"
    )

    # Database Pool Settings (PostgreSQL)
    db_pool_size: int = Field(default=5, description="Database connection pool size")
    db_max_overflow: int = Field(default=10, description="Max overflow connections")
    db_pool_timeout: int = Field(default=30, description="Pool connection timeout")
    db_pool_recycle: int = Field(default=1800, description="Recycle connections after N seconds")

    # Redis Cache (v2)
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )
    redis_enabled: bool = Field(default=True, description="Enable Redis cache")

    # Polling
    poll_interval: int = Field(default=60, description="Device poll interval (seconds)")
    full_sync_interval: int = Field(default=300, description="Full sync interval (seconds)")
    connection_timeout: int = Field(default=30, description="Connection timeout (seconds)")

    # Logging
    log_level: str = Field(default="INFO", description="Log level")
    log_file: str = Field(default="./logs/dadude.log", description="Log file path")

    # Webhook
    webhook_url: Optional[str] = Field(default=None, description="External webhook URL")
    webhook_secret: Optional[str] = Field(default=None, description="Webhook secret")

    # Encryption
    encryption_key: Optional[str] = Field(default=None, description="Master encryption key for credentials")

    # GitHub (per creazione release automatiche)
    github_token: Optional[str] = Field(default=None, description="GitHub token for creating releases")

    @computed_field
    @property
    def database_url_sync_computed(self) -> str:
        """Get sync database URL for migrations/tooling"""
        if self.database_url_sync:
            return self.database_url_sync
        # Convert async URL to sync
        url = self.database_url
        if "+asyncpg" in url:
            return url.replace("+asyncpg", "")
        if "+aiosqlite" in url:
            return url.replace("+aiosqlite", "")
        return url

    @computed_field
    @property
    def is_postgres(self) -> bool:
        """Check if using PostgreSQL"""
        return "postgresql" in self.database_url.lower()

    @computed_field
    @property
    def is_sqlite(self) -> bool:
        """Check if using SQLite (legacy mode)"""
        return "sqlite" in self.database_url.lower()

    class Config:
        # Usa .env nella directory data (persistente)
        env_file = "./data/.env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        # Permetti override da variabili ambiente per compatibilità docker-compose
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


def clear_settings_cache():
    """Clear settings cache (useful for testing)"""
    get_settings.cache_clear()
