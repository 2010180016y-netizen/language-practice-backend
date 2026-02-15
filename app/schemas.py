from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = 'bearer'


class UserSignupRequest(BaseModel):
    user_id: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    terms_accepted: bool = False

    @field_validator('user_id')
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        allowed = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-')
        if any(ch not in allowed for ch in v):
            raise ValueError('user_id may only contain letters, numbers, _ and -')
        return v


class UserLoginRequest(BaseModel):
    user_id: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class HealthResponse(BaseModel):
    status: str
    version: str


class ReadyResponse(BaseModel):
    status: Literal['ready', 'degraded']
    db: str
    redis: str


class QueueMetricsResponse(BaseModel):
    main_depth: int
    dlq_depth: int
    oldest_job_age_seconds: int
    alert: bool


class OnboardingGoal(BaseModel):
    goal_type: Literal['business', 'daily', 'both'] = 'both'
    target_language: str = 'English'
    minutes_per_day: int = Field(ge=5, le=120)


class CalculatedPlan(BaseModel):
    minutes_per_day: int
    words_count: int
    sentences_count: int
    chat_turns: int
    plan_preview: str


class ChatAnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    tone_preference: Literal['business', 'daily'] = 'business'


class ChatAlternative(BaseModel):
    category: str
    text: str


class ChatAnalyzeResponse(BaseModel):
    original: str
    alternatives: list[ChatAlternative]


class ImportRequest(BaseModel):
    channel: Literal['daily', 'business']
    content: str = Field(min_length=1, max_length=100_000)
    idempotency_key: Optional[str] = None


class ImportJob(BaseModel):
    job_id: str
    status: Literal['queued', 'processing', 'completed', 'failed']
    progress_percent: int
    created_at: datetime


class ImportListResponse(BaseModel):
    items: list[ImportJob]
    total: int
    offset: int
    limit: int
