# Observability & SLO

## Structured logging
- JSON logs with request_id/path/method/status/latency
- Correlated with `X-Request-ID`

## Core metrics
- p50/p95 latency
- 4xx/5xx ratio
- queue depth / DLQ depth / oldest job age
- refresh revoke hit rate
- worker job p50/p95 latency

## Error tracking + alerting
- Sentry via `SENTRY_DSN`
- Slack webhook via `SLACK_WEBHOOK_URL`
- PagerDuty events via `PAGERDUTY_EVENTS_URL`

## SLO
- Availability target: 99.9%
- p95 latency target: 300ms

## Dashboard
- Template: `infra/grafana/slo_dashboard.json`
