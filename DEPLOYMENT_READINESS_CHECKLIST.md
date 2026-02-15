# Deployment Readiness Checklist (Before Launch)

질문: **"지금 바로 배포만 하면 되나?"**

짧은 답: **아직 아닙니다.**
현재 코드는 좋은 베이스라인이지만, 운영 배포 전에 반드시 거쳐야 할 프로세스가 남아 있습니다.

---

## 1) 지금 이미 준비된 것 (Good)

- 인증 기본 흐름: login / refresh / logout + refresh revoke
- import 작업의 DB 영속화 + idempotency
- Redis 기반 rate limit/queue fallback 구조
- worker 분리 실행 구조
- Alembic 마이그레이션 기반 스키마 관리
- readiness endpoint, pagination, 기본 테스트

---

## 2) 배포 전에 **반드시** 추가해야 하는 것 (Must-have)

## A. 시크릿/보안 운영화

1. `JWT_SECRET`를 강한 랜덤값으로 교체 (환경변수/Secret Manager 사용)
2. CORS를 `*`에서 실제 앱 도메인으로 제한
3. TLS(HTTPS) 강제 + HSTS 적용 (Ingress/API Gateway)
4. `admin_` 접두사 기반 관리자 권한 대신, 역할(Role) 테이블 + RBAC로 교체
5. 토큰 폐기 테이블 정리 정책(cron/worker) 추가 (만료된 revoke 레코드 삭제)

## B. 데이터/마이그레이션 안전성

1. 프로덕션 DB(PostgreSQL)로 실제 연결 검증
2. `alembic upgrade head`를 CI/CD 단계에 고정
3. DB 백업/복구 리허설 (RPO/RTO 합의)
4. 인덱스 점검: 사용자별 조회/최신순 조회 쿼리의 실행계획 확인

## C. 비동기 처리 안정화

1. worker 실패 재시도(backoff) + dead-letter queue 추가
2. queue 적체 모니터링(길이, 처리지연) 알람
3. 작업 상태 전이(queued/processing/completed/failed)에서 `failed` 경로 추가
4. worker를 `/admin/worker/tick` 수동 호출이 아니라 별도 프로세스(supervisor/K8s Deployment)로 운영

## D. 관측성(Observability)

1. 구조화 로그(JSON) + `X-Request-ID` 연계
2. 핵심 메트릭 수집
   - p50/p95 latency
   - 4xx/5xx 비율
   - queue depth / job 처리시간
   - refresh revoke hit rate
3. 에러 트래킹(Sentry) + 알람 채널(Slack/PagerDuty)
4. 대시보드(Grafana)와 SLO(가용성/지연) 정의

## E. 테스트/검증 게이트

1. 현재 컴파일 테스트 외에 실제 의존성 설치 환경에서 `pytest` 통과
2. 통합 테스트 (API + DB + Redis + worker)
3. 부하 테스트 (목표 동접/트래픽 시나리오)
4. 보안 테스트
   - 인증 우회
   - 토큰 재사용
   - rate limit 우회
   - idempotency 충돌

## F. Android 릴리즈 연동

1. Retrofit 모델을 `openapi.json` 기준으로 고정 생성
2. API 버전 전략(`/v1`) 도입
3. 앱에서 재시도 정책/타임아웃/백오프 표준화
4. 앱 배포 전 스테이징 환경에서 E2E 시나리오 검증

---

## 3) 바로 실행할 권장 순서 (실무용)

1. **스테이징 환경 구성**: API + PostgreSQL + Redis + worker + TLS
2. **마이그레이션/시크릿 적용**: alembic + Secret Manager
3. **관측성 붙이기**: 로그/메트릭/알람
4. **통합/부하 테스트**: 병목 확인 후 튜닝
5. **릴리즈 캔리(소량 배포)**: 오류율/지연 확인
6. **전체 배포**

---

## 4) 현재 코드 기준 "빠진 부분" 한눈에 보기

- 운영 관측성(메트릭/알람/Sentry) 미연동
- 의존성 설치 환경에서 자동 테스트 미검증(현재 실행환경 제약)
- 본격 트래픽(예: 대규모 동접) 기준의 부하테스트 결과 부재

---

## 5) 결론

**"지금 바로 프로덕션 배포"는 권장하지 않습니다.**

다만 현재는 **좋은 Pre-Production 상태**입니다.
위 Must-have를 완료하면, Android 앱과 함께 안정적으로 런칭 가능한 수준으로 올라갑니다.


## Update (Implemented in codebase)
- [x] JWT secret minimum policy + startup validation
- [x] CORS default narrowed from wildcard
- [x] HTTPS enforcement + HSTS response header support
- [x] RBAC table (`user_roles`) + admin guard based on role
- [x] Revoked token cleanup endpoint for cron/worker integration

- [x] Production DB verify endpoint/script added
- [x] CI workflow now runs `alembic upgrade head` before tests
- [x] Backup/restore rehearsal scripts added
- [x] Query-plan check SQL added for index verification
- [x] Worker retry/backoff + DLQ implemented
- [x] Queue metrics endpoint for backlog monitoring added
- [x] Import jobs now include failed status path
- [x] Worker now runs as separate process in compose

- [x] Structured JSON logging with request-id correlation added
- [x] Core metrics endpoint added (latency, error ratio, queue, revoke hit rate)
- [x] Sentry + Slack/PagerDuty integration hooks added
- [x] SLO doc and Grafana dashboard template added
- [x] CI now installs deps and runs pytest + integration + security suites
- [x] Load smoke test gate added with Locust in CI
- [x] Security test suite added for bypass/reuse/rate-limit/idempotency

- [x] API /v1 versioning compatibility layer added
- [x] OpenAPI->Retrofit generation scripts added
- [x] Android retry/timeout/backoff standard documented
- [x] Staging E2E scenarios documented for Android release

- [x] Password-based auth with hashed credential verification added
- [x] PII-minimized import storage (hash + masked preview) added
- [x] Retrofit generator improved for path/query/body params
- [x] Load report automation script added
- [x] Prometheus /metrics exporter added
