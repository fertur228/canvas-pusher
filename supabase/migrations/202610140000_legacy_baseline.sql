-- Safe fresh-staging baseline; existing legacy tables/data remain untouched.
BEGIN;
CREATE TABLE IF NOT EXISTS public.canvas_state (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),user_id bigint NOT NULL,course_id bigint NOT NULL,
 course_name varchar(255),object_type varchar(50) NOT NULL,object_id bigint NOT NULL,state_data jsonb NOT NULL,
 last_reminder_type varchar(50),created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS canvas_state_unique_idx ON public.canvas_state(user_id,object_type,object_id);
CREATE TABLE IF NOT EXISTS public.course_grades (
 user_id bigint NOT NULL,course_id bigint NOT NULL,course_name varchar(255) NOT NULL,current_score decimal(5,2),
 updated_at timestamptz NOT NULL DEFAULT now(),PRIMARY KEY(user_id,course_id)
);
CREATE TABLE IF NOT EXISTS public.health_checks (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),user_id bigint NOT NULL,total_changes integer DEFAULT 0,
 total_errors integer DEFAULT 0,created_at timestamptz NOT NULL DEFAULT now()
);
COMMIT;
