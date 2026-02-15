# DB Backup/Restore Rehearsal Runbook

## 목표
- RPO: 15분
- RTO: 60분

## 준비
- `DATABASE_URL` 설정
- 최근 백업 파일 위치 확인

## 백업
```bash
scripts/db/backup.sh
```

## 복구 리허설
1. 임시 DB 준비
2. 복구 실행
```bash
scripts/db/restore.sh <backup.dump>
```
3. 검증
```sql
SELECT count(*) FROM import_jobs;
SELECT count(*) FROM revoked_tokens;
```

## 합격 기준
- 복구 완료 시간 60분 이내
- 데이터 손실 15분 이내
