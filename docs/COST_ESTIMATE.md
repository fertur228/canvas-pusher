# Operating cost estimate — 2026-10-14

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

## Assumptions, not fabricated usage metrics

At15-minute polling:96 runs/day,2880/month. If each cold/warm Actions job occupies
30–60seconds, budget48–96 runner minutes/day,1440–2880/month. At5-minute polling
this triples. This public repository uses standard GitHub-hosted runners, which
are free for public repositories. A private repository's included minutes and
account plan must be checked; prefer30-minute polling if necessary. Never enable
paid overage to preserve this schedule. Actual Linux CI durations are recorded
separately; container timings are not GitHub startup timings.

For10 active courses, one page each assignments/files plus courses/announcements:
~22 Canvas GETs/poll,2112/day; pagination/retries increase this. Concurrency8 and
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
