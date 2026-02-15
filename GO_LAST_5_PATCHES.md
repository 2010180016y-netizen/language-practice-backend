# Go-live Last 5 Patches

1. **실제 인증 도입(기존 user_id-only 제거)**
- `UserLoginRequest`에 `password` 필드 추가
- 서버 측 비밀번호 해시(PBKDF2) 검증
- `user_credentials` 테이블 추가 (Alembic 0005)

2. **PII 보호 강화**
- import 원문 전체 저장 대신
  - `content_sha256`
  - `content_preview_masked`(이메일/전화 마스킹)
- PII 최소 보관 전략 적용

3. **Retrofit 생성기 고도화**
- path/query/body 파라미터 반영
- 200/201/202/204 응답 스키마 우선 처리

4. **성능 리포트 자동화**
- `scripts/load/run_and_report.sh` 추가
- load 결과 텍스트 리포트 자동 저장

5. **Prometheus 메트릭 Exporter**
- `/metrics` endpoint 추가
- latency/error/revoke-hit/worker 지표 export
