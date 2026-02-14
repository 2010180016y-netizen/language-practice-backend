# Language Practice Backend (Android-first)

최근 Go-live 직전 보강(마지막 5개 패치)까지 반영했습니다.

## Go 전 마지막 5개 패치
1. 실제 인증 도입 (password + PBKDF2 hash 검증)
2. PII 보호 (import 원문 최소 보관: hash + masked preview)
3. OpenAPI→Retrofit 생성기 고도화 (path/query/body 반영)
4. 부하 테스트 리포트 자동화 (`scripts/load/run_and_report.sh`)
5. Prometheus `/metrics` exporter 추가

세부: `GO_LAST_5_PATCHES.md`

## D/E/F 포함 상태
- D 관측성: JSON 로그, request-id, Sentry/알람 훅, SLO 대시보드 템플릿
- E 테스트 게이트: CI migrate+pytest+load smoke, 통합/보안 테스트
- F Android 연동: `/v1` 전략, OpenAPI→Retrofit 생성, 네트워크 정책/E2E 문서

## 실행
```bash
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 첫 배포(초보자용) - 꼭 이 순서대로
기본값에서는 `ALLOW_SELF_REGISTRATION=false`라서 회원가입이 막혀 있습니다.
즉, **첫 관리자 계정은 수동 부트스트랩**이 필요합니다.

1. 의존성 설치
```bash
pip install -r requirements.txt
```

2. DB 마이그레이션
```bash
alembic upgrade head
```

3. DB 연결 확인
```bash
python scripts/verify_db_connection.py
```

4. 첫 관리자 계정 생성(자동화 스크립트)
```bash
python scripts/bootstrap_admin.py --user-id admin_001 --password '강한비밀번호123A' --role admin
```

5. 서버 실행
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

6. 로그인 확인
```bash
curl -s -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"admin_001","password":"강한비밀번호123A"}'
```

7. 테스트 게이트 실행
```bash
pytest -q tests tests/integration tests/security
```

8. 로드 스모크 테스트
```bash
scripts/load/run_and_report.sh http://localhost:8000 load_test_report.txt
```

## 테스트
```bash
pytest -q
pytest -q tests/integration tests/security
```

## OpenAPI + Android 생성
```bash
scripts/android/export_and_generate.sh
```

## Load report
```bash
scripts/load/run_and_report.sh http://localhost:8000 load_test_report.txt
```
