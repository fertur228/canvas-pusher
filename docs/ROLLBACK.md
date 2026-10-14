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
