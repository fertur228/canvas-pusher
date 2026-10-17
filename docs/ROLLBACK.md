# Rollback

0. Set repository variable CANVAS_WORKER_ENABLED=false to stop the whole scheduled
   scanner, including legacy mode. Disable retention separately if needed.
1. Set FLYMIND_MODE=shadow to stop enrichment edits while preserving durable primary
   notifications and scientific recording.
2. Set FLYMIND_NEURAL_ENABLED=false if simulation/dependencies fail. Keep
   FLYMIND_ENABLED=true so the same outbox/snapshot identities remain authoritative.
   Primary delivery does not wait for successful neural processing.
3. Set DELIVERY_MODE=disabled to stop ALL FlyMind deliveries while preserving pending
   jobs. Do not mark uncertain sends unsent or clear the database to restart.
4. Restore the last tested Cloudflare deployment through Pages rollback; local replay
   requires no private credentials. Sign out to clear in-memory private telemetry.
5. Roll back worker code to the last tested feature commit only after checking migration
   compatibility. Additive tables can remain; do not drop or reset production data.

Setting FLYMIND_ENABLED=false returns to the legacy main implementation, which has
separate state and weaker delivery semantics. Do not use that as the routine neural
rollback. Reconcile pending/ambiguous jobs and establish a legacy snapshot baseline
first, or notifications can be duplicated. The old webhook requires no-secret access;
**never** roll back to that insecure handler. Disable webhook or redeploy the secured
version with correctly configured secret instead.

Optional Cron rollback: `SELECT cron.unschedule('flymind-stale-heartbeat');` in the
explicitly selected project. No scheduler/production resource was changed by the
local verification work.

## Actual hosted test release — 2026-10-17

Target Canvas-pusher irjasmzytjeohwfpdnrl only. Seven migrations0000–0006 applied.
Keep data; do not reverse0002 to reopen legacy academic grants. The original
336/32/14records remain hash-identical; six new test grades are separate.

Current production flags are already off. Also set
`FLYMIND_TEST_CHAT_VALIDATION=false` to close the explicit test-only Actions workflow.
To stop newbot replies without touching data, set its namespaced
`FLYMIND_MANUAL_SYNC_ENABLED=false` and disable its test FlyMind account; handler
checks enabled binding before side effects. Do not blindly resend claimed updates
or ambiguous sends. Inspect the authorized chat and reconcile stored message IDs.

The old insecure telegram-webhook is now fail-closed503; restoring its old source
would reopen an academic-data disclosure risk. Preserve its encrypted source for
forensics, not as an automatic rollback target. The new function is isolated as
flymind-telegram-webhook with namespaced bot secrets; do not overwrite shared legacy
TELEGRAM_BOT_TOKEN during rollback.

Cloudflare actual preview deployment0928fa3a can be selected from Pages deployment
history. The preview private frontend does not contain service credentials. Do not
roll production back to a public demo build while presenting it as authenticated.

Verified encrypted database backup predates test bootstrap/telemetry. Restore first
into an isolated database, compare original and subsequent writes, then make an
explicit selective recovery plan. A blanket production restore would discard new
records. Auth/site configuration and old Edge source are in an additional encrypted
archive; actual secret values remain in private configuration/platform secret stores.


## Reminder v2 rollback — 2026-10-17

Disable delivery/scanning before reverting Python code. The new reminder JSONB
entries remain strings, so old code can parse them, but old code restores48h and
can recreate redundant creation/reminder messages. Do not run that old sender on
an active queue. Keep database migration202610170007: it only prevents suppressed
jobs from advancing neural-success health and is compatible with older completed
simulation results. No database restore, row deletion or migration-history reset
is needed to disable this release. Preserve outbox, message IDs, threshold audit
and the hosted synthetic-test checkpoint for recovery/deduplication.
