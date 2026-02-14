# Load Test Plan

## Target
- 동시 사용자: 1,000 (스테이징), 단계적으로 10,000+ 확장
- p95 API latency < 300ms
- 5xx rate < 0.5%

## Run
```bash
locust -f scripts/load/locustfile.py --host http://localhost:8000
```

## Observe
- `/admin/observability/metrics`
- `/admin/queues/metrics`
- DB CPU / Redis memory / queue depth
