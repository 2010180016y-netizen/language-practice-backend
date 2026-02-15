from fastapi.testclient import TestClient
import pytest

from app.config import settings
from app.db import UserRoleRecord, get_session
from app.main import app, rate_limiter


client = TestClient(app)


@pytest.fixture(autouse=True)
def enable_signup_for_tests():
    original = settings.allow_self_registration
    settings.allow_self_registration = True
    yield
    settings.allow_self_registration = original


def auth_headers(user_id='user_001', password='ChangeMe123!'):
    signup_res = client.post('/auth/signup', json={'user_id': user_id, 'password': password, 'terms_accepted': True})
    assert signup_res.status_code in (200, 409)

    res = client.post('/auth/login', json={'user_id': user_id, 'password': password})
    assert res.status_code == 200
    token = res.json()['access_token']
    refresh_token = res.json()['refresh_token']
    return {'Authorization': f'Bearer {token}'}, refresh_token


def grant_admin(user_id: str) -> None:
    with get_session() as session:
        if not session.get(UserRoleRecord, user_id):
            session.add(UserRoleRecord(user_id=user_id, role='admin'))


def test_auth_required():
    res = client.post('/onboarding/calculate-plan', json={
        'goal_type': 'business',
        'target_language': 'English',
        'minutes_per_day': 10,
    })
    assert res.status_code == 403


def test_calculate_plan_authenticated():
    headers, _ = auth_headers()
    res = client.post('/onboarding/calculate-plan', headers=headers, json={
        'goal_type': 'business',
        'target_language': 'English',
        'minutes_per_day': 10,
    })
    assert res.status_code == 200


def test_refresh_and_logout_revocation():
    headers, refresh = auth_headers('user_logout')
    refreshed = client.post('/auth/refresh', json={'refresh_token': refresh})
    assert refreshed.status_code == 200

    logged_out = client.post('/auth/logout', headers=headers, json={'refresh_token': refresh})
    assert logged_out.status_code == 204

    revoked = client.post('/auth/refresh', json={'refresh_token': refresh})
    assert revoked.status_code == 401


def test_idempotency_for_import_scoped_per_user():
    h1, _ = auth_headers('user_2')
    h2, _ = auth_headers('user_3')
    h1['Idempotency-Key'] = 'same-key'
    h2['Idempotency-Key'] = 'same-key'
    payload = {'channel': 'daily', 'content': 'hello world'}

    first = client.post('/import', headers=h1, json=payload)
    second = client.post('/import', headers=h1, json=payload)
    other_user = client.post('/import', headers=h2, json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert other_user.status_code == 200
    assert first.json()['job_id'] == second.json()['job_id']
    assert first.json()['job_id'] != other_user.json()['job_id']


def test_worker_tick_requires_admin_role_table():
    user_h, _ = auth_headers('user_normal')
    denied = client.post('/admin/worker/tick', headers=user_h)
    assert denied.status_code == 403

    grant_admin('ops_admin')
    admin_h, _ = auth_headers('ops_admin')
    allowed = client.post('/admin/worker/tick', headers=admin_h)
    assert allowed.status_code == 200


def test_queue_metrics_admin_only():
    grant_admin('ops_admin_metrics')
    admin_h, _ = auth_headers('ops_admin_metrics')
    metrics = client.get('/admin/queues/metrics', headers=admin_h)
    assert metrics.status_code == 200


def test_import_list_pagination():
    headers, _ = auth_headers('pager')
    for _ in range(3):
        client.post('/import', headers=headers, json={'channel': 'daily', 'content': 'x'})

    listed = client.get('/imports?offset=0&limit=2', headers=headers)
    assert listed.status_code == 200
    body = listed.json()
    assert body['limit'] == 2
    assert len(body['items']) <= 2


def test_rate_limit_enforced():
    rate_limiter.per_minute = 2
    headers, _ = auth_headers('limit-user')
    payload = {'text': 'maybe later', 'tone_preference': 'business'}

    ok1 = client.post('/chat/analyze', headers=headers, json=payload)
    ok2 = client.post('/chat/analyze', headers=headers, json=payload)
    blocked = client.post('/chat/analyze', headers=headers, json=payload)

    assert ok1.status_code == 200
    assert ok2.status_code == 200
    assert blocked.status_code == 429

    rate_limiter.per_minute = 120
