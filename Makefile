.PHONY: test openapi migrate verify-db test-integration test-security load-smoke android-generate load-report bootstrap-admin

test:
	pytest -q

test-integration:
	pytest -q tests/integration

test-security:
	pytest -q tests/security

openapi:
	python scripts/export_openapi.py

migrate:
	alembic upgrade head

verify-db:
	python scripts/verify_db_connection.py

load-smoke:
	locust -f scripts/load/locustfile.py --host http://localhost:8000 --headless -u 10 -r 2 -t 30s --only-summary

load-report:
	scripts/load/run_and_report.sh http://localhost:8000 load_test_report.txt

android-generate:
	scripts/android/export_and_generate.sh

bootstrap-admin:
	python scripts/bootstrap_admin.py --user-id $(USER_ID) --password $(PASSWORD) --role $${ROLE-admin}
