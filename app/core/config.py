"""
Core configuration module for Prontivus backend.
Handles environment variables, settings, and application configuration.
"""

import os
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    app_name: str = Field(default="Prontivus", env="APP_NAME")
    app_version: str = Field(default="1.0.0", env="APP_VERSION")
    app_env: str = Field(default="development", env="APP_ENV")
    debug: bool = Field(default=False, env="DEBUG")
    api_url: str = Field(default="https://prontivus-backend-wnw2.onrender.com", env="API_URL")
    
    # Security
    secret_key: str = Field(default="dev-secret-key-change-in-production")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(default=15, env="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    jwt_refresh_token_expire_days: int = Field(default=30, env="JWT_REFRESH_TOKEN_EXPIRE_DAYS")
    jwt_private_key: Optional[str] = Field(default=None, env="JWT_PRIVATE_KEY")
    jwt_public_key: Optional[str] = Field(default=None, env="JWT_PUBLIC_KEY")
    
    # Database
    database_url: str = Field(default="postgresql+asyncpg://prontivus_v52p_user:E01bQ3fektSOxxZXX6EGz57YfPXIExDW@dpg-d3iej3k9c44c73anq430-a.oregon-postgres.render.com/prontivus_v52p", env="DATABASE_URL")
    database_pool_size: int = Field(default=10, env="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=20, env="DATABASE_MAX_OVERFLOW")
    
    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    redis_cache_ttl: int = Field(default=3600, env="REDIS_CACHE_TTL")
    
    # File Storage
    s3_endpoint: str = Field(default="http://localhost:9000", env="S3_ENDPOINT")
    s3_access_key: str = Field(default="minioadmin", env="S3_ACCESS_KEY")
    s3_secret_key: str = Field(default="minioadmin", env="S3_SECRET_KEY")
    s3_bucket: str = Field(default="prontivus-files", env="S3_BUCKET")
    s3_region: str = Field(default="us-east-1", env="S3_REGION")
    
    # External Integrations
    tiss_api_url: str = Field(default="https://api.tiss.gov.br/v1", env="TISS_API_URL")
    tiss_api_key: Optional[str] = Field(default=None, env="TISS_API_KEY")
    
    # Payment Providers
    paypal_client_id: Optional[str] = Field(default=None, env="PAYPAL_CLIENT_ID")
    paypal_secret: Optional[str] = Field(default=None, env="PAYPAL_SECRET")
    paypal_mode: str = Field(default="sandbox", env="PAYPAL_MODE")
    
    # Telemedicine
    telemed_provider: str = Field(default="conexa", env="TELEMED_PROVIDER")
    telemed_api_key: Optional[str] = Field(default=None, env="TELEMED_API_KEY")
    
    # License Management
    rsa_license_private: Optional[str] = Field(default=None, env="RSA_LICENSE_PRIVATE")
    rsa_license_public: Optional[str] = Field(default=None, env="RSA_LICENSE_PUBLIC")
    
    # Monitoring
    sentry_dsn: Optional[str] = Field(default=None, env="SENTRY_DSN")
    prometheus_port: int = Field(default=8001, env="PROMETHEUS_PORT")
    
    # Email
    smtp_host: Optional[str] = Field(default=None, env="SMTP_HOST")
    smtp_port: int = Field(default=587, env="SMTP_PORT")
    smtp_username: Optional[str] = Field(default=None, env="SMTP_USERNAME")
    smtp_password: Optional[str] = Field(default=None, env="SMTP_PASSWORD")
    
    # Rate Limiting
    rate_limit_per_minute: int = Field(default=60, env="RATE_LIMIT_PER_MINUTE")
    rate_limit_burst: int = Field(default=100, env="RATE_LIMIT_BURST")
    
    # Offline Sync
    offline_grace_hours: int = Field(default=72, env="OFFLINE_GRACE_HOURS")
    sync_batch_size: int = Field(default=100, env="SYNC_BATCH_SIZE")
    
    # CORS
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:5173,http://localhost:8080,http://localhost:8000,https://prontivus-frontend-ten.vercel.app",
        env="CORS_ORIGINS"
    )
    cors_allow_credentials: bool = Field(default=True)
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Get CORS origins as a list."""
        if isinstance(self.cors_origins, str):
            return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        return self.cors_origins
    
    @field_validator("jwt_private_key", "jwt_public_key", mode="before")
    @classmethod
    def parse_jwt_keys(cls, v):
        if v and isinstance(v, str):
            return v.replace("\\n", "\n")
        return v
    
    @field_validator("rsa_license_private", "rsa_license_public", mode="before")
    @classmethod
    def parse_rsa_keys(cls, v):
        if v and isinstance(v, str):
            return v.replace("\\n", "\n")
        return v
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app_env.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.app_env.lower() == "development"
    
    @property
    def database_url_sync(self) -> str:
        """Get synchronous database URL for Alembic migrations."""
        # Replace asyncpg with psycopg (psycopg3 for Python 3.13 compatibility)
        return self.database_url.replace("+asyncpg", "+psycopg")
    
    model_config = {
        "case_sensitive": False,
        "env_prefix": "",
        "extra": "ignore"
    }


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()


# Global settings instance
settings = get_settings()
