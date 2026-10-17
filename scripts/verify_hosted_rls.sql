-- Scoped to the verified Canvas-pusher schema; all fixture changes ROLLBACK.
-- SQL role tests, not evidence of the human owner's Auth sign-in.
BEGIN;
SET LOCAL statement_timeout='30s';
CREATE TEMP TABLE flymind_rls_expected AS
SELECT user_id,gen_random_uuid() AS owner_id,
(SELECT count(*) FROM public.canvas_state c WHERE c.user_id=u.user_id) AS canvas_n,
(SELECT count(*) FROM public.course_grades g WHERE g.user_id=u.user_id) AS grades_n,
(SELECT count(*) FROM public.health_checks h WHERE h.user_id=u.user_id) AS health_n
FROM (SELECT DISTINCT user_id FROM public.canvas_state) u;
INSERT INTO auth.users(id) SELECT owner_id FROM flymind_rls_expected;
INSERT INTO public.flymind_accounts(telegram_chat_id,canvas_origin,owner_id,enabled)
SELECT user_id,'https://canvas.invalid',owner_id,true FROM flymind_rls_expected;
DO $$ DECLARE r record; n bigint; BEGIN
FOR r IN SELECT * FROM flymind_rls_expected LOOP
 PERFORM set_config('request.jwt.claim.sub',r.owner_id::text,true);
 SET LOCAL ROLE authenticated;
 SELECT count(*) INTO n FROM public.canvas_state;
 IF n<>r.canvas_n THEN RAISE EXCEPTION 'canvas_owner_scope'; END IF;
 SELECT count(*) INTO n FROM public.course_grades;
 IF n<>r.grades_n THEN RAISE EXCEPTION 'grades_owner_scope'; END IF;
 SELECT count(*) INTO n FROM public.health_checks;
 IF n<>r.health_n THEN RAISE EXCEPTION 'health_owner_scope'; END IF;
 IF (SELECT count(*) FROM public.flymind_accounts)<>1 THEN RAISE EXCEPTION 'account_owner_scope'; END IF;
 IF EXISTS(SELECT 1 FROM storage.objects WHERE bucket_id='flymind-private') THEN RAISE EXCEPTION 'foreign_storage_leak'; END IF;
 IF EXISTS(SELECT 1 FROM public.flymind_experiments) THEN RAISE EXCEPTION 'foreign_experiment_leak'; END IF;
 RESET ROLE;
END LOOP;
END $$;
DO $$ DECLARE uid uuid=gen_random_uuid(); n bigint; expected_n bigint; expected_experiments bigint; BEGIN
 INSERT INTO auth.users(id) VALUES(uid);
 -- Only the currently owner-unmapped TEST account. Nothing persists.
 UPDATE public.flymind_accounts SET owner_id=uid WHERE owner_id IS NULL AND telegram_chat_id<0;
 SELECT count(*) INTO expected_n FROM storage.objects WHERE bucket_id='flymind-private';
 SELECT count(*) INTO expected_experiments FROM public.flymind_experiments;
 PERFORM set_config('request.jwt.claim.sub',uid::text,true);
 SET LOCAL ROLE authenticated;
 SELECT count(*) INTO n FROM storage.objects WHERE bucket_id='flymind-private';
 IF n<>expected_n OR n=0 THEN RAISE EXCEPTION 'test_storage_owner_scope'; END IF;
 IF (SELECT count(*) FROM public.flymind_experiments)<>expected_experiments OR expected_experiments=0 THEN RAISE EXCEPTION 'test_experiment_owner_scope'; END IF;
 BEGIN PERFORM public.flymind_claim(gen_random_uuid(),'send'); RAISE EXCEPTION 'worker_rpc_browser_leak'; EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 RESET ROLE;
 PERFORM set_config('request.jwt.claim.sub',gen_random_uuid()::text,true);
 SET LOCAL ROLE authenticated;
 IF EXISTS(SELECT 1 FROM public.canvas_state) OR EXISTS(SELECT 1 FROM public.flymind_accounts) OR EXISTS(SELECT 1 FROM public.flymind_experiments) THEN RAISE EXCEPTION 'unmapped_user_leak'; END IF;
 RESET ROLE;
END $$;
SELECT set_config('request.jwt.claim.sub','',true);
SET LOCAL ROLE anon;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM storage.objects WHERE bucket_id='flymind-private') THEN RAISE EXCEPTION 'anonymous_storage_leak'; END IF;
 BEGIN PERFORM * FROM public.canvas_state; RAISE EXCEPTION 'anonymous_canvas_leak'; EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
RESET ROLE;
ROLLBACK;
SELECT json_build_object('hosted_sql_owner_isolation',true,'fixtures_rolled_back',true,'actual_owner_login_tested',false) AS result;
