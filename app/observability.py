from __future__ import annotations

import json
import logging
import statistics
import time
from collections import Counter, deque
from dataclasses import dataclass


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'time': self.formatTime(record, self.datefmt),
        }
        for key in ('request_id', 'path', 'method', 'status_code', 'latency_ms'):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> logging.Logger:
    logger = logging.getLogger('app')
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    return logger


@dataclass
class LatencyStats:
    p50_ms: float
    p95_ms: float


class MetricsStore:
    def __init__(self, max_samples: int = 5000):
        self._latencies = deque(maxlen=max_samples)
        self._status = Counter()
        self._refresh_revoke_hits = 0
        self._worker_job_durations = deque(maxlen=max_samples)

    def record_request(self, latency_ms: float, status_code: int) -> None:
        self._latencies.append(latency_ms)
        bucket = f'{status_code // 100}xx'
        self._status[bucket] += 1

    def record_refresh_revoke_hit(self) -> None:
        self._refresh_revoke_hits += 1

    def record_worker_duration(self, ms: float) -> None:
        self._worker_job_durations.append(ms)

    def latency_stats(self) -> LatencyStats:
        if not self._latencies:
            return LatencyStats(0.0, 0.0)
        values = sorted(self._latencies)
        p50 = statistics.median(values)
        p95_index = max(0, min(len(values) - 1, int(len(values) * 0.95) - 1))
        p95 = values[p95_index]
        return LatencyStats(round(p50, 2), round(p95, 2))

    def worker_latency_stats(self) -> LatencyStats:
        if not self._worker_job_durations:
            return LatencyStats(0.0, 0.0)
        values = sorted(self._worker_job_durations)
        p50 = statistics.median(values)
        p95_index = max(0, min(len(values) - 1, int(len(values) * 0.95) - 1))
        p95 = values[p95_index]
        return LatencyStats(round(p50, 2), round(p95, 2))

    def snapshot(self) -> dict:
        request_stats = self.latency_stats()
        worker_stats = self.worker_latency_stats()
        total = sum(self._status.values())
        return {
            'request_latency_ms': {'p50': request_stats.p50_ms, 'p95': request_stats.p95_ms},
            'worker_job_latency_ms': {'p50': worker_stats.p50_ms, 'p95': worker_stats.p95_ms},
            'status_ratio': {
                '2xx': self._status['2xx'] / total if total else 0.0,
                '4xx': self._status['4xx'] / total if total else 0.0,
                '5xx': self._status['5xx'] / total if total else 0.0,
            },
            'refresh_revoke_hit_rate': self._refresh_revoke_hits / total if total else 0.0,
        }

    def to_prometheus(self) -> str:
        snap = self.snapshot()
        lines = [
            '# TYPE app_request_latency_p50_ms gauge',
            f"app_request_latency_p50_ms {snap['request_latency_ms']['p50']}",
            '# TYPE app_request_latency_p95_ms gauge',
            f"app_request_latency_p95_ms {snap['request_latency_ms']['p95']}",
            '# TYPE app_worker_latency_p95_ms gauge',
            f"app_worker_latency_p95_ms {snap['worker_job_latency_ms']['p95']}",
            '# TYPE app_status_ratio gauge',
            f"app_status_ratio{{code=\"2xx\"}} {snap['status_ratio']['2xx']}",
            f"app_status_ratio{{code=\"4xx\"}} {snap['status_ratio']['4xx']}",
            f"app_status_ratio{{code=\"5xx\"}} {snap['status_ratio']['5xx']}",
            '# TYPE app_refresh_revoke_hit_rate gauge',
            f"app_refresh_revoke_hit_rate {snap['refresh_revoke_hit_rate']}",
        ]
        return '\n'.join(lines) + '\n'


metrics = MetricsStore()
app_logger = configure_logging()


def now_ms() -> float:
    return time.perf_counter() * 1000
