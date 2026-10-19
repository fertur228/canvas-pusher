# FlyMind: production launch, 19 October 2026

Status: **PRODUCTION DEPLOYED, FINAL VERIFICATION PENDING**.
Primary Telegram is enabled in shadow mode. Two actual scheduled successes are
still under observation; manual runs below do not satisfy that gate.

## Credential and real manual synchronization

The owner installed a repository-scoped fine-grained token through the hidden-input
`dispatch_setup` helper. Supabase `FLYMIND_GITHUB_PAT` was updated at
2026-10-19T11:06:28Z. The webhook selects it ahead of the invalid legacy `GITHUB_PAT`.
No personal `gh` OAuth credential was exported and no token was printed.

A controlled HTTP `/check` update to the real deployed webhook used that server
credential, the existing verified test group and main branch:

- Scanner [39242627674](https://github.com/fertur228/canvas-pusher/actions/runs/39242627674): success.
- Trusted completion [39242845141](https://github.com/fertur228/canvas-pusher/actions/runs/39242845141): success.
- Persisted request: completed, Canvas verified at 11:11:24 UTC, errors 0.
- Exactly one completion outbox send attempt, message ID persisted.
- Repeated identical Telegram update rejected as already handled; no second dispatch.
- This was real hosted HTTP/Bot API testing, not a claim of pressing the Telegram client button.

[Sanitized evidence](release-server-dispatch-verification.json).

## Primary activation

The prepared production account and its original silent bootstrap were reused.
No assignments, snapshots, reminder markers, old users or test records were reset.
Verified private user/chat/bot identity matches the stored owner evidence and
Supabase owner UUID. The test and production accounts remain separate.

The test worker/finalizer finished before routing changed. Polling was disabled
while GitHub account configuration and namespaced Edge recipient changed.
Commands were registered for the private chat; the existing secure webhook URL
and secret header remain in use. Pending Telegram updates: 0.

Bot: https://t.me/canvasheimdall_bot

One explicitly authorized launch smoke message was delivered to the private chat
through the durable outbox: one send attempt, stored message ID. Its identity is
also the current week's operational health report, preventing an extra startup
health notification. No synthetic academic event was sent to production.

Wrong webhook secret, wrong actor and old test chat each returned HTTP 403 after
switching routing, without sending messages or exposing records.

Activation: **2026-10-19T11:14:48.503767Z**.

| Flag | Value |
| --- | --- |
| CANVAS_WORKER_ENABLED | true |
| FLYMIND_ENABLED | true |
| DELIVERY_MODE | production |
| FLYMIND_PRODUCTION_AUTHORIZED | true |
| FLYMIND_MODE | shadow |
| FLYMIND_NEURAL_ENABLED | true |
| NEURAL_TELEMETRY_ENABLED | true |
| FLYMIND_MAX_NEURAL | 2 |
| FLYMIND_TEST_CHAT_VALIDATION | false |
| FLYMIND_RETENTION_ENABLED | false |

Edge `FLYMIND_MANUAL_SYNC_ENABLED=true`, workflow ref `main`, recipient is the
verified private owner chat. No identity values or credentials are included here.

## Production cloud evidence

Runtime main remains the reviewed PR1 merge `84026aa74098db8aaf4396086d26aad961e23fd7`.
No application code, neural parameters or scientific artifacts changed during rollout.

- Controlled production scan [39243302085](https://github.com/fertur228/canvas-pusher/actions/runs/39243302085): success.
- Repeat production scan [39243569052](https://github.com/fertur228/canvas-pusher/actions/runs/39243569052): success.
- Both are `workflow_dispatch`, not scheduled runs.
- Health healthy; pending/ambiguous jobs 0; only the one launch smoke message.
- No historical assignment creation events or duplicate messages.
- Existing Canvas baseline: 6 courses, 20 assignments, 91 files, 2 announcements.
- Current deadline views: 4 upcoming, 3 overdue, 10 total pending (including 3 undated).

[Initial production evidence](production-initial-verification.json).

The scanner workflow is active on main with cron `2-59/5 * * * *`; concurrency is
preserved. GitHub scheduling is best effort, not a five-minute delivery guarantee.
An independent hourly health workflow is also active; retention remains off.
Two successful actual `event=schedule` runs must be verified separately.

## Neural engine and Observatory

The genuine 1,500-neuron FlyWire network, 25,206 directed edge rows and 276,399
contacts are unchanged. Neural execution is enabled after mandatory primary delivery.
No eligible new academic event occurred during the controlled production scans,
so production has no neural run yet; `/brain` should accurately say so.
The genuine main/Linux neural execution and private SHA-verified telemetry from
18 October remain valid evidence, not new production activity.

Private Observatory: https://flymind-preview.flymind-observatory.pages.dev/
Real isolated user Auth/JWT/RLS/Storage/SHA/frontend-decoder/headless replay passed
previously and was not needlessly repeated. Actual owner-browser replay remains
unverified by the agent. Personal Chrome is neither used nor required for Telegram.
No service-role key enters the frontend. The model remains biologically unvalidated;
Canvas encoding and readout thresholds are engineering assumptions.

## Safety and quick stop

Before activation, original 336 Canvas rows, 32 historical grade rows and 14 legacy
health rows matched their full backup hashes. Eight migrations, RLS, private Storage
and all six existing artifact objects were intact. No migration was repeated.

Quick stop for new scanner jobs:

```sh
gh variable set CANVAS_WORKER_ENABLED --repo fertur228/canvas-pusher --body false
```

Changing variables does not stop a job already executing with its captured environment.
Inspect and cancel an active worker if an immediate stop is necessary; preserve all
outbox state and reconcile uncertain Telegram sends before retry. Keep
`FLYMIND_ENABLED=true` when stopping neural execution via `FLYMIND_NEURAL_ENABLED=false`.
Never restore the insecure webhook, reset snapshots, clear message IDs or automatically
restore the old backup over newer writes. See [rollback](ROLLBACK.md).

All execution evidence above is cloud-side. No localhost endpoint or running MacBook
is required. The agent did not physically turn off the owner's computer.
