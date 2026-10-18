-- PREPARED ONLY: close legacy Canvas table access before activating private integration.
-- Worker and existing webhook service-role access remain available. No rows/columns changed.
BEGIN;
DO $$ DECLARE name text; BEGIN
 FOREACH name IN ARRAY ARRAY['canvas_state','course_grades','health_checks'] LOOP
   IF to_regclass('public.'||name) IS NOT NULL THEN
     EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',name);
     EXECUTE format('REVOKE ALL ON public.%I FROM PUBLIC,anon,authenticated',name);
     EXECUTE format('GRANT ALL ON public.%I TO service_role',name);
     EXECUTE format('GRANT SELECT ON public.%I TO authenticated',name);
     -- Restrictive guard also denies rows if an old permissive policy was broad.
     EXECUTE format('CREATE POLICY flymind_legacy_owner_guard ON public.%I AS RESTRICTIVE FOR SELECT TO authenticated USING(EXISTS(SELECT 1 FROM public.flymind_accounts a WHERE a.telegram_chat_id=user_id AND a.owner_id=auth.uid()))',name);
     EXECUTE format('CREATE POLICY flymind_legacy_owner_read ON public.%I FOR SELECT TO authenticated USING(EXISTS(SELECT 1 FROM public.flymind_accounts a WHERE a.telegram_chat_id=user_id AND a.owner_id=auth.uid()))',name);
   END IF;
 END LOOP;
END $$;
COMMIT;
