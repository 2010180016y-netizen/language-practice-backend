from __future__ import annotations

import json
from urllib import request

from app.config import settings
from app.observability import app_logger


class AlertClient:
    def __init__(self, slack_webhook: str | None, pagerduty_url: str | None):
        self.slack_webhook = slack_webhook
        self.pagerduty_url = pagerduty_url

    def _post_json(self, url: str, payload: dict) -> None:
        body = json.dumps(payload).encode('utf-8')
        req = request.Request(url, data=body, headers={'Content-Type': 'application/json'})
        with request.urlopen(req, timeout=3):
            pass

    def notify_error(self, title: str, detail: str) -> None:
        if self.slack_webhook:
            try:
                self._post_json(self.slack_webhook, {'text': f'[{title}] {detail}'})
            except Exception as exc:
                app_logger.warning('slack alert failed', extra={'message': str(exc)})
        if self.pagerduty_url:
            try:
                self._post_json(self.pagerduty_url, {'event_action': 'trigger', 'payload': {'summary': title, 'source': 'backend', 'severity': 'error', 'custom_details': {'detail': detail}}})
            except Exception as exc:
                app_logger.warning('pagerduty alert failed', extra={'message': str(exc)})


alerts = AlertClient(settings.slack_webhook_url, settings.pagerduty_events_url)
