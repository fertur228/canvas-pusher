-- A cancelled reminder closes its auxiliary job without running the brain.
-- Do not report that bookkeeping transition as an actual successful simulation.
-- No migration-time data updates; existing function privileges are preserved.
BEGIN;
CREATE OR REPLACE FUNCTION public.flymind_job_audit() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
BEGIN
 IF NEW.state IS DISTINCT FROM OLD.state THEN
 INSERT INTO public.flymind_attempts(account_id,job_id,stage,state,attempt,error_code)
 VALUES(NEW.account_id,NEW.job_id,NEW.stage,NEW.state,NEW.attempts,left(NEW.result->>'error_code',80));
 END IF;
 IF NEW.state='done' AND OLD.state<>'done' AND NEW.stage IN ('send','simulate') THEN
 INSERT INTO public.flymind_health(account_id) VALUES(NEW.account_id) ON CONFLICT DO NOTHING;
 UPDATE public.flymind_health SET
 last_neural_success=CASE WHEN NEW.stage='simulate' AND NEW.result->>'status'='complete'
                         THEN now() ELSE last_neural_success END,
 last_telegram_success=CASE WHEN NEW.stage='send' AND (NEW.result->>'message_id')::bigint>0
                           THEN now() ELSE last_telegram_success END,
 last_database_success=now(),updated_at=now() WHERE account_id=NEW.account_id;
 END IF;
 RETURN NEW;
END $$;
COMMIT;
