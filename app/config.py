from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'Language Practice Backend'
    app_version: str = '3.1.0'

    jwt_secret: str = 's3cure-change-me-via-secret-manager-please-2026'
    jwt_algorithm: str = 'HS256'
    access_token_exp_minutes: int = 30
    refresh_token_exp_days: int = 14

    rate_limit_per_minute: int = 120
    redis_url: str | None = None

    database_url: str = 'sqlite:///./language_practice.db'
    production_database_url: str | None = None

    queue_mode: str = 'inmemory'  # inmemory | redis
    queue_name: str = 'import_jobs'
    dead_letter_queue_name: str = 'import_jobs_dlq'
    max_job_retries: int = 3
    backoff_base_seconds: int = 2
    queue_depth_alert_threshold: int = 1000

    cors_allow_origins: str = 'https://app.example.com'
    enforce_https: bool = True
    hsts_enabled: bool = True

    sentry_dsn: str | None = None
    slack_webhook_url: str | None = None
    pagerduty_events_url: str | None = None

    slo_availability_target: float = 99.9
    slo_p95_latency_ms: int = 300

    allow_self_registration: bool = False


settings = Settings()
