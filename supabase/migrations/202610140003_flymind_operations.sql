-- Additive operational state; apply to isolated staging first.
BEGIN;
ALTER TABLE public.flymind_accounts ADD COLUMN initialized_at timestamptz;
CREATE TABLE public.flymind_health (
 account_id uuid PRIMARY KEY REFERENCES public.flymind_accounts(id),
 last_attempt timestamptz, last_canvas_success timestamptz, last_database_success timestamptz,
 last_neural_success timestamptz, last_telegram_success timestamptz,
 status text NOT NULL DEFAULT 'unknown', error_code text, queue jsonb NOT NULL DEFAULT '{}',
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.flymind_attempts (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 account_id uuid NOT NULL REFERENCES public.flymind_accounts(id), job_id text NOT NULL,
 stage text NOT NULL, state text NOT NULL, attempt integer NOT NULL,
 error_code text, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX flymind_attempts_account_time ON public.flymind_attempts(account_id,created_at DESC);
CREATE TABLE public.flymind_webhook_updates (
 update_id bigint PRIMARY KEY CHECK(update_id>=0), account_id uuid NOT NULL REFERENCES public.flymind_accounts(id),
 status text NOT NULL DEFAULT 'claimed' CHECK(status IN ('claimed','done','ambiguous')),
 created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.flymind_health ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.flymind_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.flymind_webhook_updates ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.flymind_health,public.flymind_attempts,public.flymind_webhook_updates FROM PUBLIC,anon,authenticated;
GRANT ALL ON public.flymind_health,public.flymind_attempts,public.flymind_webhook_updates TO service_role;
GRANT USAGE,SELECT ON SEQUENCE public.flymind_attempts_id_seq TO service_role;
GRANT SELECT ON public.flymind_health,public.flymind_attempts TO authenticated;
CREATE POLICY flymind_health_owner ON public.flymind_health FOR SELECT TO authenticated USING(EXISTS(SELECT 1 FROM public.flymind_accounts a WHERE a.id=account_id AND a.owner_id=auth.uid()));
CREATE POLICY flymind_attempt_owner ON public.flymind_attempts FOR SELECT TO authenticated USING(EXISTS(SELECT 1 FROM public.flymind_accounts a WHERE a.id=account_id AND a.owner_id=auth.uid()));

CREATE FUNCTION public.flymind_runtime(p_account uuid,p_initialize boolean DEFAULT false) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE stamp timestamptz;
BEGIN
 IF NOT EXISTS(SELECT 1 FROM public.flymind_accounts WHERE id=p_account AND enabled) THEN RAISE EXCEPTION 'account_disabled'; END IF;
 IF p_initialize THEN UPDATE public.flymind_accounts SET initialized_at=coalesce(initialized_at,now()) WHERE id=p_account; END IF;
 SELECT initialized_at INTO stamp FROM public.flymind_accounts WHERE id=p_account;
 RETURN jsonb_build_object('initialized',stamp IS NOT NULL);
END $$;

CREATE FUNCTION public.flymind_heartbeat(p_account uuid,p_phase text,p_status text DEFAULT 'running',p_error text DEFAULT NULL) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
BEGIN
 IF p_phase NOT IN ('attempt','canvas','finish') OR p_status NOT IN ('running','healthy','degraded','failed','disabled','bootstrapped') THEN RAISE EXCEPTION 'invalid_health'; END IF;
 IF NOT EXISTS(SELECT 1 FROM public.flymind_accounts WHERE id=p_account AND enabled) THEN RAISE EXCEPTION 'account_disabled'; END IF;
 INSERT INTO public.flymind_health(account_id) VALUES(p_account) ON CONFLICT DO NOTHING;
 UPDATE public.flymind_health SET last_attempt=CASE WHEN p_phase='attempt' THEN now() ELSE last_attempt END,
 last_canvas_success=CASE WHEN p_phase='canvas' THEN now() ELSE last_canvas_success END,
 last_database_success=now(),status=p_status,error_code=left(p_error,80),queue=public.flymind_counts(p_account),updated_at=now() WHERE account_id=p_account;
 RETURN true;
END $$;

CREATE FUNCTION public.flymind_job_audit() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
BEGIN
 IF NEW.state IS DISTINCT FROM OLD.state THEN
 INSERT INTO public.flymind_attempts(account_id,job_id,stage,state,attempt,error_code)
 VALUES(NEW.account_id,NEW.job_id,NEW.stage,NEW.state,NEW.attempts,left(NEW.result->>'error_code',80));
 END IF;
 IF NEW.state='done' AND OLD.state<>'done' AND NEW.stage IN ('send','simulate') THEN
 INSERT INTO public.flymind_health(account_id) VALUES(NEW.account_id) ON CONFLICT DO NOTHING;
 UPDATE public.flymind_health SET last_neural_success=CASE WHEN NEW.stage='simulate' THEN now() ELSE last_neural_success END,
 last_telegram_success=CASE WHEN NEW.stage='send' AND (NEW.result->>'message_id')::bigint>0 THEN now() ELSE last_telegram_success END,
 last_database_success=now(),updated_at=now() WHERE account_id=NEW.account_id;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER flymind_job_audit AFTER UPDATE ON public.flymind_jobs FOR EACH ROW EXECUTE FUNCTION public.flymind_job_audit();

CREATE FUNCTION public.flymind_webhook_claim(p_chat bigint,p_update bigint) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
BEGIN
 INSERT INTO public.flymind_webhook_updates(update_id,account_id)
 SELECT p_update,id FROM public.flymind_accounts WHERE telegram_chat_id=p_chat AND enabled
 ON CONFLICT DO NOTHING;
 RETURN FOUND;
END $$;

-- Owner status can only be read through RLS. All mutations are worker-only.
DO $$ DECLARE fn record; BEGIN
 FOR fn IN SELECT p.oid::regprocedure AS signature FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.proname IN
 ('flymind_runtime','flymind_heartbeat','flymind_job_audit','flymind_webhook_claim') LOOP
 EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC,anon,authenticated',fn.signature);
 EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO service_role',fn.signature);
 END LOOP;
END $$;
COMMIT;
