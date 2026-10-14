BEGIN;
-- Synthetic fixtures only. All legacy tests above remain in place.
UPDATE public.flymind_jobs SET state='done';
DO $$ DECLARE a uuid='00000000-0000-0000-0000-000000000001'; v jsonb; r jsonb; stamp timestamptz; id uuid; e jsonb; BEGIN
 IF has_function_privilege('service_role','public.flymind_webhook_claim(bigint,bigint)','execute') THEN RAISE EXCEPTION 'unscoped_legacy_webhook_grant'; END IF;
 IF public.flymind_deadlines(a)->>'synced_at' IS NOT NULL THEN RAISE EXCEPTION 'unsynced_claimed_empty'; END IF;
 PERFORM public.flymind_bind_bot(a,101,123,123);
 IF NOT public.flymind_webhook_claim(101,123,123,42) OR public.flymind_webhook_claim(101,123,123,42) OR public.flymind_webhook_claim(101,123,999,43) THEN RAISE EXCEPTION 'bot_scope_or_actor'; END IF;
 PERFORM public.flymind_bind_bot(a,102,123,123);
 IF NOT public.flymind_webhook_claim(102,123,123,42) OR public.flymind_webhook_claim(101,123,123,44) THEN RAISE EXCEPTION 'replacement_bot_update_collision'; END IF;
 IF NOT EXISTS(SELECT 1 FROM public.flymind_experiments WHERE account_id=a) THEN RAISE EXCEPTION 'rotation_lost_history'; END IF;
 INSERT INTO public.flymind_snapshots(account_id,kind,entity_key,state_data)
 SELECT a,'assignment','test:'||n,jsonb_build_object('id',n,'name','SYNTHETIC '||n,'course_name','SYNTHETIC','has_submitted',n=7,'score',95,'due_at',CASE n WHEN 1 THEN '2026-10-14T18:00:00Z' WHEN 2 THEN '2026-10-14T18:45:00Z' WHEN 3 THEN '2026-10-14T19:15:00Z' WHEN 4 THEN '2026-10-20T00:00:00Z' WHEN 5 THEN NULL WHEN 6 THEN 'broken' ELSE '2026-10-14T18:50:00Z' END)
 FROM generate_series(1,7) n;
 stamp=public.flymind_sync_verified(a,ARRAY['test:1','test:2','test:3','test:4','test:5','test:6','test:7']);
 v=public.flymind_deadlines(a,'today',0,'2026-10-14T18:30:00Z');
 IF (v->>'total')::int<>2 OR v->'rows'->0->>'id'<>'1' OR v->'rows'->1->>'id'<>'2' THEN RAISE EXCEPTION 'timezone_or_order_or_grade_as_submission'; END IF;
 v=public.flymind_deadlines(a,'overdue',0,'2026-10-14T18:30:00Z');
 IF (v->>'total')::int<>1 THEN RAISE EXCEPTION 'overdue'; END IF;
 v=public.flymind_deadlines(a,'all',1,'2026-10-14T18:30:00Z');
 IF (v->>'total')::int<>5 OR jsonb_array_length(v->'rows')<>2 OR v->'rows'->1->>'id'<>'5' OR (v->>'invalid_deadlines')::int<>1 THEN RAISE EXCEPTION 'pagination_or_null_date'; END IF;
 IF (public.flymind_deadlines(a,'week',0,'2026-10-14T18:30:00Z')->>'total')::int<>3 THEN RAISE EXCEPTION 'week'; END IF;
 IF (public.flymind_deadlines(a,'month',0,'2026-10-14T18:30:00Z')->>'total')::int<>3 THEN RAISE EXCEPTION 'month'; END IF;
 IF (public.flymind_deadlines(a,'undated',0,'2026-10-14T18:30:00Z')->>'total')::int<>1 THEN RAISE EXCEPTION 'undated'; END IF;
 UPDATE public.flymind_snapshots SET state_data=state_data||'{"name":"partial failed update"}' WHERE account_id=a AND entity_key='test:1';
 IF public.flymind_deadlines(a,'overdue',0,'2026-10-14T18:30:00Z')->'rows'->0->>'name'<>'SYNTHETIC 1' THEN RAISE EXCEPTION 'partial_snapshot_leaked'; END IF;
 IF NOT (public.flymind_deadlines(a,'all',0,stamp+interval '31 minutes')->>'stale')::boolean THEN RAISE EXCEPTION 'stale_not_flagged'; END IF;
 r=public.flymind_manual_request(a,102,90,'feat/flymind-neural-poc');id=(r->>'id')::uuid;
 IF NOT (r->>'accepted')::boolean OR (public.flymind_manual_request(a,102,91,'feat/flymind-neural-poc')->>'accepted')::boolean THEN RAISE EXCEPTION 'duplicate_dispatch'; END IF;
 IF public.flymind_manual_start(a,id,'444','main') THEN RAISE EXCEPTION 'wrong_branch'; END IF;
 IF NOT public.flymind_manual_start(a,id,'444','feat/flymind-neural-poc') OR public.flymind_manual_start(a,id,'445','feat/flymind-neural-poc') THEN RAISE EXCEPTION 'duplicate_execution'; END IF;
 PERFORM public.flymind_manual_prepare(a,id,'444','{"sync_status":"verified","errors":0}');
 IF (SELECT state FROM public.flymind_manual_requests WHERE run_id='444')<>'running' THEN RAISE EXCEPTION 'premature_completion'; END IF;
 e=jsonb_build_object('event_id',repeat('d',64),'account_id',a,'entity_type','report','kind','health_report','schema_version',1,'entity_key','0:'||id,'observed_at',now(),'revision',1,'priority',1,'payload',jsonb_build_object('id',id),'changes','{}'::jsonb);
 IF NOT public.flymind_manual_complete(a,id,'444','success',e) OR public.flymind_manual_complete(a,id,'444','success',e) THEN RAISE EXCEPTION 'completion_idempotency'; END IF;
 IF (SELECT count(*) FROM public.flymind_jobs WHERE event_id=repeat('d',64))<>1 THEN RAISE EXCEPTION 'completion_outbox'; END IF;
 IF public.flymind_claim_report(a,repeat('d',64)) IS NULL OR public.flymind_claim_report(a,repeat('d',64)) IS NOT NULL THEN RAISE EXCEPTION 'completion_claim_not_exclusive'; END IF;
 IF public.flymind_manual_request(a,102,92,'feat/flymind-neural-poc')->>'state'<>'cooldown' THEN RAISE EXCEPTION 'cooldown'; END IF;
END $$;
SET LOCAL ROLE authenticated;
SET LOCAL request.jwt.claim.sub='10000000-0000-0000-0000-000000000002';
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM public.flymind_manual_requests) THEN RAISE EXCEPTION 'foreign_manual_request_leak'; END IF;
 BEGIN PERFORM public.flymind_deadlines('00000000-0000-0000-0000-000000000001'); RAISE EXCEPTION 'browser_worker_rpc'; EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN PERFORM * FROM public.flymind_snapshots; RAISE EXCEPTION 'foreign_snapshots'; EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
SET LOCAL ROLE anon;
DO $$ BEGIN
 BEGIN PERFORM public.flymind_bind_bot('00000000-0000-0000-0000-000000000001',555,123,123); RAISE EXCEPTION 'anonymous_rotation'; EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
ROLLBACK;
SELECT 'Assistant bot namespaces, verified deadlines, manual lifecycle and RLS passed' AS result;
