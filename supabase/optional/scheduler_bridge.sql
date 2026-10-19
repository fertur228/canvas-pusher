-- Operator-only, reviewed project irjasmzytjeohwfpdnrl. Apply AFTER migration 0008.
-- Does not start the timer. Keep Edge DRY_RUN=true until cloud dry-run is verified.
-- Install FLYMIND_SCHEDULE_SECRET securely in Edge and Vault beforehand; never inline it here.
BEGIN;
CREATE EXTENSION IF NOT EXISTS pg_cron;
CREATE EXTENSION IF NOT EXISTS pg_net;
REVOKE USAGE ON SCHEMA cron FROM PUBLIC,anon,authenticated;
-- Hosted pg_net is provider-owned and retains provider-managed SQL grants.
-- Do NOT expose schema net through PostgREST. Its queue holds only short-lived
-- signed ticks, never the HMAC key, GitHub PAT, Canvas or Telegram credentials.
DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM vault.secrets WHERE name='flymind_schedule_hmac') THEN RAISE EXCEPTION 'missing_scheduler_secret'; END IF;
 IF EXISTS(SELECT 1 FROM cron.job WHERE jobname='flymind-canvas-timer') THEN RAISE EXCEPTION 'timer_already_exists_do_not_overwrite'; END IF;
END $$;
SELECT cron.schedule('flymind-canvas-timer','*/5 * * * *',$job$
 WITH payload AS MATERIALIZED (
  SELECT jsonb_build_object('tick',gen_random_uuid()::text,'time',floor(extract(epoch from clock_timestamp()))::bigint) AS body
 )
 SELECT net.http_post(
  url:='https://irjasmzytjeohwfpdnrl.supabase.co/functions/v1/flymind-scheduled-dispatch',
  headers:=jsonb_build_object('Content-Type','application/json','x-flymind-signature',
    encode(extensions.hmac(payload.body::text,(SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name='flymind_schedule_hmac'),'sha256'),'hex')),
  body:=payload.body,timeout_milliseconds:=60000
 ) FROM payload;
$job$);
SELECT cron.alter_job((SELECT jobid FROM cron.job WHERE jobname='flymind-canvas-timer'),active:=false);
COMMIT;
-- Explicit later activation: cron.alter_job(..., active:=true).
-- Quick stop: CANVAS_WORKER_ENABLED=false. Timer-only stop: active:=false.
-- Never drop pg_cron: that would erase other jobs and history.
