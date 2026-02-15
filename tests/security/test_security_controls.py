from fastapi.testclient import TestClient
import pytest

from app.config import settings
from app.main import app, rate_limiter


client = TestClient(app)


@pytest.fixture(autouse=True)
def enable_signup_for_tests():
    original = settings.allow_self_registration
    settings.allow_self_registration = True
    yield
    settings.allow_self_registration = original


def auth(user_id='sec_user', password='ChangeMe123!'):
    signup_res = client.post('/auth/signup', json={'user_id': user_id, 'password': password, 'terms_accepted': True})
    assert signup_res.status_code in (200, 409)

    res = client.post('/auth/login', json={'user_id': user_id, 'password': password})
    assert res.status_code == 200
    return {'Authorization': f"Bearer {res.json()['access_token']}"}, res.json()['refresh_token']


def test_refresh_token_reuse_blocked():
    headers, refresh = auth('sec_reuse')
    first = client.post('/auth/refresh', json={'refresh_token': refresh})
    assert first.status_code == 200
    second = client.post('/auth/refresh', json={'refresh_token': refresh})
    assert second.status_code == 401


def test_rate_limit_bypass_attempt_blocked():
    rate_limiter.per_minute = 1
    headers, _ = auth('sec_limit')
    payload = {'text': 'hello', 'tone_preference': 'business'}
    ok = client.post('/chat/analyze', headers=headers, json=payload)
    blocked = client.post('/chat/analyze', headers=headers, json=payload)
    assert ok.status_code == 200
    assert blocked.status_code == 429
    rate_limiter.per_minute = 120


def test_auth_bypass_blocked():
    res = client.get('/imports')
    assert res.status_code in (401, 403)


def test_idempotency_collision_not_cross_user():
    h1, _ = auth('sec_user1')
    h2, _ = auth('sec_user2')
    h1['Idempotency-Key'] = 'shared-key'
    h2['Idempotency-Key'] = 'shared-key'
    payload = {'channel': 'daily', 'content': 'abc'}
    r1 = client.post('/import', headers=h1, json=payload)
    r2 = client.post('/import', headers=h2, json=payload)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()['job_id'] != r2.json()['job_id']
