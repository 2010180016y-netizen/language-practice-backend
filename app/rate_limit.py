from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from app.config import settings

try:
    import redis
except Exception:  # pragma: no cover - optional dependency at runtime
    redis = None


class InMemoryRateLimiter:
    def __init__(self, per_minute: int = 120):
        self.per_minute = per_minute
        self._buckets: dict[str, deque[datetime]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=1)
        bucket = self._buckets[key]

        while bucket and bucket[0] < window_start:
            bucket.popleft()

        if len(bucket) >= self.per_minute:
            return False

        bucket.append(now)
        return True


class RedisRateLimiter:
    def __init__(self, per_minute: int = 120, redis_url: str = 'redis://localhost:6379/0'):
        if redis is None:
            raise RuntimeError('redis package is not installed')
        self.per_minute = per_minute
        self.client = redis.Redis.from_url(redis_url, decode_responses=True)

    def allow(self, key: str) -> bool:
        now = datetime.now(timezone.utc)
        bucket_key = f'rate:{key}:{now.strftime("%Y%m%d%H%M")}'
        count = self.client.incr(bucket_key)
        if count == 1:
            self.client.expire(bucket_key, 70)
        return count <= self.per_minute


def build_rate_limiter() -> InMemoryRateLimiter | RedisRateLimiter:
    if settings.redis_url:
        try:
            return RedisRateLimiter(settings.rate_limit_per_minute, settings.redis_url)
        except Exception:
            pass
    return InMemoryRateLimiter(settings.rate_limit_per_minute)
