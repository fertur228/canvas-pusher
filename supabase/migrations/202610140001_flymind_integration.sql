-- PREPARED ONLY. Additive worker tables; legacy Canvas tables are not changed.
BEGIN;
CREATE TABLE public.flymind_accounts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  telegram_chat_id bigint NOT NULL UNIQUE,
  canvas_origin text NOT NULL CHECK (canvas_origin LIKE 'https://%'),
  owner_id uuid REFERENCES auth.users(id),
  enabled boolean NOT NULL DEFAULT false
);
CREATE TABLE public.flymind_snapshots (
  account_id uuid NOT NULL REFERENCES public.flymind_accounts(id),
  kind text NOT NULL CHECK (kind IN ('assignment','file','announcement','report')),
  entity_key text NOT NULL,
  revision bigint NOT NULL DEFAULT 0,
  state_data jsonb,
  reminders jsonb NOT NULL DEFAULT '[]',
  PRIMARY KEY(account_id,kind,entity_key)
);
CREATE TABLE public.flymind_events (
  event_id text PRIMARY KEY CHECK (event_id ~ '^[0-9a-f]{64}$'),
  account_id uuid NOT NULL REFERENCES public.flymind_accounts(id),
  event jsonb NOT NULL,
  encoding jsonb,
  priority integer NOT NULL CHECK(priority BETWEEN 0 AND 2),
  observed_at timestamptz NOT NULL,
  UNIQUE(account_id,event_id)
);
CREATE TABLE public.flymind_jobs (
  job_id text PRIMARY KEY,
  account_id uuid NOT NULL,
  event_id text NOT NULL,
  stage text NOT NULL CHECK(stage IN ('send','simulate','edit')),
  state text NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','running','done','ambiguous','dead')),
  attempts integer NOT NULL DEFAULT 0,
  available_at timestamptz NOT NULL DEFAULT now(),
  lease_token uuid,
  lease_until timestamptz,
  result jsonb,
  FOREIGN KEY(account_id,event_id) REFERENCES public.flymind_events(account_id,event_id),
  UNIQUE(event_id,stage)
);
CREATE INDEX flymind_jobs_ready ON public.flymind_jobs(account_id,stage,available_at) WHERE state='pending';
CREATE TABLE public.flymind_experiments (
  event_id text PRIMARY KEY,
  account_id uuid NOT NULL,
  metadata jsonb NOT NULL,
  biological_response_validated boolean NOT NULL DEFAULT false CHECK(NOT biological_response_validated),
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY(account_id,event_id) REFERENCES public.flymind_events(account_id,event_id)
);

ALTER TABLE public.flymind_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.flymind_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.flymind_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.flymind_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.flymind_experiments ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.flymind_accounts,public.flymind_snapshots,public.flymind_events,public.flymind_jobs,public.flymind_experiments FROM PUBLIC,anon,authenticated;
GRANT ALL ON public.flymind_accounts,public.flymind_snapshots,public.flymind_events,public.flymind_jobs,public.flymind_experiments TO service_role;
GRANT SELECT ON public.flymind_accounts,public.flymind_events,public.flymind_experiments TO authenticated;
CREATE POLICY flymind_account_owner ON public.flymind_accounts FOR SELECT TO authenticated USING(owner_id=auth.uid());
CREATE POLICY flymind_event_owner ON public.flymind_events FOR SELECT TO authenticated USING(EXISTS(SELECT 1 FROM public.flymind_accounts a WHERE a.id=account_id AND a.owner_id=auth.uid()));
CREATE POLICY flymind_experiment_owner ON public.flymind_experiments FOR SELECT TO authenticated USING(EXISTS(SELECT 1 FROM public.flymind_accounts a WHERE a.id=account_id AND a.owner_id=auth.uid()));

INSERT INTO storage.buckets(id,name,public) VALUES('flymind-private','flymind-private',false)
ON CONFLICT(id) DO UPDATE SET public=false;
-- Narrow boolean helper avoids granting anon access to the account table and
-- prevents these guards from breaking unrelated bucket policies.
CREATE FUNCTION public.flymind_storage_owner(p_prefix text) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
 SELECT auth.uid() IS NOT NULL AND EXISTS(SELECT 1 FROM public.flymind_accounts WHERE id::text=p_prefix AND owner_id=auth.uid());
