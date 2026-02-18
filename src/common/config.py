"""Application configuration using Pydantic Settings"""
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    service_name: str = Field(default="confluent-billing-portal")
    service_version: str = Field(default="0.1.0")
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")

    # API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_workers: int = Field(default=4)

    # Database
    database_url: str = Field(
        default="postgresql://billing_user:billing_password@localhost:5432/billing_db",
        description="PostgreSQL connection URL",
    )

    # Confluent Cloud API
    confluent_api_key: str = Field(default="", description="Confluent Cloud API key")
    confluent_api_secret: str = Field(default="", description="Confluent Cloud API secret")
    confluent_cloud_url: str = Field(
        default="https://api.confluent.cloud",
        description="Confluent Cloud API base URL",
    )

    # Metrics API (optional)
    metrics_api_url: str = Field(default="")
    metrics_api_key: str = Field(default="")

    # Scheduler Configuration
    scheduler_enabled: bool = Field(default=True, description="Enable scheduler")
    hourly_job_enabled: bool = Field(default=True, description="Enable hourly collection job")
    daily_job_enabled: bool = Field(default=True, description="Enable daily billing job")

    # API server
    api_server_enabled: bool = Field(default=True, description="Enable API server")
    api_server_host: str = Field(default="0.0.0.0", description="API server host")
    api_server_port: int = Field(default=8000, description="API server port")

    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment.lower() == "development"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
