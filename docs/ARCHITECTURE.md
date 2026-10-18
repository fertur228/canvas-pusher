# FlyMind architecture

A finite Python worker runs in GitHub Actions. It reads Canvas; an atomic PostgreSQL
RPC commits normalized snapshots, typed events and notification jobs. Primary
Telegram delivery precedes neural processing. Retries and leases survive runner
shutdown. An uncertain `sendMessage` acknowledgement is quarantined; an operator
must supply the delivered message ID or confirm non-delivery. Exactly-once external
Telegram delivery is impossible without Telegram-side idempotency.

```
Canvas GET + Link pages → snapshot CAS + event + outbox transaction
 → sendMessage → persisted message_id → fixed-profile neural child
 → private gzip + experiment metadata → readout → optional editMessageText
 → authenticated Observatory replay
```

`src/core/scanner.py` is shared by the legacy and FlyMind workers. It limits
concurrency to eight requests, follows same-origin API pagination, rejects loops,
retries transient failures and never treats a failed scope as an empty snapshot.
Announcements cover the previous 30 days. Complete assignment polling is deliberate:
Canvas submission updates may not advance the assignment's own update timestamp.
Incremental filtering that loses grades/submissions would be incorrect.

`src/flymind/events.py` versions event identity by account, object and revision;
reminders use deadline + nearest crossed threshold. Simultaneous grade/deadline
changes remain separate. Snapshot CAS protects concurrent mutation; GitHub also
serializes scanner executions. It cannot recover transitions that appear and
vanish between polls. Initial global sync requires explicit silent bootstrap.

`CANVAS_WORKER_ENABLED=false` gates the whole scheduled scanner by default.
`FLYMIND_ENABLED=false` selects legacy main behavior. Enabled mode uses the durable
worker. Within FlyMind, `DELIVERY_MODE=disabled` prevents delivery; test mode requires a separate
explicit test chat bound to its account. Shadow mode computes/stores without editing
primary notifications; enrich mode edits only confirmed message IDs. Disabling
neural processing preserves the durable primary path.

The child receives only a fixed profile and public scientific graph, never student
payloads or credentials. Timeout 30 s; Linux CPU limit 25 s, address-space limit
1.5 GiB, output-file limit 8 MiB; maximum five neural jobs by default and 600 s total
worker budget. Identical profiles reuse one calculation/artifact inside a worker.
The original recording timestamp remains visible; reuse is documented in metadata.

PostgreSQL stores small event/experiment summaries; Storage holds private gzip
artifacts (maximum 4 MiB). Browser authentication uses a pre-created owner account,
memory-only session, token refresh and RLS via auth.uid → flymind_accounts.owner_id.
No browser service key, signup UI, public private-artifact URL or persisted token.
Local mode uses only public scientific reference exports.

Heartbeat and job transition audit are persistent. An hourly GitHub watchdog is
independent of the delivery pipeline; optional Supabase Cron marks stale heartbeats
independently of GitHub. Neither free scheduler offers a delivery-time SLA.
