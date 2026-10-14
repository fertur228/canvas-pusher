# Deployment and activation

No hosted FlyMind production resources have been activated by this implementation.
Local isolated Supabase tests and browser mocks are distinct from a hosted staging
or production deployment. Check FINAL_RELEASE_REPORT.md for latest evidence.

## Local setup

Python 3.11: `python3 -m venv .venv/neural`, then
`.venv/neural/bin/pip install -r requirements-neural.lock`.
Frontend: `npm ci --prefix dashboard`; `npm --prefix dashboard run dev`.
Default dashboard is the public scientific local replay, no academic records.
Run tests with `.venv/neural/bin/python -m pytest -q` and
`npm --prefix dashboard test`; `npm --prefix dashboard run build` produces dist.
Browser checks: `npm --prefix dashboard run test:e2e` and `test:e2e:private`.
On Linux install Chrome or set PLAYWRIGHT_CHROME_PATH. Private E2E uses mocked HTTP,
actual neural exports and synthetic academic fixtures.

## Supabase isolated staging first

1. Identify a separate free-tier staging project; do not reuse production implicitly.
2. Review all six `supabase/migrations/20261014000{0..5}_*.sql`. Migration 0000 only
   creates missing legacy tables; 0002 restricts legacy grants without deleting data.
   Audit custom legacy policies/RPCs in the destination before applying.
3. Apply via Supabase CLI migrations against the explicitly linked staging project.
   Never use `db reset` against remote data. Back up first through existing project tools.
4. Create the single owner's Auth user through the administrator dashboard; disable
   public signup. Configure the exact static Observatory origin in Auth URL settings.
   Password sign-in uses no redirect; no callback tokens are accepted in URLs.
5. Insert `flymind_accounts` with UUID, owner_id=auth.users.id, exact Canvas origin,
   separate test chat ID and enabled=true. No client-supplied chat ID authorizes data.
6. Store server credentials only as GitHub Secrets. Browser receives project URL and
   publishable/anon key only. Verify owner/other-user/anonymous Storage and table access.
7. Run the worker explicitly with `FLYMIND_ENABLED=true`, `DELIVERY_MODE=disabled`
   and `python -m src.flymind.worker --bootstrap`. Confirm bootstrapped/zero events.
   Failed/partial bootstrap does not unlock normal processing.

The real local API test is `PYTHONPATH=. python tests/flymind/local_supabase_check.py
--status /private/tmp/flymind-supabase-staging/status.json --output /tmp/result.json`.
It hard-rejects all origins except localhost/127.0.0.1 port55321. Never repoint it to
production. It creates only synthetic isolated records; Telegram is captured.

## GitHub Actions

All reusable actions are SHA-pinned. CI uses Ubuntu24.04/Python3.11/Node22, no secrets,
runs scientific controls and uploads only synthetic scientific summary artifacts.
The existing scanner workflow adds `read_only=true` dispatch for safe real Canvas
schema/pagination checks: only Canvas secrets are supplied to that step.

Secrets: CANVAS_API_URL, CANVAS_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY,
TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID; add TEST_TELEGRAM_CHAT_ID for a distinct test
account. Variables: CANVAS_WORKER_ENABLED=false (master scheduler gate, including legacy mode);
FLYMIND_ACCOUNT_ID; FLYMIND_ENABLED=false initially;
FLYMIND_MODE=shadow; DELIVERY_MODE=disabled; FLYMIND_NEURAL_ENABLED=true;
NEURAL_TELEMETRY_ENABLED=true; FLYMIND_MAX_NEURAL=5;
FLYMIND_PRODUCTION_AUTHORIZED=false. The server validates account/chat/origin binding.

The new 15-minute schedule executes only when the workflow is on the default branch.
Feature-branch CI and manual validation do not activate its cron. The owner must
review/merge the PR; no main merge is performed autonomously. GitHub schedules can
be late/dropped and public repository schedules can disable after 60 days inactivity.

## Telegram webhook

