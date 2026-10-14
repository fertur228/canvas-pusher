-- Additive assistant state. Apply to isolated staging first; no academic data removed.
BEGIN;
ALTER TABLE public.flymind_accounts ADD COLUMN telegram_bot_id bigint, ADD COLUMN telegram_user_id bigint;
ALTER TABLE public.flymind_webhook_updates ADD COLUMN bot_id bigint NOT NULL DEFAULT 0;
ALTER TABLE public.flymind_webhook_updates DROP CONSTRAINT flymind_webhook_updates_pkey;
ALTER TABLE public.flymind_webhook_updates ADD PRIMARY KEY(bot_id,update_id);
REVOKE ALL ON FUNCTION public.flymind_webhook_claim(bigint,bigint) FROM service_role;
CREATE FUNCTION public.flymind_webhook_claim(p_bot bigint,p_chat bigint,p_user bigint,p_update bigint) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
BEGIN
 INSERT INTO public.flymind_webhook_updates(bot_id,update_id,account_id)
 SELECT p_bot,p_update,id FROM public.flymind_accounts WHERE enabled AND telegram_chat_id=p_chat AND telegram_user_id=p_user AND telegram_bot_id=p_bot
 ON CONFLICT DO NOTHING;
 RETURN FOUND;
END $$;

ALTER TABLE public.flymind_snapshots ADD COLUMN verified_data jsonb, ADD COLUMN verified_at timestamptz;
ALTER TABLE public.flymind_health ADD COLUMN last_snapshot_success timestamptz;
CREATE FUNCTION public.flymind_sync_verified(p_account uuid,p_keys text[]) RETURNS timestamptz
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE stamp timestamptz=clock_timestamp();
BEGIN
 IF NOT EXISTS(SELECT 1 FROM public.flymind_accounts WHERE id=p_account AND enabled) THEN RAISE EXCEPTION 'account_disabled'; END IF;
 -- Unseen/deleted/inactive-course assignments remain in history, outside the current verified list.
 UPDATE public.flymind_snapshots SET verified_data=state_data,verified_at=stamp WHERE account_id=p_account AND kind='assignment' AND entity_key=ANY(p_keys);
 INSERT INTO public.flymind_health(account_id,last_snapshot_success) VALUES(p_account,stamp)
 ON CONFLICT(account_id) DO UPDATE SET last_snapshot_success=stamp,last_database_success=stamp;
 RETURN stamp;
END $$;
CREATE FUNCTION public.flymind_try_date(value text) RETURNS timestamptz LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog AS $$
BEGIN
 IF value IS NULL OR value !~ '^\d{4}-\d{2}-\d{2}T.*(Z|[+-]\d{2}:\d{2})$' THEN RETURN NULL; END IF;
 RETURN value::timestamptz;
