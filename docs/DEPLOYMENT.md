# Deployment and activation

## Текущее hosted-состояние — 2026-10-17

Семь миграций реально применены, legacy hashes сохранены; новый защищённый webhook
и Cloudflare Supabase-mode preview размещены. Реальные test-chat send/edit и
FlyWire/Storage проверки прошли. Production и основной scheduler выключены;
owner Auth/sign-in и manual completion на main ещё не проверены.
Актуальные доказательства: [HOSTED_RELEASE_VERIFICATION.md](HOSTED_RELEASE_VERIFICATION.md).
Нижележащие отчёты от предыдущих сессий являются историей, а не текущими blockers.

The existing Canvas-pusher project is the authorized target, ref
`irjasmzytjeohwfpdnrl` (ap-northeast-2). Do not create another Supabase project or
touch Network Media. Hosted test resources are deployed; recurring production
notifications are not active. See the current evidence linked above.

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

## Supabase existing-project rollout

1. Confirm CLI/MCP project ref `irjasmzytjeohwfpdnrl` and migration history. The
   seven reviewed migrations0000–0006 are already applied. Never reset or replay
   seed/import operations over existing records. Original336/32/14row hashes were
   preserved; six additional test grades remain scoped to the test chat.
2. Preserve the encrypted verified backup and its separate key. The additional
   pre-release configuration/source archive is encrypted too; secrets and later
   Storage objects are separate from that snapshot. See ROLLBACK.md.
3. Owner runs `PYTHONPATH=. .venv/neural/bin/python -m src.flymind.owner_setup`
   in their own terminal to enter email/chosen password privately. It binds the
   already verified test account only. Public signup is disabled; the preview
   uses password sign-in without URL tokens and keeps sessions only in memory.
4. Validate actual owner sign-in/private replay at the deployed preview. Hosted
   SQL owner/foreign/anonymous tests and anonymous HTTP denial already passed,
   but are not substitutes for this owner session test.
5. Test account silent bootstrap already succeeded:113snapshots/20assignments,
   zero historical events. Production account must be bound separately to the
   verified private chat and silently bootstrapped before any delivery activation.
6. Keep server secrets in GitHub/Supabase secret stores. Browser gets project URL
   and publishable/anon key only. No client-supplied chat ID authorizes records.

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
Feature-branch CI and manual validation do not activate its cron. The owner has conditionally authorized merge after code/security/integration
gates; PR1 currently remains open while owner Auth/replay is pending. GitHub schedules can
be late/dropped and public repository schedules can disable after 60 days inactivity.

## Telegram webhook

The new isolated `flymind-telegram-webhook` is deployed in the SAME existing
project. Its bot secrets are FLYMIND_TELEGRAM_BOT_TOKEN,
FLYMIND_TELEGRAM_WEBHOOK_SECRET,FLYMIND_TELEGRAM_BOT_ID,
FLYMIND_TELEGRAM_CHAT_ID,FLYMIND_TELEGRAM_USER_ID. It uses automatically injected
SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY. Never overwrite the legacy shared bot
keys just to configure the new function. FLYMIND_OBSERVATORY_URL points to the
actual preview; FLYMIND_MANUAL_SYNC_ENABLED=false until workflow gates pass.

FLYMIND_GITHUB_PAT may provide a narrowly scoped dispatch credential; otherwise
the existing server-side GITHUB_PAT is reused in place. Its dispatch rights have
not yet been validated through a successful /check. Do not copy a broader local
CLI OAuth token into Edge secrets as a silent substitute.

Telegram setWebhook and commands are already configured for the verified test
group. Gateway JWT verification is disabled because Telegram cannot send it;
the application validates exact secret header/bot/user/chat. The old
telegram-webhook has been replaced with the secure handler but deliberately lacks
its required legacy secret/actor settings, so it fails closed503. Do not restore
its insecure old source. The replacement source is backed up encrypted.

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

Actual authenticated Pages project: `flymind-observatory`. To update the preview
after building with Supabase mode and scanning the bundle:
`cd dashboard && npx wrangler pages deploy dist --project-name flymind-observatory --branch flymind-preview`.
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

## Remaining activation gates

Canvas token rotation and Cloudflare OAuth are complete. Read-only cloud run
39043798824 passed; controlled two-scan test-chat runs39044400161/39044657067
passed, including a real cloud neural event/upload. Current preview:
https://flymind-preview.flymind-observatory.pages.dev

Owner Auth provisioning and actual authenticated private browser replay remain
pending. Use the private terminal command above, then sign in. Next verify reviewed
main/default-branch manual completion, repeated test /check results, and controlled
primary-account rollout. Never claim workflow_dispatch acceptance means completion.

The existing scanner workflow is disabled_inactivity. Keep it disabled until migration,
bootstrap and target gates pass. After owner-reviewed merge, explicitly configure all
variables, enable CANVAS_WORKER_ENABLED, then re-enable the scanner workflow. Setting
FLYMIND_ENABLED=false selects legacy behavior; DELIVERY_MODE is a FlyMind switch and
does not secure legacy code by itself. The master workflow gate prevents accidental
legacy execution with empty repository variables.

Retention is prepared in flymind-maintenance.yml: weekly 30-day cleanup only when
FLYMIND_ENABLED and FLYMIND_RETENTION_ENABLED are true. Manual dispatch defaults to
dry-run. Review candidates before enabling the flag; it was not enabled here.

The Telegram product extension requires migration0006 and explicit bot/user binding.
See TELEGRAM_ASSISTANT.md for private token entry, test-chat discovery, command/webhook
configuration and the default-branch dependency of workflow_run completion.
