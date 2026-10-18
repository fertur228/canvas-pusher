
INSERT INTO auth.users VALUES('10000000-0000-0000-0000-000000000001'),('10000000-0000-0000-0000-000000000002');
INSERT INTO public.flymind_accounts(id,telegram_chat_id,canvas_origin,owner_id,enabled) VALUES
('00000000-0000-0000-0000-000000000001',123,'https://canvas.invalid','10000000-0000-0000-0000-000000000001',true),
('00000000-0000-0000-0000-000000000002',456,'https://canvas.invalid','10000000-0000-0000-0000-000000000002',true);
DO $$ BEGIN
 IF NOT public.flymind_check_account('00000000-0000-0000-0000-000000000001',123,'https://canvas.invalid') THEN RAISE EXCEPTION 'valid_binding_rejected'; END IF;
 IF public.flymind_check_account('00000000-0000-0000-0000-000000000001',456) THEN RAISE EXCEPTION 'cross_chat_binding'; END IF;
 IF public.flymind_check_account('00000000-0000-0000-0000-000000000001',123,'https://evil.invalid') THEN RAISE EXCEPTION 'cross_origin_binding'; END IF;
 IF NOT public.flymind_commit('00000000-0000-0000-0000-000000000001','assignment','20:10',0,'{"reminders":[],"revision":1,"state":{"course_id":20,"course_name":"SYNTHETIC course","course_score":null,"due_at":"2026-10-19T00:00:00+00:00","has_submitted":false,"id":10,"name":"<SYNTHETIC task>","points_possible":100.0,"score":null}}'::jsonb,'[{"encoding":{"case":"weak","meaning":"Engineering mapping to an existing recorded-protocol hypothesis, not a biological Canvas sense","parameters_policy":"Unchanged literature_parameters + presynaptic_shiu + exponential_current","stimulus":{"contrast":0.35,"direct_gf_stimulation":false,"radius_over_speed_ms":80,"targets":["LC4","LPLC2"]},"version":"canvas-looming/v1"},"event":{"account_id":"00000000-0000-0000-0000-000000000001","changes":{},"entity_key":"20:10","entity_type":"assignment","event_id":"03b609bc50c03ea3dc035e977b8c946275eb561e308275a436dd09a8645cae0a","kind":"assignment_created","observed_at":"2026-10-14T00:00:00+00:00","payload":{"course_id":20,"course_name":"SYNTHETIC course","course_score":null,"due_at":"2026-10-19T00:00:00+00:00","has_submitted":false,"id":10,"name":"<SYNTHETIC task>","points_possible":100.0,"score":null},"priority":1,"reminder":null,"revision":1,"schema_version":1}}]'::jsonb) THEN RAISE EXCEPTION 'commit_failed'; END IF;
 IF public.flymind_commit('00000000-0000-0000-0000-000000000001','assignment','20:10',0,'{"reminders":[],"revision":1,"state":{"course_id":20,"course_name":"SYNTHETIC course","course_score":null,"due_at":"2026-10-19T00:00:00+00:00","has_submitted":false,"id":10,"name":"<SYNTHETIC task>","points_possible":100.0,"score":null}}'::jsonb,'[{"encoding":{"case":"weak","meaning":"Engineering mapping to an existing recorded-protocol hypothesis, not a biological Canvas sense","parameters_policy":"Unchanged literature_parameters + presynaptic_shiu + exponential_current","stimulus":{"contrast":0.35,"direct_gf_stimulation":false,"radius_over_speed_ms":80,"targets":["LC4","LPLC2"]},"version":"canvas-looming/v1"},"event":{"account_id":"00000000-0000-0000-0000-000000000001","changes":{},"entity_key":"20:10","entity_type":"assignment","event_id":"03b609bc50c03ea3dc035e977b8c946275eb561e308275a436dd09a8645cae0a","kind":"assignment_created","observed_at":"2026-10-14T00:00:00+00:00","payload":{"course_id":20,"course_name":"SYNTHETIC course","course_score":null,"due_at":"2026-10-19T00:00:00+00:00","has_submitted":false,"id":10,"name":"<SYNTHETIC task>","points_possible":100.0,"score":null},"priority":1,"reminder":null,"revision":1,"schema_version":1}}]'::jsonb) THEN RAISE EXCEPTION 'stale_revision_accepted'; END IF;
 IF (SELECT count(*) FROM public.flymind_events)<>1 OR (SELECT count(*) FROM public.flymind_jobs)<>2 THEN RAISE EXCEPTION 'duplicate_events_or_jobs'; END IF;