EXCEPTION WHEN OTHERS THEN RETURN NULL;
END $$;
CREATE FUNCTION public.flymind_deadlines(p_account uuid,p_view text DEFAULT 'upcoming',p_page integer DEFAULT 0,p_now timestamptz DEFAULT now()) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE stamp timestamptz; result jsonb; total integer; invalid integer; current_page integer;
BEGIN
 IF p_view NOT IN ('upcoming','overdue','today','week','month','all','undated') OR p_page<0 OR p_page>10000 THEN RAISE EXCEPTION 'invalid_deadline_view'; END IF;
 IF NOT EXISTS(SELECT 1 FROM public.flymind_accounts WHERE id=p_account AND enabled) THEN RAISE EXCEPTION 'account_disabled'; END IF;
 SELECT last_snapshot_success INTO stamp FROM public.flymind_health WHERE account_id=p_account;
 IF stamp IS NULL THEN RETURN jsonb_build_object('synced_at',NULL,'rows','[]'::jsonb,'total',0,'page',0); END IF;
 WITH pending AS (
 SELECT entity_key,verified_data AS data,public.flymind_try_date(verified_data->>'due_at') AS due
 FROM public.flymind_snapshots WHERE account_id=p_account AND kind='assignment' AND verified_at=stamp AND verified_data->>'has_submitted'='false'
 ), filtered AS (
 SELECT * FROM pending WHERE CASE p_view
 WHEN 'undated' THEN data->>'due_at' IS NULL
 WHEN 'all' THEN due IS NOT NULL OR data->>'due_at' IS NULL
 WHEN 'overdue' THEN due<p_now
 WHEN 'today' THEN (due AT TIME ZONE 'Asia/Almaty')::date=(p_now AT TIME ZONE 'Asia/Almaty')::date
 WHEN 'week' THEN due>=p_now AND due<p_now+interval '7 days'
 WHEN 'month' THEN due>=p_now AND due<p_now+interval '30 days'
 ELSE due>=p_now END
 ) SELECT count(*) INTO total FROM filtered;
 current_page=least(p_page,greatest(0,(total-1)/3));
 SELECT count(*) INTO invalid FROM public.flymind_snapshots WHERE account_id=p_account AND kind='assignment' AND verified_at=stamp AND verified_data->>'due_at' IS NOT NULL AND public.flymind_try_date(verified_data->>'due_at') IS NULL;
 WITH pending AS (
 SELECT entity_key,verified_data AS data,public.flymind_try_date(verified_data->>'due_at') AS due
 FROM public.flymind_snapshots WHERE account_id=p_account AND kind='assignment' AND verified_at=stamp AND verified_data->>'has_submitted'='false'
 ) SELECT coalesce(jsonb_agg(data ORDER BY due NULLS LAST,entity_key),'[]'::jsonb) INTO result FROM (
 SELECT * FROM pending WHERE CASE p_view
 WHEN 'undated' THEN data->>'due_at' IS NULL WHEN 'all' THEN due IS NOT NULL OR data->>'due_at' IS NULL WHEN 'overdue' THEN due<p_now
 WHEN 'today' THEN (due AT TIME ZONE 'Asia/Almaty')::date=(p_now AT TIME ZONE 'Asia/Almaty')::date
 WHEN 'week' THEN due>=p_now AND due<p_now+interval '7 days'
 WHEN 'month' THEN due>=p_now AND due<p_now+interval '30 days' ELSE due>=p_now END
 ORDER BY due NULLS LAST,entity_key LIMIT 3 OFFSET current_page*3) q;
 RETURN jsonb_build_object('synced_at',stamp,'rows',result,'total',total,'page',current_page,'invalid_deadlines',invalid,'stale',p_now-stamp>interval '30 minutes');
END $$;

