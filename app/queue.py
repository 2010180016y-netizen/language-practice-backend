from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from dataclasses import dataclass

from app.config import settings

try:
    import redis
except Exception:  # pragma: no cover
    redis = None


@dataclass
class QueueMetrics:
    main_depth: int
    dlq_depth: int
    oldest_job_age_seconds: int


class InMemoryQueue:
    def __init__(self):
        self._q: deque[tuple[str, datetime]] = deque()
        self._dlq: deque[tuple[str, datetime]] = deque()

    def enqueue(self, job_id: str) -> None:
        self._q.append((job_id, datetime.now(timezone.utc)))

    def dequeue(self) -> str | None:
        if not self._q:
            return None
        return self._q.popleft()[0]

    def enqueue_dead_letter(self, job_id: str) -> None:
        self._dlq.append((job_id, datetime.now(timezone.utc)))

    def metrics(self) -> QueueMetrics:
        oldest = 0
        now = datetime.now(timezone.utc)
        if self._q:
            oldest = int((now - self._q[0][1]).total_seconds())
        return QueueMetrics(main_depth=len(self._q), dlq_depth=len(self._dlq), oldest_job_age_seconds=oldest)


class RedisQueue:
    def __init__(self, redis_url: str, queue_name: str, dead_letter_queue_name: str):
        if redis is None:
            raise RuntimeError('redis package not installed')
        self.client = redis.Redis.from_url(redis_url, decode_responses=True)
        self.queue_name = queue_name
        self.dead_letter_queue_name = dead_letter_queue_name
        self.enqueue_time_zset = f'{queue_name}:enqueue_times'

    def enqueue(self, job_id: str) -> None:
        now_ts = int(datetime.now(timezone.utc).timestamp())
        pipe = self.client.pipeline()
        pipe.rpush(self.queue_name, job_id)
        pipe.zadd(self.enqueue_time_zset, {job_id: now_ts})
        pipe.execute()

    def dequeue(self) -> str | None:
        job_id = self.client.lpop(self.queue_name)
        if job_id:
            self.client.zrem(self.enqueue_time_zset, job_id)
        return job_id

    def enqueue_dead_letter(self, job_id: str) -> None:
        self.client.rpush(self.dead_letter_queue_name, job_id)

    def metrics(self) -> QueueMetrics:
        main_depth = self.client.llen(self.queue_name)
        dlq_depth = self.client.llen(self.dead_letter_queue_name)
        oldest_job_age_seconds = 0
        if main_depth > 0:
            first = self.client.zrange(self.enqueue_time_zset, 0, 0, withscores=True)
            if first:
                oldest_ts = int(first[0][1])
                oldest_job_age_seconds = max(0, int(datetime.now(timezone.utc).timestamp()) - oldest_ts)
        return QueueMetrics(main_depth=main_depth, dlq_depth=dlq_depth, oldest_job_age_seconds=oldest_job_age_seconds)


def build_queue() -> InMemoryQueue | RedisQueue:
    if settings.queue_mode == 'redis' and settings.redis_url:
        try:
            return RedisQueue(settings.redis_url, settings.queue_name, settings.dead_letter_queue_name)
        except Exception:
            pass
    return InMemoryQueue()
