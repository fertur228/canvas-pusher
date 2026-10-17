# Telegram assistant — implementation and secure activation

## Текущее hosted-состояние — 2026-10-17

Семь миграций реально применены, legacy hashes сохранены; новый защищённый webhook
и Cloudflare Supabase-mode preview размещены. Реальные test-chat send/edit и
FlyWire/Storage проверки прошли. Production и основной scheduler выключены;
owner Auth/sign-in и manual completion на main ещё не проверены.
Актуальные доказательства: [HOSTED_RELEASE_VERIFICATION.md](HOSTED_RELEASE_VERIFICATION.md).
Нижележащие отчёты от предыдущих сессий являются историей, а не текущими blockers.

**Status update, 2026-10-17:** the renewed local Canvas credential now passed real
read-only validation; bot/owner/separate-test-chat identities passed getMe checks.
The linked legacy Supabase was audited and backed up with verified local restore.
Hosted migrations, new webhook and delivery remain unactivated. See
[SUPABASE_REMOTE_PREFLIGHT.md](SUPABASE_REMOTE_PREFLIGHT.md) for current evidence;
older activation/evidence statements below describe the implementation handoff.

This is implemented code, not a claim of hosted activation. New bot commands/webhook
have NOT been applied to a real bot. Production remains disabled; no real Telegram
messages were sent. The renewed Canvas token must be installed privately by the owner.

## Commands and navigation

| Command | Persistent reply button | Result |
| --- | --- | --- |
| /start, /menu | Menu navigation | Main menu; does not implicitly send grades |
| /deadlines | 📅 Deadlines | Last verified cached assignment snapshot |
| /check | 🔄 Check Canvas Now | Authenticated, gated tracked GitHub dispatch |
| /stats | 📊 My Grades | Existing grade/GPA view |
| /brain | 🧠 Fly Brain | Saved experimental neural status/Observatory link |
| /status | ⚙️ System Status | Heartbeat, successful snapshots, queues, manual request state |

The official Bot API `setMyCommands` and `setChatMenuButton` are invoked by the
local configuration tool; the persistent ReplyKeyboardMarkup is sent on /start.
Every command and callback requires webhook secret, exact Telegram user, chat,
enabled account and matching bot identity. Menu visibility is not authorization.

## Verified deadlines

Migration 0006 adds verified_data/verified_at to flymind_snapshots and
last_snapshot_success to flymind_health. The worker publishes a verified assignment
list only after a complete scan and persistence without errors. Changed partial
snapshots cannot replace the previously verified list. Empty successful scans are
valid; absence of any successful sync explicitly says not synchronized yet.

Views: upcoming, overdue, today in Asia/Almaty, next 7/30 days, all unsubmitted
(including undated last), and a separate undated view. PostgreSQL sorts and pages
three assignments at a time. Each response includes the successful sync timestamp;
older than 30 minutes is flagged stale. Malformed dates are counted and excluded
from dated lists. History for absent/inactive-course objects is retained but is
excluded from the latest verified list. No neural simulator runs for these reads.

Submission is derived from submitted_at or submitted/pending_review workflow state,
never from the score alone. Canvas's effective per-user due_at is requested with
`override_assignment_dates=true`; the bot does not merge other students' overrides.
API-provided same-origin HTTPS html_url is retained. Cards show course, title, due,
time remaining, unsubmitted state, points and a safe link. Fields are escaped and
bounded before HTML assembly; optional oversized/invalid links are omitted.

## Tracked manual synchronization

1. Webhook authenticates owner and bot, then verifies GitHub access, active workflow,
   selected branch's upgraded manual entry point, completion workflow and repository
   variables CANVAS_WORKER_ENABLED/FLYMIND_ENABLED/account/delivery authorization.
2. A PostgreSQL account lock serializes request creation. An active request/worker
   prevents another dispatch; cooldown is 60 seconds. The request UUID is durable.
3. GitHub accepts workflow_dispatch with manual_request_id. The bot says **queued**,
   not completed. Lost dispatch responses become uncertain and are not blindly retried.
4. Worker claims that UUID once, validates branch, account and bot, executes the normal
   scanner/outbox and stores counters. This alone does not mark completion.
5. `flymind-manual-completion.yml` handles the actual `workflow_run: completed` event.
   It executes trusted default-branch code, rejects foreign repositories/branches,
   never executes run artifacts, and atomically stores status plus a completion outbox
   event. It sends only that operational report, not an unrelated academic backlog.
6. Completion reports last successful check, new assignments, deadline/grade changes,
   errors and a Deadlines button. Failures remain visible through /status and outbox.

Requests waiting >30 minutes expire when a new request is considered; a late old worker
cannot execute them. Repeated finalizer execution uses the same event identity. A
lost Telegram send acknowledgement stays ambiguous and requires reconciliation.
GitHub scheduling and dispatch latency are best effort. A failed finalizer/database
outage can leave a request running: rerun the completion workflow after repair;
never mark it completed just because GitHub accepted dispatch.