CREATE TABLE public.flymind_manual_requests (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),account_id uuid NOT NULL REFERENCES public.flymind_accounts(id),
 bot_id bigint NOT NULL,update_id bigint NOT NULL,workflow_ref text NOT NULL,
 state text NOT NULL DEFAULT 'queued' CHECK(state IN ('queued','dispatched','uncertain','running','completed','failed','expired')),
 created_at timestamptz NOT NULL DEFAULT now(),started_at timestamptz,finished_at timestamptz,
 run_id text UNIQUE,summary jsonb,error_code text,
 UNIQUE(bot_id,update_id)
);
ALTER TABLE public.flymind_manual_requests ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.flymind_manual_requests FROM PUBLIC,anon,authenticated;
GRANT ALL ON public.flymind_manual_requests TO service_role;
GRANT SELECT ON public.flymind_manual_requests TO authenticated;
CREATE POLICY flymind_manual_owner ON public.flymind_manual_requests FOR SELECT TO authenticated USING(EXISTS(SELECT 1 FROM public.flymind_accounts a WHERE a.id=account_id AND a.owner_id=auth.uid()));
CREATE FUNCTION public.flymind_manual_request(p_account uuid,p_bot bigint,p_update bigint,p_ref text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE prior public.flymind_manual_requests; request_id uuid;
BEGIN
 PERFORM 1 FROM public.flymind_accounts WHERE id=p_account AND enabled AND telegram_bot_id=p_bot FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'account_binding_invalid'; END IF;
 SELECT * INTO prior FROM public.flymind_manual_requests WHERE bot_id=p_bot AND update_id=p_update;
 IF FOUND THEN RETURN jsonb_build_object('accepted',false,'state',prior.state,'id',prior.id); END IF;
 UPDATE public.flymind_manual_requests SET state='expired',finished_at=now(),error_code='start_timeout'
 WHERE account_id=p_account AND state IN ('queued','dispatched','uncertain') AND created_at<now()-interval '30 minutes';
 SELECT * INTO prior FROM public.flymind_manual_requests WHERE account_id=p_account AND state IN ('queued','dispatched','uncertain','running') ORDER BY created_at DESC LIMIT 1;
 IF FOUND THEN RETURN jsonb_build_object('accepted',false,'state',prior.state,'id',prior.id); END IF;
 IF EXISTS(SELECT 1 FROM public.flymind_health WHERE account_id=p_account AND status='running' AND last_attempt>now()-interval '20 minutes') THEN RETURN jsonb_build_object('accepted',false,'state','scanner_running'); END IF;
 IF EXISTS(SELECT 1 FROM public.flymind_manual_requests WHERE account_id=p_account AND created_at>now()-interval '60 seconds') THEN RETURN jsonb_build_object('accepted',false,'state','cooldown'); END IF;
 INSERT INTO public.flymind_manual_requests(account_id,bot_id,update_id,workflow_ref) VALUES(p_account,p_bot,p_update,p_ref) RETURNING id INTO request_id;
 RETURN jsonb_build_object('accepted',true,'state','queued','id',request_id);
END $$;
CREATE FUNCTION public.flymind_manual_start(p_account uuid,p_id uuid,p_run text,p_ref text) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
BEGIN
 UPDATE public.flymind_manual_requests r SET state='running',run_id=p_run,started_at=now()
 WHERE r.id=p_id AND r.account_id=p_account AND r.workflow_ref=p_ref AND r.state IN ('queued','dispatched','uncertain') AND r.created_at>now()-interval '30 minutes'
 AND EXISTS(SELECT 1 FROM public.flymind_accounts a WHERE a.id=p_account AND a.enabled AND a.telegram_bot_id=r.bot_id);
 RETURN FOUND;
END $$;
CREATE FUNCTION public.flymind_manual_prepare(p_account uuid,p_id uuid,p_run text,p_summary jsonb) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
BEGIN
 UPDATE public.flymind_manual_requests SET summary=p_summary WHERE id=p_id AND account_id=p_account AND run_id=p_run AND state='running';
 RETURN FOUND;
END $$;
CREATE FUNCTION public.flymind_manual_complete(p_account uuid,p_id uuid,p_run text,p_conclusion text,p_event jsonb) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE r public.flymind_manual_requests;
BEGIN
 SELECT * INTO r FROM public.flymind_manual_requests WHERE account_id=p_account AND id=p_id AND (run_id=p_run OR run_id IS NULL) FOR UPDATE;
 IF NOT FOUND OR r.state NOT IN ('queued','dispatched','uncertain','running','expired') THEN RETURN false; END IF;
 IF p_event->>'account_id'<>p_account::text OR p_event->>'entity_type'<>'report' OR p_event->'payload'->>'id'<>r.id::text THEN RAISE EXCEPTION 'invalid_completion_event'; END IF;
 UPDATE public.flymind_manual_requests SET run_id=p_run,state=CASE WHEN p_conclusion='success' AND summary->>'sync_status'='verified' THEN 'completed' ELSE 'failed' END,finished_at=now() WHERE id=r.id;
 -- A bot replacement must not leak a delayed old-bot completion to the new recipient.
 IF NOT EXISTS(SELECT 1 FROM public.flymind_accounts WHERE id=p_account AND enabled AND telegram_bot_id=r.bot_id) THEN RETURN true; END IF;
 INSERT INTO public.flymind_events(event_id,account_id,event,priority,observed_at) VALUES(p_event->>'event_id',p_account,p_event,1,(p_event->>'observed_at')::timestamptz) ON CONFLICT DO NOTHING;
 INSERT INTO public.flymind_jobs(job_id,account_id,event_id,stage) VALUES((p_event->>'event_id')||':send',p_account,p_event->>'event_id','send') ON CONFLICT DO NOTHING;
 RETURN true;
END $$;
CREATE FUNCTION public.flymind_bind_bot(p_account uuid,p_bot bigint,p_user bigint,p_chat bigint) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
BEGIN
 PERFORM 1 FROM public.flymind_accounts WHERE id=p_account FOR UPDATE;
 IF NOT FOUND OR p_bot<=0 OR p_user<=0 OR p_chat=0 THEN RAISE EXCEPTION 'invalid_binding'; END IF;
 IF EXISTS(SELECT 1 FROM public.flymind_jobs WHERE account_id=p_account AND state='running') OR EXISTS(SELECT 1 FROM public.flymind_manual_requests WHERE account_id=p_account AND state IN ('queued','dispatched','uncertain','running')) THEN RAISE EXCEPTION 'stop_and_reconcile_workers_first'; END IF;
 UPDATE public.flymind_accounts SET telegram_bot_id=p_bot,telegram_user_id=p_user,telegram_chat_id=p_chat WHERE id=p_account;
 RETURN true;
END $$;
DO $$ DECLARE fn record; BEGIN
 FOR fn IN SELECT p.oid::regprocedure AS signature FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.proname IN
 ('flymind_webhook_claim','flymind_sync_verified','flymind_try_date','flymind_deadlines','flymind_manual_request','flymind_manual_start','flymind_manual_prepare','flymind_manual_complete','flymind_bind_bot') LOOP
 EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC,anon,authenticated',fn.signature);
 IF fn.signature::text<>'flymind_webhook_claim(bigint,bigint)' THEN EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO service_role',fn.signature); END IF;
 END LOOP;
END $$;
CREATE OR REPLACE FUNCTION public.flymind_claim(p_account uuid,p_stage text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE j public.flymind_jobs; token uuid;
BEGIN
 IF NOT EXISTS(SELECT 1 FROM public.flymind_accounts WHERE id=p_account AND enabled) THEN RAISE EXCEPTION 'account_disabled'; END IF;
 IF p_stage NOT IN ('send','simulate','edit') THEN RAISE EXCEPTION 'invalid_stage'; END IF;
 UPDATE public.flymind_jobs SET state=CASE WHEN stage='send' THEN 'ambiguous' ELSE 'pending' END,lease_token=NULL,result=jsonb_build_object('error_code','expired_lease')
 WHERE account_id=p_account AND state='running' AND lease_until<now();
 SELECT jobs.* INTO j FROM public.flymind_jobs jobs JOIN public.flymind_events e USING(event_id)
 WHERE jobs.account_id=p_account AND jobs.stage=p_stage AND jobs.state='pending' AND jobs.available_at<=now()
   AND (p_stage='send' OR EXISTS(SELECT 1 FROM public.flymind_jobs b WHERE b.event_id=jobs.event_id AND b.stage='send' AND b.state='done'))
 ORDER BY e.priority DESC,e.observed_at,jobs.job_id LIMIT 1 FOR UPDATE OF jobs SKIP LOCKED;
 IF NOT FOUND THEN RETURN NULL; END IF;
 token=gen_random_uuid();
 UPDATE public.flymind_jobs SET state='running',attempts=attempts+1,lease_token=token,lease_until=now()+interval '120 seconds' WHERE job_id=j.job_id;
 RETURN jsonb_build_object('id',j.job_id,'stage',j.stage,'token',token,'attempts',j.attempts+1,
   'event',(SELECT event FROM public.flymind_events WHERE event_id=j.event_id),
   'encoding',(SELECT encoding FROM public.flymind_events WHERE event_id=j.event_id),
   'neural',(SELECT metadata FROM public.flymind_experiments WHERE event_id=j.event_id),
   'base_bot_id',(SELECT result->'bot_id' FROM public.flymind_jobs WHERE event_id=j.event_id AND stage='send'),
   'message_id',(SELECT result->'message_id' FROM public.flymind_jobs WHERE event_id=j.event_id AND stage='send'));
END $$;

CREATE FUNCTION public.flymind_check_bot(p_account uuid,p_bot bigint) RETURNS boolean
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
 SELECT EXISTS(SELECT 1 FROM public.flymind_accounts WHERE id=p_account AND enabled AND telegram_bot_id=p_bot);
$$;
REVOKE ALL ON FUNCTION public.flymind_check_bot(uuid,bigint) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.flymind_check_bot(uuid,bigint) TO service_role;
CREATE FUNCTION public.flymind_claim_report(p_account uuid,p_event text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE j public.flymind_jobs; token uuid=gen_random_uuid();
BEGIN
 UPDATE public.flymind_jobs SET state='ambiguous',lease_token=NULL,result='{"error_code":"expired_lease"}'
 WHERE account_id=p_account AND event_id=p_event AND stage='send' AND state='running' AND lease_until<now();
 SELECT jobs.* INTO j FROM public.flymind_jobs jobs JOIN public.flymind_events e USING(event_id)
 WHERE jobs.account_id=p_account AND jobs.event_id=p_event AND jobs.stage='send' AND jobs.state='pending' AND jobs.available_at<=now()
 AND e.event->>'entity_type'='report' AND EXISTS(SELECT 1 FROM public.flymind_accounts WHERE id=p_account AND enabled)
 FOR UPDATE OF jobs SKIP LOCKED;
 IF NOT FOUND THEN RETURN NULL; END IF;
 UPDATE public.flymind_jobs SET state='running',attempts=attempts+1,lease_token=token,lease_until=now()+interval '120 seconds' WHERE job_id=j.job_id;
 RETURN jsonb_build_object('id',j.job_id,'stage','send','token',token,'attempts',j.attempts+1,'event',(SELECT event FROM public.flymind_events WHERE event_id=p_event),'neural',NULL,'message_id',NULL);
END $$;
REVOKE ALL ON FUNCTION public.flymind_claim_report(uuid,text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.flymind_claim_report(uuid,text) TO service_role;
COMMIT;
