-- Additive fallback timer ledger. No existing academic or delivery state is changed.
BEGIN;
CREATE TABLE public.flymind_schedule_ticks (
 tick uuid PRIMARY KEY,
 account_id uuid NOT NULL REFERENCES public.flymind_accounts(id),
 created_at timestamptz NOT NULL DEFAULT now(),
 state text NOT NULL DEFAULT 'claimed' CHECK(state IN ('claimed','accepted','ambiguous','skipped','failed','dry_run')),
 reason text CHECK(length(reason)<=80)
);
CREATE INDEX flymind_schedule_ticks_account_time ON public.flymind_schedule_ticks(account_id,created_at DESC);
ALTER TABLE public.flymind_schedule_ticks ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.flymind_schedule_ticks FROM PUBLIC,anon,authenticated;
GRANT SELECT,UPDATE ON public.flymind_schedule_ticks TO service_role;

CREATE FUNCTION public.flymind_schedule_claim(p_account uuid,p_tick uuid) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
BEGIN
 -- Serialize claims across Edge isolates. A lost dispatch response is never resent.
 PERFORM pg_advisory_xact_lock(hashtextextended('flymind_schedule:'||p_account::text,0));
 IF NOT EXISTS(SELECT 1 FROM public.flymind_accounts WHERE id=p_account AND enabled AND initialized_at IS NOT NULL)
 THEN RAISE EXCEPTION 'account_not_ready'; END IF;
 IF EXISTS(SELECT 1 FROM public.flymind_schedule_ticks WHERE tick=p_tick) OR EXISTS(
  SELECT 1 FROM public.flymind_schedule_ticks WHERE account_id=p_account
  AND created_at>now()-interval '4 minutes' AND state IN ('claimed','accepted','ambiguous'))
 THEN RETURN false; END IF;
 INSERT INTO public.flymind_schedule_ticks(tick,account_id) VALUES(p_tick,p_account);
 RETURN true;
END $$;
REVOKE ALL ON FUNCTION public.flymind_schedule_claim(uuid,uuid) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.flymind_schedule_claim(uuid,uuid) TO service_role;
COMMIT;
