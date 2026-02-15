from datetime import datetime, timezone
import hashlib
import re
from functools import lru_cache
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import create_engine, func, select, text

from app.alerts import alerts
from app.config import settings
from app.db import (
    IdempotencyRecord,
    ImportJobRecord,
    RevokedTokenRecord,
    UserRoleRecord,
    UserCredentialRecord,
    get_session,
    init_db,
)
from app.observability import app_logger, metrics, now_ms
from app.queue import build_queue
from app.rate_limit import build_rate_limiter
from app.schemas import (
    CalculatedPlan,
    ChatAlternative,
    ChatAnalyzeRequest,
    ChatAnalyzeResponse,
    HealthResponse,
    ImportJob,
    ImportListResponse,
    ImportRequest,
    LogoutRequest,
    OnboardingGoal,
    QueueMetricsResponse,
    ReadyResponse,
    RefreshTokenRequest,
    TokenPair,
    UserLoginRequest,
    UserSignupRequest,
)
from app.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.worker import process_batch

try:
    import sentry_sdk
except Exception:  # pragma: no cover
    sentry_sdk = None

app = FastAPI(title=settings.app_name, version=settings.app_version)
security = HTTPBearer(auto_error=True)
rate_limiter = build_rate_limiter()
queue = build_queue()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_allow_origins.split(',') if origin.strip()],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _is_secure_request(request: Request) -> bool:
    proto = request.headers.get('X-Forwarded-Proto', request.url.scheme)
    return proto == 'https'


@app.middleware('http')
async def observability_and_security_middleware(request: Request, call_next):
    start = now_ms()
    request_id = request.headers.get('X-Request-ID', str(uuid4()))

    api_version = 'unversioned'
    if request.scope.get('path', '').startswith('/v1/'):
        request.scope['path'] = request.scope['path'][3:]
        api_version = 'v1'

    if settings.enforce_https and not _is_secure_request(request) and request.url.path not in ('/health', '/ready', '/v1/health', '/v1/ready'):
        latency = now_ms() - start
        metrics.record_request(latency, 400)
        app_logger.warning(
            'https required',
            extra={'request_id': request_id, 'path': request.url.path, 'method': request.method, 'status_code': 400, 'latency_ms': round(latency, 2)},
        )
        raise HTTPException(status_code=400, detail='https required')

    try:
        response = await call_next(request)
    except Exception as exc:
        latency = now_ms() - start
        metrics.record_request(latency, 500)
        app_logger.error(
            'request failed',
            extra={'request_id': request_id, 'path': request.url.path, 'method': request.method, 'status_code': 500, 'latency_ms': round(latency, 2)},
        )
        alerts.notify_error('api_exception', f'path={request.url.path} request_id={request_id} error={exc}')
        raise

    latency = now_ms() - start
    metrics.record_request(latency, response.status_code)
    app_logger.info(
        'request completed',
        extra={
            'request_id': request_id,
            'path': request.url.path,
            'method': request.method,
            'status_code': response.status_code,
            'latency_ms': round(latency, 2),
        },
    )

    response.headers['X-Request-ID'] = request_id
    response.headers['X-API-Version'] = api_version
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Cache-Control'] = 'no-store'
    if settings.hsts_enabled:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
    return response


@app.on_event('startup')
def startup() -> None:
    if len(settings.jwt_secret) < 32:
        raise RuntimeError('JWT_SECRET is not secure enough for runtime use')
    init_db()
    if settings.sentry_dsn and sentry_sdk is not None:
        sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.2)


def is_token_revoked(jti: str) -> bool:
    with get_session() as session:
        return session.get(RevokedTokenRecord, jti) is not None


def revoke_token(jti: str, user_id: str, token_type: str, exp: datetime) -> None:
    with get_session() as session:
        if not session.get(RevokedTokenRecord, jti):
            session.add(RevokedTokenRecord(jti=jti, user_id=user_id, token_type=token_type, expires_at=exp))


def cleanup_expired_revoked_tokens() -> int:
    now = utc_now()
    with get_session() as session:
        rows = session.execute(select(RevokedTokenRecord).where(RevokedTokenRecord.expires_at < now)).scalars().all()
        count = len(rows)
        for row in rows:
            session.delete(row)
    return count


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    try:
        payload = decode_token(credentials.credentials, expected_type='access')
    except Exception as exc:
        raise HTTPException(status_code=401, detail='invalid access token') from exc

    if is_token_revoked(payload['jti']):
        raise HTTPException(status_code=401, detail='token revoked')

    return payload['sub']