**Deployment dependency:** workflow_run handlers must exist on the default branch.
The unmerged feature branch cannot promise full on-demand operation. Until owner
review/merge (or an isolated staging repo with this code on its default branch), the
webhook returns an accurate configuration error. No legacy worker fallback is used.
The 5-minute scheduled scanner remains guarded by CANVAS_WORKER_ENABLED.

## Bot replacement and private credentials

Never put tokens into AI chat, shell arguments, Git, PR bodies or public logs.
Use a local terminal in the repo. Commands below use a Python environment with the
pinned core requirements installed. Files beginning `.env.` are ignored by Git.

### 1. Pause and preserve

Keep Canvas State Tracker disabled and wait for all in-flight runs to finish. Pause
other senders/pollers. Keep the same production FlyMind account UUID to preserve its
snapshots/events/experiments. Resolve active/ambiguous jobs before rotation; do not
clear tables to start again. Existing source datasets remain untouched.

### 2. Enter new tokens locally

```sh
.venv/neural/bin/python -m src.flymind.bot_setup credentials
.venv/neural/bin/python -m src.flymind.bot_setup preflight
```

`credentials` uses hidden terminal input for Canvas and bot tokens, generates a webhook
secret and exclusively creates `.env.flymind.local` with mode0600. It never overwrites
an existing file. `preflight` loads it, performs read-only Canvas checks and prints
only sanitized status/counts. Existing process environment takes precedence: unset
old exported values first if they would override the new local file.

### 3. Discover owner and separate test chat

```sh
.venv/neural/bin/python -m src.flymind.bot_setup discover
.venv/neural/bin/python -m src.flymind.bot_setup discover --test-chat --output .env.flymind.test
```

First send the displayed `/start RANDOM_CHALLENGE` in your private conversation with
the new bot. Numeric bot/user/chat IDs are saved to `.env.flymind.identity` (0600).
Then add the bot to a separate test group and send the second challenge there from
the same verified owner. Its IDs go to `.env.flymind.test`. An arbitrary first /start
cannot take ownership. Discovery refuses to poll if a webhook is active; it never
silently deletes a webhook. Stop polling before configuring the webhook.

### 4. Hosted staging database and Edge Function

Identify a separate staging project. Apply migrations0000–0006, create the owner Auth
user and enabled FlyMind staging account with exact Canvas origin/owner UUID. Do not
reset existing production data. Put its SUPABASE_URL, SUPABASE_SERVICE_KEY and
FLYMIND_ACCOUNT_ID in a separate private local env file. Set FLYMIND_TARGET_ENV=staging.
Use the test identity to bind the bot, user and group to that account:

```sh
.venv/neural/bin/python -m src.flymind.bot_setup --env-file .env.flymind.staging --identity .env.flymind.test bind-staging --apply
```

The staging env must also contain the new TELEGRAM_BOT_TOKEN. The binding RPC refuses
active jobs/manual requests and never deletes academic records. Existing webhook
update rows remain under bot namespace0; new updates use (bot_id,update_id), so reused
update numbers do not collide. Old/unknown-bot message IDs are never edited by the
new bot. Pending sends remain idempotent; ambiguous sends still need reconciliation.

Deploy the updated Edge Function to staging with its own JWT verification disabled
only when the webhook secret is configured. Edge secrets: SUPABASE_URL,
SUPABASE_SERVICE_ROLE_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (test group),
TELEGRAM_USER_ID (owner), TELEGRAM_WEBHOOK_SECRET. Also set OBSERVATORY_URL if available.
For manual refresh: GITHUB_PAT, GITHUB_REPO, FLYMIND_WORKFLOW_REF and
FLYMIND_MANUAL_SYNC_ENABLED=true. GitHub credential needs Actions read/write, Contents
read and repository Variables read; no bot token belongs in browser configuration.

Provision those values privately through the Supabase dashboard or a separate ignored
`.env.flymind.webhook` passed to `supabase secrets set --env-file ... --project-ref ...`.
Do not upload the whole local credential file (Canvas token is not needed by webhook).
The webhook secret must match the one passed to setWebhook below.

```sh
.venv/neural/bin/python -m src.flymind.bot_setup --identity .env.flymind.test configure --webhook-url https://STAGING_PROJECT.supabase.co/functions/v1/telegram-webhook --apply
```

This configures commands and webhook with secret_token, preserves pending updates,
checks getWebhookInfo URL and refuses a different existing URL unless explicitly
passed --replace-webhook. The same bot cannot have both staging and production
webhooks simultaneously. Use a separate staging bot if simultaneous environments are
needed. An actual owner command is still required to verify secret-header delivery.

### 5. Publish rotated GitHub secrets safely

```sh
.venv/neural/bin/python -m src.flymind.bot_setup publish-github --repo fertur228/canvas-pusher --apply
```

This requires successful Canvas preflight, matching bot/identity, a separate test chat,
and a disabled idle scanner workflow. Values go to `gh secret set` over stdin, never
command-line arguments. It sets Canvas/new bot/owner/test/webhook secrets; it does not
change Supabase destination, variables, merge code or enable scheduling. Failure can
leave a partially updated set: keep the scanner disabled, repair and rerun.

