from fastapi.testclient import TestClient
import pytest

from app.config import settings
from app.db import UserRoleRecord, get_session
from app.main import app


client = TestClient(app)


@pytest.fixture(autouse=True)
def enable_signup_for_tests():
    original = settings.allow_self_registration
    settings.allow_self_registration = True
    yield
    settings.allow_self_registration = original


def auth(user_id: str, password: str = 'ChangeMe123!'):
    signup_res = client.post('/auth/signup', json={'user_id': user_id, 'password': password, 'terms_accepted': True})
    assert signup_res.status_code in (200, 409)

    res = client.post('/auth/login', json={'user_id': user_id, 'password': password})
    assert res.status_code == 200
    return {'Authorization': f"Bearer {res.json()['access_token']}"}


def grant_admin(user_id: str):
    with get_session() as session:
        if not session.get(UserRoleRecord, user_id):
            session.add(UserRoleRecord(user_id=user_id, role='admin'))


def test_api_db_queue_integration_flow():
    user_headers = auth('int_user')
    admin_id = 'int_admin'
    grant_admin(admin_id)
    admin_headers = auth(admin_id)

    create = client.post('/import', headers=user_headers, json={'channel': 'daily', 'content': 'hello'})
    assert create.status_code == 200
    job_id = create.json()['job_id']

    tick = client.post('/admin/worker/tick?max_jobs=10', headers=admin_headers)
    assert tick.status_code == 200

    fetch = client.get(f'/import/{job_id}', headers=user_headers)
    assert fetch.status_code == 200
    assert fetch.json()['status'] in ('queued', 'processing', 'completed')

    metrics = client.get('/admin/queues/metrics', headers=admin_headers)
    assert metrics.status_code == 200
