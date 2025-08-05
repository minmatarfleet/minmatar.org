import os
from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_env_file() -> str:
    """Choose the env file to load"""

    file = ".env"

    specified_env_file = os.getenv("ENV_FILE")
    if specified_env_file:
        if os.path.exists(specified_env_file):
            file = specified_env_file
        else:
            raise ValueError(
                f"Error loading environment file. ENV_FILE '{specified_env_file}' does not exist."
            )

    return file


class EnvConfig(BaseSettings):
    """Application configuration with validation and type safety."""

    model_config = SettingsConfigDict(
        env_file=get_env_file(),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_nested_delimiter="__",
        # Don't try to parse string values as JSON for these fields
        env_parse_none_str="",
    )

    # =============================================================================
    # save current env file
    # =============================================================================

    env_file_used: str = Field(
        default=get_env_file(),
        description="Path to the environment file used for configuration",
    )

    # =============================================================================
    # Django settings
    # =============================================================================

    secret_key: str = Field(
        ...,
        description="Django secret key for cryptographic signing",
        min_length=1,
    )

    shared_secret: str = Field(
        ...,
        description="todo - what is this?",
        min_length=1,
    )

    debug: bool = Field(default=False, description="Set Django debug mode")

    allowed_hosts: Union[List[str], str] = Field(
        default=["*"], description="List of allowed host/domain names"
    )

    csrf_trusted_origins: Union[List[str], str] = Field(
        default=["https://api.minmatar.org", "https://minmatar.org"],
        description="List of trusted origins for CSRF validation",
    )

    # =============================================================================
    # Database Configuration
    # =============================================================================

    db_host: str = Field(default="127.0.0.1", description="Database host")

    db_port: int = Field(
        default=3306, description="Database port", ge=1, le=65535
    )

    db_name: str = Field(default="minmatar", description="Database name", min_length=1)

    db_user: str = Field(default="root", description="Database user", min_length=1)

    db_password: str = Field(default="example", description="Database password")

    # =============================================================================
    # Discord Integration
    # =============================================================================

    discord_bot_token: str = Field(
        ..., description="Discord bot token for API access", min_length=1
    )

    discord_client_id: str = Field(
        ..., description="Discord OAuth2 client ID", min_length=1
    )

    discord_client_secret: str = Field(
        ..., description="Discord OAuth2 client secret", min_length=1
    )

    discord_guild_id: int = Field(
        ..., description="Discord guild/server ID", gt=0
    )

    discord_api_base_url: str = Field(
        default="https://discord.com/api/v9",
        description="Discord API base URL",
    )

    # =============================================================================
    # EVE Online ESI Configuration
    # =============================================================================

    esi_sso_client_id: str = Field(
        ..., description="EVE Online ESI client ID", min_length=1
    )

    esi_sso_client_secret: str = Field(
        ..., description="EVE Online ESI client secret", min_length=1
    )

    esi_sso_callback_url: str = Field(
        ..., description="EVE Online ESI OAuth callback URL", min_length=1
    )

    # =============================================================================
    # Redis/Celery Configuration
    # =============================================================================

    broker_url: str = Field(
        default="redis://localhost:6379/0", description="Celery broker URL"
    )

    # =============================================================================
    # Sentry Configuration
    # =============================================================================

    sentry_auth_token: str = Field(
        default="", description="Sentry DSN auth token (optional)"
    )

    sentry_dsn: str = Field(
        default="", description="Sentry DSN for error tracking (optional)"
    )

    sentry_backend_dsn: str = Field(
        default="",
        description="Backend DSN for Sentry error tracking (optional)",
    )

    sentry_celery_dsn: str = Field(
        default="",
        description="Celery DSN for Sentry error tracking (optional)",
    )

    # =============================================================================
    # Validators
    # =============================================================================

    @field_validator("sentry_auth_token", "sentry_dsn", "sentry_backend_dsn", "sentry_celery_dsn", mode="before")
    @classmethod
    def parse_sentry_fields(cls, v):
        """Convert None values to empty strings for optional Sentry fields."""
        if v is None:
            return ""
        return v

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, v):
        """Parse comma-separated ALLOWED_HOSTS string into list."""
        if isinstance(v, str):
            # Handle special case of '*' (allow all hosts)
            if v.strip() == "*":
                return ["*"]
            # Parse comma-separated values
            return [host.strip() for host in v.split(",") if host.strip()]
        return v

    @field_validator("csrf_trusted_origins", mode="before")
    @classmethod
    def parse_csrf_trusted_origins(cls, v):
        """Parse comma-separated CSRF_TRUSTED_ORIGINS string into list."""
        if isinstance(v, str):
            # Parse comma-separated values
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("discord_api_base_url")
    @classmethod
    def validate_discord_url(cls, v):
        """Ensure Discord API URL is valid."""
        if not v.startswith(("http://", "https://")):
            raise ValueError(
                "Discord API URL must start with http:// or https://"
            )
        return v.rstrip("/")  # Remove trailing slash

    @field_validator("esi_sso_callback_url")
    @classmethod
    def validate_esi_callback_url(cls, v):
        """Ensure ESI callback URL is valid."""
        if not v.startswith(("http://", "https://")):
            raise ValueError(
                "ESI callback URL must start with http:// or https://"
            )
        return v

    # =============================================================================
    # Computed Properties
    # =============================================================================
    @property
    def environment(self) -> str: 
        """Application environment. Only development or production. Based on debug setting."""
        return "development" if self.debug else "production"

    @property
    def database_url(self) -> str:
        """Construct database URL from components."""
        return f"mysql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


# Create global configuration instance
config = EnvConfig()
