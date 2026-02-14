from __future__ import annotations

import time
from datetime import datetime, timezone

from app.alerts import alerts
from app.config import settings
from app.db import ImportJobRecord, get_session
from app.observability import app_logger, metrics, now_ms
from app.queue import build_queue

queue = build_queue()


def _process_job_payload(job: ImportJobRecord) -> None:
    if 'FORCE_FAIL' in job.content:
        raise RuntimeError('forced processing failure')


def process_next_job() -> str | None:
    start = now_ms()
    job_id = queue.dequeue()
    if not job_id:
        return None

    with get_session() as session:
        job = session.get(ImportJobRecord, job_id)
        if not job:
            return None

        job.status = 'processing'
        job.updated_at = datetime.now(timezone.utc)

        try:
            _process_job_payload(job)
            next_progress = min(job.progress_percent + 25, 100)
            job.progress_percent = next_progress
            job.status = 'completed' if next_progress == 100 else 'queued'
            job.last_error = None
            job.updated_at = datetime.now(timezone.utc)
            if next_progress < 100:
                queue.enqueue(job_id)
        except Exception as exc:
            job.attempts += 1
            job.last_error = str(exc)
            job.updated_at = datetime.now(timezone.utc)

            if job.attempts < settings.max_job_retries:
                backoff_s = settings.backoff_base_seconds ** job.attempts
                job.status = 'queued'
                time.sleep(min(backoff_s, 5))
                queue.enqueue(job_id)
            else:
                job.status = 'failed'
                queue.enqueue_dead_letter(job_id)
                alerts.notify_error('worker_job_failed', f'job_id={job_id} error={exc}')

    duration = now_ms() - start
    metrics.record_worker_duration(duration)
    app_logger.info('worker job processed', extra={'job_id': job_id, 'latency_ms': round(duration, 2)})
    return job_id


def process_batch(max_jobs: int = 50) -> list[str]:
    processed: list[str] = []
    for _ in range(max_jobs):
        job_id = process_next_job()
        if not job_id:
            break
        processed.append(job_id)
    return processed


def worker_forever(poll_interval_seconds: int = 1) -> None:
    while True:
        processed = process_batch(max_jobs=100)
        if not processed:
            time.sleep(max(1, poll_interval_seconds))
