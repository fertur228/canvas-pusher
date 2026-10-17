BEGIN;
-- Explicit opt-in maintenance. Never removes snapshots, event identity or delivery tombstones.
CREATE FUNCTION public.flymind_retention(p_account uuid,p_days integer DEFAULT 30,p_apply boolean DEFAULT false) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE candidates jsonb;
BEGIN
 IF p_days<7 OR p_days>3650 THEN RAISE EXCEPTION 'invalid_retention'; END IF;
 IF NOT EXISTS(SELECT 1 FROM public.flymind_accounts WHERE id=p_account AND enabled) THEN RAISE EXCEPTION 'account_disabled'; END IF;
 SELECT coalesce(jsonb_agg(jsonb_build_object('event_id',e.event_id,'path',e.metadata->>'telemetry_path')),'[]') INTO candidates
 FROM public.flymind_experiments e WHERE e.account_id=p_account AND e.created_at<now()-make_interval(days=>p_days)
 AND e.metadata->>'telemetry_path' IS NOT NULL
 AND NOT EXISTS(SELECT 1 FROM public.flymind_jobs j WHERE j.event_id=e.event_id AND j.state NOT IN ('done','dead'));
 IF p_apply THEN
 UPDATE public.flymind_experiments e SET metadata=(metadata-'telemetry_path')||jsonb_build_object('telemetry_unavailable','retention_expired','telemetry_expired_at',now())
 WHERE e.account_id=p_account AND e.event_id IN (SELECT x->>'event_id' FROM jsonb_array_elements(candidates) x);
 DELETE FROM public.flymind_attempts WHERE id IN (SELECT id FROM public.flymind_attempts WHERE account_id=p_account AND created_at<now()-make_interval(days=>p_days) ORDER BY id LIMIT 1000);
 END IF;
 RETURN candidates;
END $$;

CREATE FUNCTION public.flymind_orphans(p_account uuid) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
 SELECT coalesce(jsonb_agg(name),'[]') FROM (
 SELECT o.name FROM storage.objects o WHERE o.bucket_id='flymind-private' AND split_part(o.name,'/',1)=p_account::text
 AND o.created_at<now()-interval '1 day'
 AND EXISTS(SELECT 1 FROM public.flymind_accounts a WHERE a.id=p_account AND a.enabled)
 AND NOT EXISTS(SELECT 1 FROM public.flymind_experiments e WHERE e.account_id=p_account AND e.metadata->>'telemetry_path'=o.name)
 AND NOT EXISTS(SELECT 1 FROM public.flymind_jobs j WHERE j.account_id=p_account AND j.event_id=split_part(o.name,'/',2) AND j.state IN ('pending','running','ambiguous'))
 ORDER BY o.name LIMIT 100) q;
$$;
CREATE FUNCTION public.flymind_retry_dead(p_account uuid,p_job text) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
BEGIN
 -- Ambiguous sends require the separate evidence-based reconcile RPC.
 UPDATE public.flymind_jobs SET state='pending',attempts=0,available_at=now(),lease_token=NULL
 WHERE account_id=p_account AND job_id=p_job AND state='dead';
 RETURN FOUND;
END $$;
REVOKE ALL ON FUNCTION public.flymind_retention(uuid,integer,boolean),public.flymind_orphans(uuid),public.flymind_retry_dead(uuid,text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.flymind_retention(uuid,integer,boolean),public.flymind_orphans(uuid),public.flymind_retry_dead(uuid,text) TO service_role;
COMMIT;
