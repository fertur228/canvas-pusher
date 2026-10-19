# Native scheduler recovery — 19 October 2026

Production activation and the scoped server credential are already verified. Do
not bootstrap again, replay historical Telegram updates, repeat the launch smoke,
or resubmit earlier manual requests. The remaining release gate is two real
scheduled scanner runs, including successful scanner jobs and scanner steps.

## Read-only diagnosis at 16:12 UTC

- `FLYMIND_GITHUB_PAT` remains installed with update time 11:06:28 UTC. Its
  successful hosted dispatch/completion evidence remains valid; no credential
  was exported, replaced or printed.
- Main is `590b1c46fc5eb5885d0cdffa9e5b295f8b052c2a`, the scanner workflow is
  active, Actions is enabled, and the five-minute expression is `3/5 * * * *`.
- All production gates retain the reviewed values. The owner binding and original
  bootstrap timestamp match the activation checkpoint.
- No native scanner `schedule` event has been emitted since activation at
  11:14 UTC. The last earlier event, at 10:41 UTC, was skipped while gates were off.
- The latest successful snapshot remains 12:38:59 UTC. Freshness is therefore
  **failed**, even though the stored last-run result is healthy.
- The independent native watchdog actually ran at 14:37 UTC and failed its health
  step with `status=failed`; this correctly detects the stale scanner. It is not
  a successful scanner run.
- No active manual requests exist. The production outbox contains two completed
  sends with saved message IDs and no nonterminal or failed jobs.
- Original 336/32/14 legacy row hashes, eight migrations and public-table RLS
  checks pass. No database or academic records were changed by diagnosis.

GitHub's listing still shows old run `39137536308` as queued with no jobs; the
cancellation endpoint reports that it is already completed. No rerun was sent.
This inconsistent provider state is not evidence of an executing scanner.

## Controlled recovery

At **16:12:32 UTC**, after confirming no active scanner or manual request, the
existing workflow was disabled and re-enabled through the GitHub API. Final state
is active. This did not change code, credentials, production flags, snapshots,
outbox rows, delivery identities or the cron expression. No dispatch was sent.

The observer only reads runs and jobs. It records actual `event=schedule` events
after activation and requires the last two completed runs to have workflow, job
and scanner-step success. It never counts a manual dispatch, skipped job or
workflow acceptance as success, and performs no automatic resend.

