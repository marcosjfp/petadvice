"""Runtime configuration. Secrets stay in environment variables or an ignored .env."""
import secrets
from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    app_env: Literal['development', 'test', 'production'] = 'development'
    database_url: str = 'sqlite:///./petadvice.db'
    jwt_secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    cors_origins: str = 'http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174'
    public_web_url: str = 'http://127.0.0.1:5173'
    trusted_hosts: str = 'localhost,127.0.0.1,testserver'
    rate_limit_storage_uri: str = 'memory://'
    guest_retention_hours: int = Field(default=24, ge=1, le=720)
    require_email_verification: bool = False
    mail_backend: Literal['file', 'smtp'] = 'file'
    mail_directory: str = '.mail'
    mail_encryption_key: str = ''
    backup_encryption_key: str = ''
    smtp_host: str = ''
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = ''
    smtp_password: str = ''
    smtp_from: str = ''
    smtp_starttls: bool = True
    smtp_ssl: bool = False
    privacy_operator: str = ''
    privacy_email: str = ''
    privacy_policy_url: str = ''
    privacy_policy_version: str = 'beta-2026-10-09'

    @property
    def production(self) -> bool:
        return self.app_env == 'production'

    @property
    def email_verification_required(self) -> bool:
        return self.production or self.require_email_verification

    @property
    def origins(self) -> list[str]:
        return [value.strip().rstrip('/') for value in self.cors_origins.split(',') if value.strip()]

    def validate_production(self) -> None:
        if not self.production:
            return
        if 'jwt_secret_key' not in self.model_fields_set or len(self.jwt_secret_key) < 32 or self.jwt_secret_key == 'dev-only-insecure-secret-change-me':
            raise RuntimeError('Production requires a stable random JWT_SECRET_KEY of at least 32 characters')
        if not self.database_url.startswith(('postgresql://', 'postgresql+psycopg://', 'postgres://')):
            raise RuntimeError('Production requires PostgreSQL DATABASE_URL')
        if not self.rate_limit_storage_uri.startswith(('redis://', 'rediss://')):
            raise RuntimeError('Production requires shared Redis rate-limit storage')
        if not self.origins or any(not value.startswith('https://') or '*' in value for value in self.origins):
            raise RuntimeError('Production requires explicit HTTPS CORS_ORIGINS')
        if not self.public_web_url.startswith('https://'):
            raise RuntimeError('Production requires HTTPS PUBLIC_WEB_URL')
        public = urlsplit(self.public_web_url)
        if not public.hostname or public.username or public.password or public.query or public.fragment or public.path not in ('', '/'):
            raise RuntimeError('PUBLIC_WEB_URL must be a clean HTTPS site origin')
        for origin in self.origins:
            parsed = urlsplit(origin)
            if not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
                raise RuntimeError('CORS_ORIGINS must contain exact HTTPS site origins')
        if not self.trusted_hosts or '*' in self.trusted_hosts:
            raise RuntimeError('Production requires explicit TRUSTED_HOSTS')
        if self.mail_backend != 'smtp' or not self.smtp_host or not self.smtp_from or not self.mail_encryption_key:
            raise RuntimeError('Production requires SMTP delivery and MAIL_ENCRYPTION_KEY')
        if not self.smtp_ssl and not self.smtp_starttls:
            raise RuntimeError('SMTP delivery requires TLS')
        from cryptography.fernet import Fernet
        try:
            Fernet(self.mail_encryption_key)
        except (ValueError, TypeError) as error:
            raise RuntimeError('MAIL_ENCRYPTION_KEY must be a valid Fernet key') from error
        if not self.privacy_operator or not self.privacy_email or not self.privacy_policy_url.startswith('https://'):
            raise RuntimeError('Complete operator, privacy contact and policy URL before public release')


@lru_cache
def get_settings() -> Settings:
    return Settings()
