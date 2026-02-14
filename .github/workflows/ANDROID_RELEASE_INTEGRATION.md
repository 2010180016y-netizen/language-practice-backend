# Android Release Integration (F)

## 1) Retrofit 모델 `openapi.json` 기준 고정 생성

```bash
scripts/android/export_and_generate.sh
```

산출물:
- `openapi.json`
- `android/ApiModels.kt`
- `android/LanguageApiV1.kt`

릴리즈 전 체크:
- 생성 결과를 앱 레포에 커밋
- 서버/앱 모두 같은 OpenAPI 해시 사용

## 2) API 버전 전략 `/v1`

- 서버는 `/v1/*` 경로를 지원하도록 호환 레이어 적용
- 앱 Retrofit은 `/v1` 경로를 사용하도록 고정
- 서버 응답 헤더 `X-API-Version`으로 버전 추적

## 3) 앱 재시도/타임아웃/백오프 표준

권장값(OkHttp):
- connect timeout: 5s
- read timeout: 10s
- write timeout: 10s
- retry: 최대 3회
- exponential backoff: 300ms, 600ms, 1200ms (+ jitter)
- 재시도 대상: 429/503/504 + 네트워크 IO 오류
- 재시도 제외: 400/401/403/404

예시 정책:
- 401 발생 시 refresh 1회 후 원요청 1회 재시도
- idempotent 요청(GET, Idempotency-Key 있는 POST)만 자동 재시도

## 4) 스테이징 E2E 시나리오 검증

출시 전 필수 시나리오:
1. 로그인 → 토큰 갱신 → 로그아웃 → 재갱신 실패(401)
2. import 생성(Idempotency-Key 포함) → worker 처리 → 완료
3. FORCE_FAIL import → retry 후 failed + DLQ 적재 확인
4. `/admin/observability/metrics`에서 p95/오류비율/queue 확인
5. 앱 네트워크 불안정 상황(타임아웃/재시도)에서 UX/데이터 일관성 확인
6. API `/v1` 경로 전수 호출 및 응답 모델 deserialize 확인

합격 기준(예시):
- 치명적 크래시 0
- 인증/토큰 흐름 100% 통과
- 주요 사용자 여정 성공률 99%+