- [Recovery operation](production-scheduler-recovery.json)
- [Latest observed native runs](production-scheduled-verification.json)
- [Production invariants and health](production-final-observation.json)
- [Actual failed watchdog](https://github.com/fertur228/canvas-pusher/actions/runs/39270675298)

GitHub documents that scheduled events can be delayed or dropped and that an
inactive schedule actor can also prevent events. The configured actor is the
repository owner, main contains the workflow, and Actions/workflow are enabled.
The provider has not supplied a definitive cause for the missing events.
See [GitHub scheduling troubleshooting](https://docs.github.com/en/actions/how-tos/troubleshoot-workflows).

At 16:21 UTC the live GitHub Status API confirmed an active incident affecting
Actions, Pages and webhooks, opened at 15:49 UTC. GitHub reports delayed workflow
processing and webhook delivery. This confirms a current provider incident but
does **not** establish the cause of the earlier missing scanner events.
See [incident 8tzbpcnl75jp](https://www.githubstatus.com/incidents/8tzbpcnl75jp).

Observation ended at **16:23:54 UTC**, more than eleven minutes after the guarded
workflow restart: **zero** new native scanner events and **zero of two** required
scheduled successes. The local read-only observer was stopped; the cloud workflow
and production gates remain enabled. No new application version was deployed.

## Controlled fallback implementation

If native scheduling does not recover, the proposed alternative is Supabase Cron
every five minutes, invoking an authenticated, narrowly scoped Edge dispatcher
that uses the existing server PAT to launch the same reviewed main-branch worker.
It must preserve production gates, account binding, serialized workers, durable
dispatch identities, ambiguous-outcome handling and the existing outbox.

The acceptance chain would then be two actual Supabase cron executions, each
correlated to a successful GitHub worker and verified persisted Canvas snapshot.
Those GitHub runs would be `workflow_dispatch`, **not** native GitHub `schedule`;
the evidence and release gate must explicitly name that difference.

The existing project supports `pg_cron` 1.6.4 and `pg_net` 0.20.0, but neither is
installed. Vault 0.3.1 is installed. This inventory is read-only. No extension,
cron job, new Edge function, scheduler secret or migration has been deployed.
The continued release authorization is used to prepare a separately authenticated fallback.
The original native-scheduler evidence remains unchanged and must not be relabeled.

Changing only the source of scheduled dispatch would still depend on GitHub
Actions workers and would not remove the currently confirmed provider outage.
Do not present that alternative as an immediate outage fix or deploy it merely
to manufacture successful scheduling evidence.

Implementation would require reviewed additive schema/permissions, tests for
denied callers and duplicate ticks, a disabled-first deployment, authenticated
negative checks and two observed cloud cycles before claiming completion. The
existing rollback remains: disable new scanner work and preserve all persisted
data. See [Supabase scheduled functions](https://supabase.com/docs/guides/functions/schedule-functions).

### Implementation under validation

- `202610190008_scheduler_bridge.sql` adds only a private timer ledger and
  service-only advisory-lock claim RPC; original migrations/data stay unchanged.
- `flymind-scheduled-dispatch` authenticates timestamped HMAC payloads, exact
  production identity and GitHub activation gates. It checks recent workers and
  scan attempts; a tick is durable before its single dispatch POST. Lost responses
  stay ambiguous and are never blindly resent.
- `supabase/optional/scheduler_bridge.sql` provisions a five-minute job **disabled**.
  Vault stores its key; the cron command contains no credential. The Edge function
  starts disabled/dry-run. Browser roles cannot access the ledger/RPC/cron. Provider-owned `pg_net`
  retains its SQL grants, but is not an exposed API schema: real anonymous
  PostgREST access returned HTTP406/PGRST106. The queue contains no secret key,
  PAT, bot credential or academic payload; signed tick replay is time-bounded
  and claimed durably. Do not expose `net` via API configuration.
- A timer run title has a `timer-` prefix, so the trusted manual completion handler
  cannot mistake it for an owner `/check` request. Existing worker concurrency,
  snapshots, reminders and notification outbox are unchanged.
- Native GitHub cron stays active. The fallback skips recent work if it recovers.
  `CANVAS_WORKER_ENABLED=false` is still the master quick stop; independently pause
  only the fallback with `cron.alter_job(jobid, active:=false)`.
- Prove two real clock-originated cron ticks, HTTP results, matching successful
  GitHub scanner steps and persisted fresh snapshots. A cron SQL success alone is
  not a completed scan. GitHub events from this fallback are `workflow_dispatch`.

At 288 invocations/day this adds approximately 8,640 Edge calls and small ledger
rows per 30 days. No continuously running process or paid service is introduced.
Timer ledger history is currently preserved; review its growth after 30 days.

No fallback deployment or activation is claimed by this implementation section.
The operational verification section will record actual outcomes separately.

## Hosted preparation verified at 16:36 UTC

Migration `202610190008_scheduler_bridge.sql` was the only dry-run pending file
and was applied normally. Nine migrations are now recorded. Authenticated backup
decryption and every original 336/32/14 legacy row checksum passed again; protected
public tables still have RLS. Nothing was bootstrapped again.

The dedicated Edge function is deployed with explicit HMAC authentication,
`FLYMIND_SCHEDULE_ENABLED=true`, `FLYMIND_SCHEDULE_DRY_RUN=true`; the actual Cron
job remains **inactive**. Its HMAC key is in Vault/Edge and a private ignored local
file. No key is in the cron command or repository.

Real checks: wrong signature403, expired signature403; valid signed request passed
the new server PAT preflight and stopped at `workflow_not_upgraded` because main
has not merged this timer input. A real database `pg_net` POST using Vault produced
the same503 result without timeout. No scanner was dispatched. Real anonymous
RPC/table reads were denied; service-only test-account claim succeeded, then
repeat and overlapping claims were denied. One explicitly labeled dry-run audit
row was added to the isolated test account; no production event or message was made.

The hosted provider retains SQL role grants on its `net` schema/tables. The CLI
role cannot revoke grants made by the provider owner. This is recorded rather than
hidden: `net` is not exposed through PostgREST (real anonymous request406/PGRST106),
and this queue carries no credential or academic payload. Do not expose `net`.
The new public ledger/RPC are independently denied to anon/authenticated roles.

GitHub officially reported degraded Actions/Pages/Webhooks from15:49 UTC:
https://www.githubstatus.com/incidents/8tzbpcnl75jp. Current PR3 CI jobs are queued
with zero steps executed. This corroborates the current runtime blocker, but is
not proof of the cause of all missing native cron events earlier in the day.
PR3 is unmerged; its gateway-configuration review finding is fixed and resolved.

The fallback still requires green current-head CI, guarded merge, signed dry-run
against upgraded main, then activation and two correlated real cloud cycles. It
does not bypass GitHub runner outages. Native `event=schedule` successes remain0.
Neither scheduled autonomy nor a completed fallback scan is claimed.
