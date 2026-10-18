-- Optional independent-of-GitHub watchdog. Review/apply only in the intended project
-- after enabling the free Supabase Cron extension. No external delivery or data deletion.
-- The dashboard reads this persistent degraded state; GitHub failure notifications
-- additionally report its separate hourly watchdog job. Neither is an uptime guarantee.
SELECT cron.schedule('flymind-stale-heartbeat','*/5 * * * *',$$
 UPDATE public.flymind_health SET status=CASE WHEN last_attempt<now()-interval '90 minutes' THEN 'failed' ELSE 'delayed' END,
 error_code='scanner_heartbeat_stale'
 WHERE last_attempt<now()-interval '30 minutes';
$$);
-- Rollback: SELECT cron.unschedule('flymind-stale-heartbeat');
