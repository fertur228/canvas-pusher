BEGIN;
DO $$ DECLARE a uuid='00000000-0000-0000-0000-000000000001'; t uuid=gen_random_uuid(); BEGIN
 IF has_function_privilege('anon','public.flymind_schedule_claim(uuid,uuid)','execute') OR has_function_privilege('authenticated','public.flymind_schedule_claim(uuid,uuid)','execute') THEN RAISE EXCEPTION 'browser_scheduler_rpc'; END IF;
 IF has_table_privilege('authenticated','public.flymind_schedule_ticks','select') OR has_table_privilege('anon','public.flymind_schedule_ticks','select') THEN RAISE EXCEPTION 'browser_scheduler_ledger'; END IF;
 UPDATE public.flymind_accounts SET enabled=true,initialized_at=now() WHERE id=a;
 IF NOT public.flymind_schedule_claim(a,t) OR public.flymind_schedule_claim(a,t) OR public.flymind_schedule_claim(a,gen_random_uuid()) THEN RAISE EXCEPTION 'nonexclusive_tick'; END IF;
 UPDATE public.flymind_schedule_ticks SET state='ambiguous' WHERE tick=t;
 IF public.flymind_schedule_claim(a,gen_random_uuid()) THEN RAISE EXCEPTION 'uncertain_tick_retried'; END IF;
 UPDATE public.flymind_schedule_ticks SET created_at=now()-interval '5 minutes' WHERE tick=t;
 IF public.flymind_schedule_claim(a,t) OR NOT public.flymind_schedule_claim(a,gen_random_uuid()) THEN RAISE EXCEPTION 'new_tick_or_replay'; END IF;
END $$;
ROLLBACK;