END $$;
DO $$ DECLARE j jsonb; n jsonb; BEGIN
 IF public.flymind_claim('00000000-0000-0000-0000-000000000001','simulate') IS NOT NULL THEN RAISE EXCEPTION 'neural_started_before_delivery'; END IF;
 j=public.flymind_claim('00000000-0000-0000-0000-000000000001','send');
 IF j IS NULL THEN RAISE EXCEPTION 'claim_failed'; END IF;
 IF public.flymind_claim('00000000-0000-0000-0000-000000000001','send') IS NOT NULL THEN RAISE EXCEPTION 'duplicate_claim'; END IF;
 IF public.flymind_finish('00000000-0000-0000-0000-000000000001',j->>'id','00000000-0000-0000-0000-000000000000','done','{"message_id":42}') THEN RAISE EXCEPTION 'bad_token_accepted'; END IF;
 IF NOT public.flymind_finish('00000000-0000-0000-0000-000000000001',j->>'id',(j->>'token')::uuid,'done','{"message_id":42}') THEN RAISE EXCEPTION 'send_ack_failed'; END IF;
 IF public.flymind_finish('00000000-0000-0000-0000-000000000001',j->>'id',(j->>'token')::uuid,'done','{"message_id":42}') THEN RAISE EXCEPTION 'duplicate_ack'; END IF;
 n=public.flymind_claim('00000000-0000-0000-0000-000000000001','simulate');
 IF n->>'message_id'<>'42' THEN RAISE EXCEPTION 'base_message_association'; END IF;
 PERFORM public.flymind_finish('00000000-0000-0000-0000-000000000001',n->>'id',(n->>'token')::uuid,'done','{"status":"complete","biological_response_validated":false,"readout":{"classification":"moderate"}}');
 IF (SELECT count(*) FROM public.flymind_experiments)<>1 OR public.flymind_claim('00000000-0000-0000-0000-000000000001','edit') IS NULL THEN RAISE EXCEPTION 'metadata_or_edit_missing'; END IF;
END $$;
INSERT INTO storage.objects(bucket_id,name) VALUES('flymind-private','00000000-0000-0000-0000-000000000001/event/telemetry.json.gz'),('flymind-private','00000000-0000-0000-0000-000000000002/event/telemetry.json.gz'),('other','public-example');
BEGIN;
SET LOCAL ROLE authenticated;
SET LOCAL request.jwt.claim.sub='10000000-0000-0000-0000-000000000001';
DO $$ BEGIN
 IF (SELECT count(*) FROM public.course_grades)<>1 THEN RAISE EXCEPTION 'legacy_grades_owner_scope'; END IF;
 IF (SELECT count(*) FROM public.flymind_accounts)<>1 OR (SELECT count(*) FROM public.flymind_experiments)<>1 THEN RAISE EXCEPTION 'owner_scope_wrong'; END IF;
 IF (SELECT count(*) FROM storage.objects WHERE bucket_id='flymind-private')<>1 THEN RAISE EXCEPTION 'storage_owner_scope_wrong'; END IF;
 BEGIN PERFORM public.flymind_claim('00000000-0000-0000-0000-000000000001','send'); RAISE EXCEPTION 'browser_called_worker_rpc'; EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN INSERT INTO storage.objects(bucket_id,name) VALUES('flymind-private','00000000-0000-0000-0000-000000000001/malicious'); RAISE EXCEPTION 'browser_uploaded_private_blob'; EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN PERFORM * FROM public.flymind_jobs; RAISE EXCEPTION 'browser_read_worker_outbox'; EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
SET LOCAL request.jwt.claim.sub='10000000-0000-0000-0000-000000000002';
DO $$ BEGIN
 IF (SELECT count(*) FROM public.flymind_experiments)<>0 THEN RAISE EXCEPTION 'other_owner_read_experiment'; END IF;
 IF (SELECT count(*) FROM storage.objects WHERE bucket_id='flymind-private')<>1 THEN RAISE EXCEPTION 'other_owner_scope_wrong'; END IF;
END $$;
SET LOCAL ROLE anon;
SET LOCAL request.jwt.claim.sub='';
DO $$ BEGIN
 IF (SELECT count(*) FROM storage.objects WHERE bucket_id='flymind-private')<>0 THEN RAISE EXCEPTION 'anonymous_read_private_blob'; END IF;
 IF (SELECT count(*) FROM storage.objects WHERE bucket_id='other')<>1 THEN RAISE EXCEPTION 'unrelated_bucket_broken'; END IF;
 BEGIN PERFORM * FROM public.course_grades; RAISE EXCEPTION 'anonymous_read_legacy_grades'; EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN PERFORM * FROM public.flymind_events; RAISE EXCEPTION 'anonymous_read_canvas_data'; EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
