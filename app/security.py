from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4
import hashlib
import hmac
import os

import jwt

from app.config import settings


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or os.urandom(16).hex()
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 120_000)
    return f'pbkdf2_sha256${salt}${dk.hex()}'


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt, digest = stored.split('$', 2)
        if algo != 'pbkdf2_sha256':
            return False
        computed = hash_password(password, salt)
        return hmac.compare_digest(computed, stored)
    except Exception:
        return False


def _create_token(sub: str, token_type: str, expires_delta: timedelta) -> str:
    payload = {
        'sub': sub,
        'type': token_type,
        'jti': str(uuid4()),
        'iat': utc_now(),
        'exp': utc_now() + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str) -> str:
    return _create_token(user_id, 'access', timedelta(minutes=settings.access_token_exp_minutes))


def create_refresh_token(user_id: str) -> str:
    return _create_token(user_id, 'refresh', timedelta(days=settings.refresh_token_exp_days))


def decode_token(token: str, expected_type: Optional[str] = None) -> dict:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if expected_type and payload.get('type') != expected_type:
        raise jwt.InvalidTokenError('invalid token type')
    if not payload.get('jti'):
        raise jwt.InvalidTokenError('missing jti')
    return payload
