> Актуально 19 октября 2026: production использует активный Supabase Cron → защищённый Edge → GitHub worker каждые пять минут. Два автоматических цикла проверены; native GitHub `schedule` остаётся отдельным нерешённым ограничением. [Доказательства и итоговый отчёт](FINAL_PRODUCTION_REPORT_20261019.md). Предыдущие инструкции ниже сохраняются как история и общий runbook.

# Operations

The laptop is unnecessary after reviewed default-branch deployment and configuration:
GitHub Actions runs finite workers, Supabase persists state and private artifacts,
Cloudflare serves static assets, Telegram receives notifications. Local dev servers
are not an operational dependency. A feature branch alone does not activate schedules.

## Health and recovery

Observe flymind_health: last attempt, Canvas success, DB success, neural success,
Telegram success, status/error code and queue counts. Timestamps represent actual
completed operations, not a fabricated live stream. New job state transitions enter
flymind_attempts. Pending/failed/ambiguous delivery or failed neural work degrades
health; scanner failures never become healthy empty synchronizations.

Heartbeat age >30 minutes is delayed; >90 minutes failed. The separate GitHub hourly
watchdog exits nonzero without using the notification outbox. Configure GitHub failure
notifications. Optional Supabase Cron watchdog SQL independently marks stale database
state, including when GitHub scheduling stops. The dashboard itself refreshes on user
request; it is not a background monitoring service. Full platform outages cannot be
reliably detected by a monitor on that same platform.

Recovery commands (server credentials only, never browser):

- `python -m src.flymind.maintenance reconcile --job EVENT:send --message-id 123`
  after checking Telegram for the stable event reference.
- `python -m src.flymind.maintenance reconcile --job EVENT:send --confirmed-unsent`
  only after establishing non-delivery. Never guess after a timeout.
- `python -m src.flymind.maintenance retry --job EVENT:simulate` for a reviewed
  terminal failure after fixing dependencies/storage. Dead jobs remain visible.
- Telegram missing credentials leaves unclaimed pending jobs; restore credentials.
- Expired primary lease → ambiguous; simulation/edit leases can be safely retried.
- Webhook update rows remaining claimed indicate interrupted/uncertain command work;
  review side effects manually. A new owner command has a new Telegram update ID.

Known Telegram refusal 429/5xx retries with bounded exponential backoff. Transport
outcomes that could have been accepted are quarantined. Maximum primary/edit attempts
10; neural attempts3. Worker defaults max5 neural jobs, 25 deliveries per drain and
600s total budget; scanner pages100 and parallel requests8. Backlogs need monitoring.

## Retention and cost

`python -m src.flymind.maintenance retention --days 30` is dry-run. To explicitly
expire old artifact references/delete orphan objects, set FLYMIND_RETENTION_ENABLED=true
and add `--apply`. Minimum retention7days. Run manually first, then enable the prepared weekly
flymind-maintenance.yml only in the reviewed environment. Its schedule requires
FLYMIND_RETENTION_ENABLED=true; manual dispatch defaults to dry-run. It does not delete source datasets, baseline experiments,
snapshots, event identities or notification delivery tombstones.

References are expired first; object removal uses orphan candidates older than24h
with no other reference and no pending/running/ambiguous job. Failed removal is
recoverable on next sweep. Shared per-worker artifacts are retained while any newer
association refers to them. Up to100 orphan objects and1000 expired attempt rows per
pass. Student event payloads and snapshots remain private but persist: define a
separate explicit academic-data erasure/export policy before multi-user operation.
No automatic deletion of existing production records is performed by this release.

## Limits

Polling cannot observe changes created and reverted between polls. Announcements
older than30days are outside the scanner window. Initial bootstrap suppresses existing
historical content and the currently crossed reminder band. Future threshold crossings
still notify. A newly added course may contain historical objects; bootstrap that
scope before enabling it when necessary (currently global CLI bootstrap is the provided
operator tool). No deletion inference is made from failed or absent API scopes.

Controlled real Telegram smoke test (when a separate test chat is configured):
`python -m src.flymind.telegram_check --state /private/tmp/flymind-telegram-test.sqlite`.
It persists a fixed synthetic event and message ID, edits the same message and is
idempotent across reruns. Keep the state file to preserve reconciliation evidence.
It refuses a missing test chat or a test chat equal to TELEGRAM_CHAT_ID.

The Telegram test CLI exits nonzero until both send and edit are confirmed. An
ambiguous send remains quarantined across reruns; an exit code of zero is not emitted
for a pending, refused or uncertain test. No actual test-chat credential is configured.

## Telegram assistant extension

Verified deadline snapshots use last_snapshot_success, distinct from successful fetch.
Canvas401/403 or missing credentials block academic backlog release. A requested manual
workflow failure has its own targeted operational outbox report; it never drains unrelated
academic notifications. New bot rotation requires disabled idle workers and explicit
account binding. See TELEGRAM_ASSISTANT.md for commands and recovery details.

## Current hosted test operation (2026-10-17)

See HOSTED_RELEASE_VERIFICATION.md for deployed targets and verified evidence.
`FlyMind controlled hosted test chat` is a finite two-scan smoke test, without cron.
It requires FLYMIND_TEST_CHAT_VALIDATION=true and FLYMIND_TEST_ACCOUNT_ID; validates
that test chat differs from the primary chat and that server-side account/bot
bindings match. Its output/artifact contains counts only. Disable the opt-in after
validation. It does not replace main-branch manual completion or scheduled rollout.

The authenticated owner has not been provisioned yet; don't report Auth login or
private browser replay complete based only on SQL RLS tests/service-role downloads.
Old webhook503 is intentional retirement, not a healthy newbot endpoint. Newbot
endpoint rejects missing/wrong header/user/chat403; its /status reports actual
staleness until further verified scans refresh heartbeat.
