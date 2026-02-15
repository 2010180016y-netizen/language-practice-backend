EXPLAIN ANALYZE
SELECT job_id, status, progress_percent, created_at
FROM import_jobs
WHERE user_id = 'user_001'
ORDER BY created_at DESC
LIMIT 20 OFFSET 0;

EXPLAIN ANALYZE
SELECT count(*)
FROM import_jobs
WHERE user_id = 'user_001';