ROLLBACK;
SELECT 'PostgreSQL RPC + ownership/RLS + restrictive Storage checks passed' AS result;

DO $$ BEGIN
 IF (public.flymind_runtime('00000000-0000-0000-0000-000000000001')->>'initialized')::boolean THEN RAISE EXCEPTION 'unsafe_initialization_default'; END IF;
 PERFORM public.flymind_runtime('00000000-0000-0000-0000-000000000001',true);
 PERFORM public.flymind_heartbeat('00000000-0000-0000-0000-000000000001','attempt');
 PERFORM public.flymind_heartbeat('00000000-0000-0000-0000-000000000001','canvas');
 PERFORM public.flymind_heartbeat('00000000-0000-0000-0000-000000000001','finish','healthy');
 IF (SELECT last_telegram_success IS NULL OR last_neural_success IS NULL OR last_canvas_success IS NULL FROM public.flymind_health WHERE account_id='00000000-0000-0000-0000-000000000001') THEN RAISE EXCEPTION 'missing_heartbeat_evidence'; END IF;
 IF (SELECT count(*) FROM public.flymind_attempts)<4 THEN RAISE EXCEPTION 'missing_attempt_audit'; END IF;
 IF NOT public.flymind_webhook_claim(123,42) OR public.flymind_webhook_claim(123,42) OR public.flymind_webhook_claim(999,43) THEN RAISE EXCEPTION 'webhook_dedupe_or_scope'; END IF;
END $$;
BEGIN;
UPDATE public.flymind_experiments SET created_at=now()-interval '40 days',metadata=metadata||jsonb_build_object('telemetry_path','00000000-0000-0000-0000-000000000001/'||event_id||'/'||repeat('a',64)||'.json.gz');
DO $$ BEGIN
 IF jsonb_array_length(public.flymind_retention('00000000-0000-0000-0000-000000000001',30,false))<>0 THEN RAISE EXCEPTION 'retention_removed_active_job'; END IF;
END $$;
UPDATE public.flymind_jobs SET state='done' WHERE stage='edit';
DO $$ BEGIN
 IF jsonb_array_length(public.flymind_retention('00000000-0000-0000-0000-000000000001',30,false))<>1 THEN RAISE EXCEPTION 'retention_dry_run'; END IF;
 IF NOT EXISTS(SELECT 1 FROM public.flymind_experiments WHERE metadata->>'telemetry_path' IS NOT NULL) THEN RAISE EXCEPTION 'dry_run_mutated'; END IF;
 PERFORM public.flymind_retention('00000000-0000-0000-0000-000000000001',30,true);
 IF EXISTS(SELECT 1 FROM public.flymind_experiments WHERE metadata->>'telemetry_path' IS NOT NULL) THEN RAISE EXCEPTION 'retention_reference_not_expired'; END IF;
 IF (SELECT count(*) FROM public.flymind_events)<>1 THEN RAISE EXCEPTION 'lost_event_tombstone'; END IF;
END $$;
SET LOCAL ROLE authenticated;
SET LOCAL request.jwt.claim.sub='10000000-0000-0000-0000-000000000002';
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM public.flymind_health) OR EXISTS(SELECT 1 FROM public.flymind_attempts) THEN RAISE EXCEPTION 'other_owner_health_leak'; END IF;
 BEGIN PERFORM public.flymind_retention('00000000-0000-0000-0000-000000000001',30,true); RAISE EXCEPTION 'browser_retention'; EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
SET LOCAL request.jwt.claim.sub='10000000-0000-0000-0000-000000000001';
DO $$ BEGIN
 IF (SELECT count(*) FROM public.flymind_health)<>1 THEN RAISE EXCEPTION 'owner_health_missing'; END IF;
END $$;
ROLLBACK;
SELECT 'Heartbeat, audit, webhook replay and retention controls passed' AS result;

BEGIN;
UPDATE public.flymind_health SET last_neural_success='2000-01-01T00:00:00Z',last_telegram_success='2000-01-01T00:00:00Z';
UPDATE public.flymind_jobs SET state='pending' WHERE stage IN ('send','simulate');
UPDATE public.flymind_jobs SET state='done',result='{"status":"suppressed","suppressed":"submitted"}' WHERE stage IN ('send','simulate');
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM public.flymind_health WHERE last_neural_success<>'2000-01-01T00:00:00Z' OR last_telegram_success<>'2000-01-01T00:00:00Z') THEN
 RAISE EXCEPTION 'suppression_fabricated_successful_delivery_or_neural_run'; END IF;
END $$;
ROLLBACK;
SELECT 'Suppressed reminders do not fabricate successful neural or Telegram health' AS result;