def get_admin_user(user_id: str = Depends(get_current_user)) -> str:
    with get_session() as session:
        role = session.get(UserRoleRecord, user_id)
    if not role or role.role != 'admin':
        raise HTTPException(status_code=403, detail='admin required')
    return user_id


def enforce_rate_limit(request: Request, user_id: str | None = None) -> None:
    key = user_id or request.client.host if request.client else 'anonymous'
    if not rate_limiter.allow(key):
        raise HTTPException(status_code=429, detail='rate limit exceeded')


def scoped_idempotency_key(user_id: str, key: str) -> str:
    return f'{user_id}:{key}'


@app.get('/health', response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status='ok', version=settings.app_version)


@app.get('/ready', response_model=ReadyResponse)
def readiness_check() -> ReadyResponse:
    db = 'ok'
    redis = 'ok'

    try:
        with get_session() as session:
            session.execute(select(ImportJobRecord).limit(1))
    except Exception:
        db = 'error'

    if settings.redis_url:
        try:
            _ = rate_limiter.allow('readiness_probe')
        except Exception:
            redis = 'error'
    else:
        redis = 'not_configured'

    status = 'ready' if db == 'ok' and redis in ('ok', 'not_configured') else 'degraded'
    return ReadyResponse(status=status, db=db, redis=redis)


@app.get('/admin/observability/metrics')
def observability_metrics(_: str = Depends(get_admin_user)) -> dict:
    queue_m = queue.metrics()
    snapshot = metrics.snapshot()
    snapshot['queue'] = {
        'depth': queue_m.main_depth,
        'dlq_depth': queue_m.dlq_depth,
        'oldest_job_age_seconds': queue_m.oldest_job_age_seconds,
    }
    snapshot['slo'] = {
        'availability_target_percent': settings.slo_availability_target,
        'p95_latency_target_ms': settings.slo_p95_latency_ms,
    }
    return snapshot




def _mask_pii(text: str) -> str:
    # email
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+", "[EMAIL]", text)
    # phone variants
    text = re.sub(r"\b(?:\+?\d{1,3}[ -]?)?(?:\d{2,4}[ -]?)?\d{3,4}[ -]?\d{4}\b", "[PHONE]", text)
    # possible account number and resident-id like patterns
    text = re.sub(r"\b\d{6}-?\d{7}\b", "[NATIONAL_ID]", text)
    text = re.sub(r"\b\d{2,6}-\d{2,6}-\d{2,6}\b", "[ACCOUNT]", text)
    # rough address masking (Korean road names)
    text = re.sub(r"[가-힣0-9\- ]{2,}(로|길|동|구|시)\s*\d+(-\d+)?", "[ADDRESS]", text)
    return text[:500]


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

@app.get('/metrics')
def prometheus_metrics() -> Response:
    return Response(content=metrics.to_prometheus(), media_type='text/plain; version=0.0.4')


@app.post('/auth/signup', response_model=TokenPair)
def signup(req: UserSignupRequest) -> TokenPair:
    if not settings.allow_self_registration:
        raise HTTPException(status_code=403, detail='self registration disabled')
    if not req.terms_accepted:
        raise HTTPException(status_code=400, detail='terms must be accepted')
    if not re.search(r'[A-Z]', req.password) or not re.search(r'[a-z]', req.password) or not re.search(r'\d', req.password):
        raise HTTPException(status_code=400, detail='password must include upper/lowercase and number')

    with get_session() as session:
        existing = session.get(UserCredentialRecord, req.user_id)
        if existing:
            raise HTTPException(status_code=409, detail='user already exists')
        session.add(UserCredentialRecord(user_id=req.user_id, password_hash=hash_password(req.password)))

    return TokenPair(
        access_token=create_access_token(req.user_id),
        refresh_token=create_refresh_token(req.user_id),
    )


@app.post('/auth/login', response_model=TokenPair)
def login(req: UserLoginRequest) -> TokenPair:
    with get_session() as session:
        cred = session.get(UserCredentialRecord, req.user_id)
    if not cred or not verify_password(req.password, cred.password_hash):
        raise HTTPException(status_code=401, detail='invalid credentials')
    return TokenPair(
        access_token=create_access_token(req.user_id),
        refresh_token=create_refresh_token(req.user_id),
    )