Deploy only to the identified staging project first. Configure TELEGRAM_WEBHOOK_SECRET,
TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_USER_ID (mandatory for group chats),
SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY; optional GITHUB_PAT with narrowly scoped
Actions workflow permission, GITHUB_REPO, FLYMIND_WORKFLOW_REF, OBSERVATORY_URL.
Configure Telegram setWebhook with the **same secret_token** using a secure local
script; never paste token-bearing URLs into public logs. Telegram cannot supply
Supabase JWT, so deploy webhook with JWT verification disabled only after its own
secret validation is configured. No wildcard CORS is needed.

Webhook accounts must be explicitly enabled/mapped. Update IDs are durably claimed
before side effects; claimed/ambiguous operations require review instead of blind
replay. Validate /stats, /start, callbacks and /brain in the separate test chat.
The command keeps grade names HTML-escaped and sends no private content to other actors.

## Cloudflare Pages

Static target, no permanent backend. Build command `npm ci && npm run build`, root
`dashboard`, output `dist`; Node22. `dashboard/wrangler.toml`, `_headers` and
`_redirects` prepare Pages deployment. Assets are immutable; source telemetry is
revalidated; CSP permits self and HTTPS *.supabase.co only. A custom Supabase domain
requires an explicitly reviewed CSP connect-src change.

Local/public research: VITE_OBSERVATORY_DATA_SOURCE=local.
Private: VITE_OBSERVATORY_DATA_SOURCE=supabase, VITE_SUPABASE_URL,
VITE_SUPABASE_PUBLISHABLE_KEY, VITE_DEPLOYMENT_LABEL=staging.
Never define VITE_SUPABASE_SERVICE_KEY or any VITE_* Canvas/Telegram token.

After Cloudflare authentication and naming an isolated project:
`cd dashboard && npx wrangler pages deploy dist --project-name flymind-observatory-staging --branch preview`.
Verify login, foreign/anonymous rejection, private artifact failure states, mobile
layout, browser console and static bundle secret scan. Promote only the tested build
and project; no billing upgrade is required. See ROLLBACK.md.

## Production gates

Require reviewed migrations/backups, owner mapping, test-chat send/edit/idempotency,
real hosted Storage/Auth checks, repeated shadow runs, bounded queues and independent
watchdog. Then set CANVAS_WORKER_ENABLED=true, FLYMIND_ENABLED=true, DELIVERY_MODE=production and
FLYMIND_PRODUCTION_AUTHORIZED=true for the unambiguous authorized production account.
Keep FLYMIND_MODE=shadow first; only then opt into enrich. Production authorization
is a deliberate operational switch, not a claim that biology is validated.

## Verified external access blocker

A Cloudflare OAuth configuration exists locally, but `wrangler whoami --json` failed
with expired credentials after a real network retry. No deployment occurred. Run
`npx wrangler login` interactively or provide a scoped CLOUDFLARE_API_TOKEN and account
ID; then deploy the isolated preview above. The stored login was not replaced.

The real read-only Canvas check on 2026-10-14 returned HTTP401 on its first request.
Replace/renew CANVAS_API_KEY in GitHub Secrets and confirm CANVAS_API_URL, then rerun
`FlyMind controlled Canvas read`. No pagination or real assignment schema was verified
beyond that denied request. Do not confuse this with the successful fixture tests.

The existing scanner workflow is disabled_inactivity. Keep it disabled until migration,
bootstrap and target gates pass. After owner-reviewed merge, explicitly configure all
variables, enable CANVAS_WORKER_ENABLED, then re-enable the scanner workflow. Setting
FLYMIND_ENABLED=false selects legacy behavior; DELIVERY_MODE is a FlyMind switch and
does not secure legacy code by itself. The master workflow gate prevents accidental
legacy execution with empty repository variables.

Retention is prepared in flymind-maintenance.yml: weekly 30-day cleanup only when
FLYMIND_ENABLED and FLYMIND_RETENTION_ENABLED are true. Manual dispatch defaults to
dry-run. Review candidates before enabling the flag; it was not enabled here.