$$;
REVOKE ALL ON FUNCTION public.flymind_storage_owner(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.flymind_storage_owner(text) TO anon,authenticated,service_role;

CREATE POLICY flymind_private_read ON storage.objects FOR SELECT TO authenticated USING(
  bucket_id='flymind-private' AND public.flymind_storage_owner(split_part(name,'/',1)));
-- Restrictive rules also protect this bucket if older unrelated permissive policies are broad.
CREATE POLICY flymind_private_read_guard ON storage.objects AS RESTRICTIVE FOR SELECT TO anon,authenticated USING(
  bucket_id<>'flymind-private' OR public.flymind_storage_owner(split_part(name,'/',1)));
CREATE POLICY flymind_private_insert_guard ON storage.objects AS RESTRICTIVE FOR INSERT TO anon,authenticated WITH CHECK(bucket_id<>'flymind-private');
CREATE POLICY flymind_private_update_guard ON storage.objects AS RESTRICTIVE FOR UPDATE TO anon,authenticated USING(bucket_id<>'flymind-private') WITH CHECK(bucket_id<>'flymind-private');
CREATE POLICY flymind_private_delete_guard ON storage.objects AS RESTRICTIVE FOR DELETE TO anon,authenticated USING(bucket_id<>'flymind-private');

CREATE FUNCTION public.flymind_check_account(p_account uuid,p_chat_id bigint,p_origin text DEFAULT NULL) RETURNS boolean
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
 SELECT EXISTS(SELECT 1 FROM public.flymind_accounts WHERE id=p_account AND enabled AND telegram_chat_id=p_chat_id AND (p_origin IS NULL OR canvas_origin=p_origin));
$$;

CREATE FUNCTION public.flymind_snapshot(p_account uuid,p_kind text,p_key text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE s public.flymind_snapshots; legacy record; chat bigint;
BEGIN
 SELECT * INTO s FROM public.flymind_snapshots WHERE account_id=p_account AND kind=p_kind AND entity_key=p_key;
 IF FOUND THEN RETURN jsonb_build_object('revision',s.revision,'state',s.state_data,'reminders',s.reminders); END IF;
 SELECT telegram_chat_id INTO chat FROM public.flymind_accounts WHERE id=p_account AND enabled;
 IF NOT FOUND THEN RAISE EXCEPTION 'account_disabled'; END IF;
 IF p_kind<>'report' AND to_regclass('public.canvas_state') IS NOT NULL THEN
   EXECUTE 'SELECT state_data,last_reminder_type FROM public.canvas_state WHERE user_id=$1 AND object_type=$2 AND object_id=$3 LIMIT 1'
   INTO legacy USING chat,p_kind,split_part(p_key,':',2)::bigint;
   IF legacy.state_data IS NOT NULL THEN RETURN jsonb_build_object('revision',0,'state',legacy.state_data,'reminders','[]'::jsonb,'legacy_reminder',legacy.last_reminder_type); END IF;
 END IF;
 RETURN jsonb_build_object('revision',0,'state',NULL,'reminders','[]'::jsonb);
END $$;

CREATE FUNCTION public.flymind_commit(p_account uuid,p_kind text,p_key text,p_expected bigint,p_snapshot jsonb,p_events jsonb) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE current_revision bigint; item jsonb; e jsonb; inserted integer;
BEGIN
 IF NOT EXISTS(SELECT 1 FROM public.flymind_accounts WHERE id=p_account AND enabled) THEN RAISE EXCEPTION 'account_disabled'; END IF;
 INSERT INTO public.flymind_snapshots(account_id,kind,entity_key) VALUES(p_account,p_kind,p_key) ON CONFLICT DO NOTHING;
 SELECT revision INTO current_revision FROM public.flymind_snapshots WHERE account_id=p_account AND kind=p_kind AND entity_key=p_key FOR UPDATE;
 IF current_revision<>p_expected THEN RETURN false; END IF;
 IF (p_snapshot->>'revision')::bigint NOT BETWEEN p_expected AND p_expected+1 THEN RAISE EXCEPTION 'invalid_revision'; END IF;
 UPDATE public.flymind_snapshots SET revision=(p_snapshot->>'revision')::bigint,state_data=p_snapshot->'state',reminders=p_snapshot->'reminders'
 WHERE account_id=p_account AND kind=p_kind AND entity_key=p_key;
 FOR item IN SELECT value FROM jsonb_array_elements(p_events) LOOP
   e=item->'event';
   IF e->>'account_id'<>p_account::text OR e->>'entity_key'<>p_key OR e->>'entity_type'<>p_kind THEN RAISE EXCEPTION 'event_scope_mismatch'; END IF;
   INSERT INTO public.flymind_events(event_id,account_id,event,encoding,priority,observed_at)
   VALUES(e->>'event_id',p_account,e,NULLIF(item->'encoding','null'::jsonb),(e->>'priority')::integer,(e->>'observed_at')::timestamptz) ON CONFLICT DO NOTHING;
   GET DIAGNOSTICS inserted=ROW_COUNT;
   IF inserted=1 THEN
     INSERT INTO public.flymind_jobs(job_id,account_id,event_id,stage) VALUES((e->>'event_id')||':send',p_account,e->>'event_id','send');
     IF item->'encoding'<>'null'::jsonb AND item->'encoding' IS NOT NULL THEN
       INSERT INTO public.flymind_jobs(job_id,account_id,event_id,stage) VALUES((e->>'event_id')||':simulate',p_account,e->>'event_id','simulate');
     END IF;
   END IF;
 END LOOP;
 RETURN true;
END $$;

CREATE FUNCTION public.flymind_claim(p_account uuid,p_stage text) RETURNS jsonb
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
   'message_id',(SELECT result->'message_id' FROM public.flymind_jobs WHERE event_id=j.event_id AND stage='send'));
END $$;

CREATE FUNCTION public.flymind_finish(p_account uuid,p_id text,p_token uuid,p_outcome text,p_result jsonb,p_delay integer DEFAULT 0) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE j public.flymind_jobs;
BEGIN
 IF p_outcome NOT IN ('done','retry','ambiguous','dead') THEN RAISE EXCEPTION 'invalid_outcome'; END IF;
 SELECT * INTO j FROM public.flymind_jobs WHERE job_id=p_id AND account_id=p_account AND lease_token=p_token AND state='running' FOR UPDATE;
 IF NOT FOUND THEN RETURN false; END IF;
 UPDATE public.flymind_jobs SET state=CASE WHEN p_outcome='retry' THEN 'pending' ELSE p_outcome END,result=p_result,
   available_at=now()+make_interval(secs=>least(86400,greatest(0,p_delay))),lease_token=NULL WHERE job_id=j.job_id;
 IF j.stage='simulate' AND p_outcome IN ('done','dead') THEN
   IF coalesce((p_result->>'biological_response_validated')::boolean,false) THEN RAISE EXCEPTION 'unvalidated_model'; END IF;
   INSERT INTO public.flymind_experiments(event_id,account_id,metadata) VALUES(j.event_id,p_account,p_result)
   ON CONFLICT(event_id) DO UPDATE SET metadata=excluded.metadata;
   INSERT INTO public.flymind_jobs(job_id,account_id,event_id,stage) VALUES(j.event_id||':edit',p_account,j.event_id,'edit') ON CONFLICT DO NOTHING;
 END IF;
 RETURN true;
END $$;

CREATE FUNCTION public.flymind_counts(p_account uuid) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
 SELECT coalesce(jsonb_object_agg(key,n),'{}'::jsonb) FROM(SELECT stage||'.'||state AS key,count(*) AS n FROM public.flymind_jobs WHERE account_id=p_account GROUP BY stage,state) q;
$$;

CREATE FUNCTION public.flymind_reconcile(p_account uuid,p_id text,p_message_id bigint DEFAULT NULL,p_confirm_no_delivery boolean DEFAULT false) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
BEGIN
 IF (p_message_id IS NULL AND NOT p_confirm_no_delivery) OR p_message_id<=0 THEN RAISE EXCEPTION 'operator_confirmation_required'; END IF;
 UPDATE public.flymind_jobs SET state=CASE WHEN p_message_id IS NULL THEN 'pending' ELSE 'done' END,
 result=CASE WHEN p_message_id IS NULL THEN NULL ELSE jsonb_build_object('message_id',p_message_id) END,available_at=now()
 WHERE account_id=p_account AND job_id=p_id AND stage='send' AND state='ambiguous';
 RETURN FOUND;
END $$;

-- These are service-worker RPCs. Browser sessions can only SELECT their own data via RLS.
DO $$ DECLARE fn record; BEGIN
 FOR fn IN SELECT p.oid::regprocedure AS signature FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.proname IN
 ('flymind_check_account','flymind_snapshot','flymind_commit','flymind_claim','flymind_finish','flymind_counts','flymind_reconcile') LOOP
 EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC,anon,authenticated',fn.signature);
 EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO service_role',fn.signature);
 END LOOP;
END $$;
COMMIT;