@app.post('/auth/refresh', response_model=TokenPair)
def refresh(req: RefreshTokenRequest) -> TokenPair:
    try:
        payload = decode_token(req.refresh_token, expected_type='refresh')
    except Exception as exc:
        raise HTTPException(status_code=401, detail='invalid refresh token') from exc

    if is_token_revoked(payload['jti']):
        metrics.record_refresh_revoke_hit()
        raise HTTPException(status_code=401, detail='token revoked')

    revoke_token(payload['jti'], payload['sub'], 'refresh', datetime.fromtimestamp(payload['exp'], tz=timezone.utc))

    user_id = payload['sub']
    return TokenPair(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@app.post('/auth/logout', status_code=204)
def logout(req: LogoutRequest, _: str = Depends(get_current_user)) -> Response:
    try:
        payload = decode_token(req.refresh_token, expected_type='refresh')
    except Exception as exc:
        raise HTTPException(status_code=401, detail='invalid refresh token') from exc

    revoke_token(payload['jti'], payload['sub'], 'refresh', datetime.fromtimestamp(payload['exp'], tz=timezone.utc))
    return Response(status_code=204)


@app.post('/onboarding/calculate-plan', response_model=CalculatedPlan)
def calculate_onboarding_plan(goal: OnboardingGoal, request: Request, user_id: str = Depends(get_current_user)) -> CalculatedPlan:
    enforce_rate_limit(request, user_id)

    words_count = max(4, int(goal.minutes_per_day * 0.8))
    sentences_count = max(2, int(goal.minutes_per_day * 0.3))
    chat_turns = max(2, int(goal.minutes_per_day * 0.25))

    return CalculatedPlan(
        minutes_per_day=goal.minutes_per_day,
        words_count=words_count,
        sentences_count=sentences_count,
        chat_turns=chat_turns,
        plan_preview=f"{goal.minutes_per_day} min/day → {words_count} words + {sentences_count} sentences + {chat_turns} chat turns",
    )


@lru_cache(maxsize=256)
def cached_chat_alternatives(text: str, tone_preference: str) -> tuple[tuple[str, str], ...]:
    _ = text
    if tone_preference == 'business':
        return (
            ('business', 'Could we revisit this tomorrow?'),
            ('business', 'Let me review this and get back to you.'),
            ('natural', 'I am tied up right now, can we reschedule?'),
        )

    return (
        ('daily', 'Can we do this a bit later?'),
        ('daily', 'I am swamped right now.'),
        ('natural', 'Let us pick this up tomorrow.'),
    )


@app.post('/chat/analyze', response_model=ChatAnalyzeResponse)
def analyze_chat_input(payload: ChatAnalyzeRequest, request: Request, user_id: str = Depends(get_current_user)) -> ChatAnalyzeResponse:
    enforce_rate_limit(request, user_id)
    text = payload.text.strip()
    alts = [ChatAlternative(category=c, text=t) for c, t in cached_chat_alternatives(text, payload.tone_preference)]
    return ChatAnalyzeResponse(original=text, alternatives=alts)


@app.post('/import', response_model=ImportJob)
def create_import_job(
    request_payload: ImportRequest,
    request: Request,
    x_idempotency_key: str | None = Header(default=None, alias='Idempotency-Key'),
    user_id: str = Depends(get_current_user),
) -> ImportJob:
    enforce_rate_limit(request, user_id)

    raw_key = request_payload.idempotency_key or x_idempotency_key
    key = scoped_idempotency_key(user_id, raw_key) if raw_key else None

    with get_session() as session:
        if key:
            existing = session.get(IdempotencyRecord, key)
            if existing:
                existing_job = session.get(ImportJobRecord, existing.job_id)
                if not existing_job:
                    raise HTTPException(status_code=500, detail='idempotency record is stale')
                return ImportJob(
                    job_id=existing_job.job_id,
                    status=existing_job.status,
                    progress_percent=existing_job.progress_percent,
                    created_at=existing_job.created_at,
                )

        job_id = str(uuid4())
        created_at = utc_now()
        record = ImportJobRecord(
            job_id=job_id,
            user_id=user_id,
            status='queued',
            progress_percent=0,
            attempts=0,
            channel=request_payload.channel,
            content_sha256=_sha256_text(request_payload.content),
            content_preview_masked=_mask_pii(request_payload.content),
            last_error=None,
            created_at=created_at,
            updated_at=created_at,
        )
        session.add(record)

        if key:
            session.add(IdempotencyRecord(key=key, user_id=user_id, job_id=job_id))

    queue.enqueue(job_id)

    return ImportJob(job_id=job_id, status='queued', progress_percent=0, created_at=created_at)


@app.get('/import/{job_id}', response_model=ImportJob)
def get_import_job(job_id: str, request: Request, user_id: str = Depends(get_current_user)) -> ImportJob:
    enforce_rate_limit(request, user_id)
    with get_session() as session:
        rec = session.get(ImportJobRecord, job_id)
        if not rec:
            raise HTTPException(status_code=404, detail='import job not found')
        if rec.user_id != user_id:
            raise HTTPException(status_code=403, detail='forbidden')
        return ImportJob(
            job_id=rec.job_id,
            status=rec.status,
            progress_percent=rec.progress_percent,
            created_at=rec.created_at,
        )


@app.get('/admin/queues/metrics', response_model=QueueMetricsResponse)
def queue_metrics(_: str = Depends(get_admin_user)) -> QueueMetricsResponse:
    queue_data = queue.metrics()
    alert = queue_data.main_depth > settings.queue_depth_alert_threshold
    if alert:
        alerts.notify_error('queue_backlog_alert', f'depth={queue_data.main_depth}')
    return QueueMetricsResponse(
        main_depth=queue_data.main_depth,
        dlq_depth=queue_data.dlq_depth,
        oldest_job_age_seconds=queue_data.oldest_job_age_seconds,
        alert=alert,
    )


@app.post('/admin/worker/tick')
def worker_tick(
    max_jobs: int = Query(default=20, ge=1, le=200),
    _: str = Depends(get_admin_user),
) -> dict[str, list[str]]:
    return {'processed_job_ids': process_batch(max_jobs=max_jobs)}


@app.post('/admin/tokens/cleanup')
def cleanup_tokens(_: str = Depends(get_admin_user)) -> dict[str, int]:
    deleted = cleanup_expired_revoked_tokens()
    return {'deleted': deleted}


@app.post('/admin/db/verify-production')
def verify_production_db(_: str = Depends(get_admin_user)) -> dict[str, str]:
    if not settings.production_database_url:
        raise HTTPException(status_code=400, detail='production_database_url not configured')

    engine = create_engine(settings.production_database_url, future=True)
    with engine.connect() as conn:
        conn.execute(text('SELECT 1'))
    return {'status': 'ok'}



@app.delete('/me/data', status_code=204)
def delete_my_data(user_id: str = Depends(get_current_user)) -> Response:
    with get_session() as session:
        for rec in session.execute(select(ImportJobRecord).where(ImportJobRecord.user_id == user_id)).scalars().all():
            session.delete(rec)
        for rec in session.execute(select(IdempotencyRecord).where(IdempotencyRecord.user_id == user_id)).scalars().all():
            session.delete(rec)
        for rec in session.execute(select(RevokedTokenRecord).where(RevokedTokenRecord.user_id == user_id)).scalars().all():
            session.delete(rec)
        role = session.get(UserRoleRecord, user_id)
        if role:
            session.delete(role)
        cred = session.get(UserCredentialRecord, user_id)
        if cred:
            session.delete(cred)
    return Response(status_code=204)


@app.get('/imports', response_model=ImportListResponse)
def list_my_imports(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    user_id: str = Depends(get_current_user),
) -> ImportListResponse:
    with get_session() as session:
        query = select(ImportJobRecord).where(ImportJobRecord.user_id == user_id).order_by(ImportJobRecord.created_at.desc())
        rows = session.execute(query.offset(offset).limit(limit)).scalars().all()
        total = session.execute(
            select(func.count()).select_from(ImportJobRecord).where(ImportJobRecord.user_id == user_id)
        ).scalar_one()

    items = [
        ImportJob(
            job_id=r.job_id,
            status=r.status,
            progress_percent=r.progress_percent,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return ImportListResponse(items=items, total=total, offset=offset, limit=limit)
