# Operating cost estimate — updated 2026-10-19

## Verified cloud timer cycles — 2026-10-19

Two automatic Supabase Cron → GitHub worker jobs took105/87seconds (mean96s):
460.8runner minutes/day,13824per30days at288cycles/day. Timer adds8640Edge
invocations/month plus small ledger rows; no paid service enabled. This is now the
active polling source. Native GitHub scheduled emitter remains unverified. The independent database
heartbeat monitor also runs every five minutes and sends no external messages.
Current measured database: 14,175,379 bytes; private telemetry: 912,139 bytes.
Estimated infrastructure cost remains $0/month within existing free limits.
Standard runners for this public repository are free under the current
[GitHub billing policy](https://docs.github.com/en/billing/concepts/product-billing/github-actions);
[Supabase Free](https://supabase.com/pricing) and
[Cloudflare static Pages](https://developers.cloudflare.com/pages/functions/pricing/)
cover the current scale. No paid services were activated.
[Exact runtime evidence](scheduler-runtime-measurement.json).

## Earlier production measurements — 2026-10-19

The private production bot is enabled; native scheduled execution is still being
verified. Two real production `workflow_dispatch` runs took approximately 99 and
92 seconds from creation to completion, including queue/setup. At a fully served
five-minute schedule, 288 runs/day would imply about 458 runner minutes/day or
13,752 minutes per 30 days at this two-run average. This is a projection from
unchanged snapshots, not measured monthly usage or a guaranteed schedule rate.
The public repository uses standard Ubuntu runners; no paid runner or billing
upgrade was activated. A private-repository conversion requires a fresh quota
review before keeping this frequency.

The read-only hosted inventory is 13,782,163 database bytes and six private
telemetry objects totaling 912,139 bytes. Retention remains disabled during
rollout; no old academic records or artifacts were deleted. Canvas uses roughly
14 requests per ordinary poll for this account: about 4,032/day at five minutes,
before retries and additional pagination. Real API reads returned HTTP200, but
this is not evidence of an unlimited university-specific quota.

The platform has not yet emitted native schedule events after initial activation;
therefore the earlier 1–7 minute detection estimate below is only conditional on
an on-time run. Current cron delays can be substantially longer. Forecasts must
not be presented as an achieved delivery SLA.

The dated sections below preserve earlier measurements and assumptions.

Target $0/month, not an uptime guarantee. Current official references:
[Supabase billing](https://supabase.com/docs/guides/platform/billing-on-supabase),
[Supabase pricing](https://supabase.com/pricing),
[Cloudflare Pages limits](https://developers.cloudflare.com/pages/platform/limits/),
[GitHub scheduling](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule),
[GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
Review quotas again before activation; no paid service was purchased.

Supabase Free currently includes 500MB database, 1GB object storage, 5GB uncached
and5GB cached egress, 50,000 MAU and500,000 Edge invocations/month. No Realtime is
used. Free projects can pause after a week of inactivity; free organizations have
limited project count. Quota exhaustion can put a database in read-only mode.
Cloudflare Pages Free allows500 builds/month,20,000 files and25MiB/file; this
static dashboard is far below those asset limits and needs no Pages Functions.

## Historical 15-minute estimate (superseded by measured five-minute assessment below)

At15-minute polling:96 runs/day,2880/month. If each cold/warm Actions job occupies
30–60seconds, budget48–96 runner minutes/day,1440–2880/month. At5-minute polling
this triples. This public repository uses standard GitHub-hosted runners, which
are free for public repositories. A private repository's included minutes and
account plan must be checked; prefer30-minute polling if necessary. Never enable
paid overage to preserve this schedule. Actual Linux CI durations are recorded
separately; container timings are not GitHub startup timings.

For10 active courses, one page each assignments/files plus courses/announcements:
~22 Canvas GETs/poll,2112/day; pagination/retries increase this. Previously concurrency8; current concurrency2 and
Retry-After handling bound pressure. No promise of a university-specific rate quota.

Example20 relevant events/day:600/month. Artifacts ~55–163KB gzip using existing
references; worst simple600×163KB≈98MB/month,30-day retention≈98MB steady state.
Per-worker identical profiles reuse computation and one object, reducing this.
Default5 neural jobs/run caps burst work; primary delivery is processed first.
At strong ~2seconds standalone simulation/process cost,20 computations/day is
~40seconds scientific CPU/wall scale per day, excluding installation and scanner.
This is an estimate; see recorded Linux platform-specific benchmark reports.

Budget roughly2–6MB/month for600 events, summaries, three jobs/event and bounded
attempt history including indexes; actual Canvas payload lengths vary. Initial
snapshots can add several MB. Event identities and delivery tombstones persist to
preserve idempotency; long-term database growth is not eliminated by blob retention.
Review storage/database usage monthly and define explicit academic-record erasure
before years of operation. No production records are automatically deleted here.

Dashboard local scientific bundle ~2.04MB uncompressed telemetry (~0.33MB gzip),
plus lazily loaded JavaScript; ten private163KB replays/day ≈49MB/month object egress.
A few builds/releases per month fit Pages quotas. Authentication is one owner;
webhook invocations track owner commands, not every Canvas poll. Telegram ~20
primary+20 enrichment edits/day in this example, no paid Telegram API product.

Schedules are best effort, can be delayed/dropped, run only on the default branch
and may disable after60days of public-repository inactivity. Persisted reminder
thresholds tolerate late execution, but cannot create an uptime guarantee. GitHub
failure alerts and an optional independent Supabase Cron stale-heartbeat check
reduce silent failures without introducing a paid always-on server.

## Hosted measurements — 2026-10-17

Official quota pages linked above rechecked on2026-10-17: Supabase Free500MB DB,
1GBStorage,5GB egress+5GBcached; Pages Free500builds/month; standard public-repository
GitHub runners remain free. No plan upgrade/billing activation was performed.
Actual project DB12.82MB; two compressed neural objects293657bytes total. Preview
build17files/3.82MB. The actual GitHub read-only job39043798824 took26seconds,
including14Canvas requests; the full neural worker timing is measured separately.
At96polls/day and14requests/poll, this dataset implies1344Canvas GETs/day before
pagination/retries. At20events/day with147KB average current artifact,600events
would add~88MB/month before dedup/retention. These are estimates, not an active
production schedule. Current scheduler is disabled; retention remains opt-in.

The real full hosted tests each did two scans:98s/154s whole GitHub job,73.17s/
128.47s worker portion, with one actual neural child in the second job. A cautious
single scheduled job estimate is60–100s including setup:96–160runner min/day,
2880–4800min/month at15min intervals. This remains $0 for standard runners in this
public repository; it would exceed typical included private-repository minutes.
Keep budget assumptions separate from uptime guarantees. Supabase per-snapshot RPC
round trips dominate this small-circuit workload more than the4.47CPU-second neural
child. Three current Storage objects use456075bytes; no paid infrastructure enabled.

## Five-minute polling decision — 2026-10-17

Repository visibility was verified PUBLIC through the GitHub API. Standard Ubuntu
runners remain free for public repositories; larger runners are not selected.
Change only feature-branch cron to `2-59/5 * * * *`: 288 runs/day, 8640/30-day month.
Production master flags and the disabled-inactivity scheduler remain OFF.

Measured read-only Canvas check after reducing concurrency from8 to2: 14 HTTP200,
6 courses,20 assignments,91 files,2 announcements,29.996s wall time. Request-cost
sum56.88694; minimum reported remaining quota592.09832; no429 or failed scopes.
Canvas uses replenishing cost-based quotas, not a universal fixed requests/minute
limit. These headers are a point-in-time measurement, not a reservation or SLA.
We preserve bounded retries/Retry-After and fail closed on authentication errors.
Source: [Instructure throttling](https://github.com/instructure/canvas-lms/blob/master/doc/api/throttling.md).
Evidence: [deadline-canvas-preflight.json](deadline-canvas-preflight.json).

At14requests/poll:4032GET/day,120960/month before pagination/retries. Using the
previous real cloud durations plus lower request concurrency, allow60–120s per
single job:288–576 runner min/day,8640–17280/month. This is feasible at$0 for this
PUBLIC repository's standard runners, but not inside private GitHub Free's2000min.
No paid overage enabled. One observed quota sample does not guarantee future load;
return to15min if429 or sustained runs>5min appear.

Concurrency remains one active scanner (`cancel-in-progress:false`) plus at most
one pending run; later pending runs replace older ones. A slow scan is not killed
for the next tick. The15min job timeout and10min application budget remain.
No telemetry is uploaded on unchanged snapshots. Metadata reads increase3x;
~113small snapshot responses/poll imply roughly0.5–2GB/month API payload depending
on response sizes/headers, an estimate to verify against Supabase usage charts.
Event/telemetry growth follows actual changes/reminders rather than poll count.

Expected detection in an on-time healthy schedule:0–5min polling wait, plus runner
queue/setup and roughly30s Canvas reading; allow about1–7min end-to-end as an
estimate, not a measured scheduled-delivery SLA. GitHub can delay/drop runs for
longer, only schedules the default branch, and may disable inactive public repos.
This feature branch is NOT an active production schedule. Official references:
[GitHub schedules](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule),
[concurrency](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency),
[billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).

Latest real Linux hosted notification check39049711232: two normal real scans
took176.825s total, with0events/errors; a separate accelerated14-step synthetic
deadline exercise took88.236s and sent11test messages. Wholejob294s includes
setup and both phases, not the cost of one normal poll. Two cached real neural
profiles served11event associations; one cancelled reminder ran no simulation.
Evidence:[deadline-hosted-verification.json](deadline-hosted-verification.json).