For staging, configure Supabase GitHub Secrets to that explicitly selected staging
project and FLYMIND_ACCOUNT_ID to its account. Set FLYMIND_ENABLED=true,
DELIVERY_MODE=test, FLYMIND_MODE=shadow, FLYMIND_PRODUCTION_AUTHORIZED=false. Complete
silent bootstrap with the test group binding and verify the hosted flow before
production. CANVAS_WORKER_ENABLED stays false until ready to execute staging jobs.

### 6. Production gate

After owner-approved merge/default-branch deployment and passing hosted test-chat
send/edit/repeat/failure checks: pause again, select the reviewed production project,
apply migrations and bind the SAME production account UUID via flymind_bind_bot using
verified getMe bot ID, owner user ID and authorized primary chat. Do not use the
staging-only CLI to bypass this deliberate production binding. Bootstrap if needed.
Switch webhook to production explicitly, retain the same secret on both sides, verify
owner-only access, then enable worker+production authorization in shadow mode first.
Only then enable enrich if desired. Revoke the old bot token after migration; never
reuse its message IDs. Read ROLLBACK.md before activation.

## Evidence and boundaries

Automated Python, Deno, SQL, TypeScript/frontend and CI checks are recorded in
telegram-assistant-validation.json and DELIVERY_PROGRESS.md. Deno uses mocked HTTP;
SQL runs a real isolated PostgreSQL16. The renewed credential was not available to
the agent. Actual read-only GitHub run38570459817 still returned401 with the previously
configured secret; GitHub reported its last update in March2026. No real bot setup,
commands, webhook, Telegram messages or hosted migrations were performed.

Official references: [Telegram Bot API](https://core.telegram.org/bots/api),
[GitHub workflow dispatch](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event),
[Canvas assignments](https://developerdocs.instructure.com/services/canvas/resources/assignments).

## Owner-local Auth setup after the hosted test release

Run `PYTHONPATH=. .venv/neural/bin/python -m src.flymind.owner_setup` yourself in
the repository terminal. Email/password are entered locally (password hidden);
never paste them into AI chat. It provisions the explicitly supplied owner through
admin Auth, verifies password sign-in, then binds only the separately verified
test account. It neither rotates an existing password nor changes production flags.
The resulting `.env.flymind.owner` contains UUID/email, not the password.
Open the actual preview and sign in to complete the remaining browser replay gate.


## Mandatory notification contract — 2026-10-17

The FlyMind outbox path (`FLYMIND_ENABLED=true`, explicit delivery gates) creates
one assignment-created event immediately on discovery, even with no/far/near due
 date or zero/unknown points. Initial `--bootstrap` stays silent. Primary sends are
drained before neural work, including batches larger than25; up to1000 attempts
and the10min worker budget bound a run. Outages/Telegram rate limits can postpone
actual delivery, but never postpone event creation until a reminder threshold.

Reminder thresholds are exactly24/12/6/3/1hours, future unsubmitted work only.
The existing snapshot JSONB `reminders` array stores backward-compatible due:band
consumption strings plus `deadline-version:v2:` and `reminder-audit:v2:` strings.
Audit reasons: `queued` (outbox, not delivery), `skipped_late`,
`covered_by_creation`, `covered_by_deadline_change`, `silent_bootstrap`,
`submitted`, `expired`. Delivery truth stays in jobs/message IDs. This requires
NO new snapshot columns and does not rewrite old academic data. Separately,
`202610170007_flymind_suppressed_health.sql` corrects the existing audit trigger
function: a suppressed auxiliary job must not advance last_neural_success. It
changes no rows, schemas, policies or grants at migration time.

A scan at4h for a newly discovered assignment sends creation only, consumes24/12/6,
then3h and1h can fire later. A delayed scan from>24h to2h sends only3h and records
24/12/6 skipped. Submitted/undated/expired work gets no new reminder. The overdue
cached deadline view remains available; there is no additional overdue alert.
A changed timestamp sends its own notification and covers the current band; later
bands use a new deadline revision, including a genuine return to an old due date.
Equivalent UTC/offset timestamp spellings do not reset this revision.

Before every reminder send/retry, reload the snapshot and verify submission, due
version and current band. Old queued bands are suppressed, never sent in a burst.
If the database cannot verify the snapshot, retry without sending. No API can
retract a send already in flight; global scanner concurrency serializes supported
cloud runs, while CAS/outbox leases prevent duplicate commits/claims. Canvas
changes become known only after the next successful fetch.

Ordinary messages use🆕/⏰/📌/📚/📅/💯, escaped titles, Almaty time, remaining time,
submission status and safe Canvas links. No event IDs, GF spike counts or pending
simulation diagnostics. Optional enrichment retains an explicitly experimental,
biologically unvalidated indicator. Neural failure never blocks the base message.

Finite hosted test: `python -m src.flymind.deadline_validation --output /tmp/flymind-deadline-cloud.json`
with the existing guarded test-chat environment. Stable synthetic IDs and a
persisted checkpoint prevent repeat sends; do not delete those records to rerun.
The controlled hosted workflow runs this exercise only behind
`FLYMIND_TEST_CHAT_VALIDATION=true`; primary scheduler gates stay off.
