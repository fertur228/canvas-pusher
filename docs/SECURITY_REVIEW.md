# Security review — 2026-10-14

Scope: local code, available Git history, dependencies, offline/browser tests,
real isolated local Supabase APIs. This is not an audit of the live production
project's unknown custom grants, logs, policies or secrets. No secret values are
recorded here. Production activation remains gated.

## Findings and mitigations

| Severity | Finding | Implemented mitigation |
| --- | --- | --- |
| High | Telegram webhook accepted requests without a secret header | Fail-closed secret comparison, exact chat+actor allowlist, bounded JSON body |
| High | Webhook logged inbound payloads and grade responses | Removed private payload/error-body logging; sanitized fixed error codes |
| High | Duplicate webhook update could repeat side effects | Durable unique update_id claim before commands; uncertain commands require review |
| High | Legacy exposed academic tables lacked an explicit owner boundary | Additive legacy RLS/grant migration; auth.uid→account owner mapping; worker-only mutations |
| High | Service credential could accidentally be configured in browser | Public config rejects service role/secret keys; user sessions only; memory-only auth |
| Medium | Raw course names entered Telegram HTML | Escaping and bounded report pages; React renders private fields as text |
| Medium | Canvas pagination could leak bearer token cross-origin | Shared same-origin API-prefix Link validation, no redirects, loop/page bounds |
| Medium | Lost Telegram acknowledgement could trigger duplicate delivery | Ambiguous-send quarantine; edit only confirmed message_id; persisted retries/leases |
| Medium | Unbounded telemetry/decompression and no retention | 4MiB object limit,32MiB browser decompression bound, hashes, private bucket and explicit retention |
| Medium | Default legacy path could deliver when FlyMind flag is off | Master CANVAS_WORKER_ENABLED scheduler gate; separate test/production chat validation |
| Medium | Old test/CLI dependencies had known advisories | Vitest5.0.4 and Supabase CLI2.120.0 upgrade; pinned lockfiles; audits repeated |
| Low | Generated Supabase connection metadata was tracked | Removed from Git index; preserved local files and ignore rules; no history rewrite |

Repository checker scans known GitHub/Telegram/private-key/service-role JWT signatures
and rejects oversized/generated/private paths. Available history scan found no
matching credentials. This is not proof that arbitrary strings or historical logs
never contain sensitive information. Scientific gzip files were inspected as real
public neuronal recordings and contain no Canvas event payloads.

## Verified boundaries

Real local PostgreSQL migrations test CAS/outbox, claim tokens, owner/other/anonymous
RLS, restrictive Storage guards even with broad legacy policies, heartbeat/audit,
webhook replay and retention. Real LOCAL Supabase Auth/PostgREST/Storage tested two
users: owner read succeeds; other owner/anonymous/browser worker RPC access fails;
public/guessed private artifact URLs fail; authorized download hash matches; shared
artifact survives expiration of only one association. See local-supabase-validation.json.

Browser tests cover no private requests before sign-in, explicit failure without demo
fallback, actual neural replay through mocked authenticated transport, in-memory token
handling and sign-out. These are UI mocks, distinct from local service API checks.

Worker child strips Canvas/Supabase/Telegram credentials and receives only a fixed
profile. Linux CPU/address-space/output limits and process timeout bound resource use.
GitHub actions are SHA-pinned, contents:read, no pull_request_target, no secret-bearing
CI artifacts. The controlled Canvas check gets no database or Telegram credentials.
No service role credential appears in the static dashboard build.

## Remaining release gates

Review live destination RLS, legacy functions/grants, Storage bucket access and Auth
settings before activation. Disable public signup and map the owner UUID explicitly.
Rotate any credential ever found in public history/logs; do not assume removing a
file invalidates a secret. Review production log retention separately. Do not restore
the old unauthenticated webhook as a rollback.

Telegram cannot guarantee exactly-once sendMessage. Human reconciliation is required
for ambiguous delivery; this protects against duplicates at the cost of automatic
liveness. Persisted snapshots/event payloads remain private but need an explicit
long-term academic-data deletion/export policy. Free-tier monitoring is not an SLA.

Historical CI-log retrieval was attempted for the latest available legacy run;
GitHub returned HTTP410 (expired logs). No claim of a completed historical-log
content audit is made. The old main code demonstrably contained private name/body
logging; the feature branch removes it. Existing scanner workflow state is
`disabled_inactivity`; it was not re-enabled during testing.

Final audits: npm audit (root tools and dashboard) and pip-audit (core/scientific
lockfiles) reported no known vulnerabilities. These are point-in-time advisories,
not a guarantee. Brian2/pyparsing deprecation warnings and a large lazy 3D chunk remain.
SHA-pinned older GitHub actions emit a Node20-runtime migration advisory while running
successfully under the runner runtime. Updating those pins needs a separate regression
check; no dependency versions were changed to tune scientific outputs.

## Telegram assistant follow-up (2026-10-14)

New webhook authorization requires exact secret/user/chat/account AND bot identity.
Telegram update IDs are namespaced by numeric bot ID; replacing a bot preserves
academic history and prevents accidental old-bot message edits. Menu visibility is
not authorization. New deadline/manual RPCs are server-only; manual request history
has owner SELECT RLS. Missing completion-event fields are rejected transactionally.

Private bootstrap uses hidden terminal input, ignored exclusive0600 files, a random
owner challenge, getMe identity checks and stdin for GitHub secrets. Discovery refuses
an active webhook. Secret rotation requires a disabled idle scanner. These controls
were tested with mocked Bot/GitHub APIs; no real bot was configured. Completion runs
trusted default-branch code and never executes a triggering workflow artifact.

Core outbox retains ambiguous-send handling and retry state. Immediate webhook menu
responses deliberately are not automatically replayed after claim: a lost response
or rate limit requires a new user command/reconciliation, not a potentially duplicate
send. Canvas401/403 prevents releasing academic notification backlog. Operational
manual-failure reports use a targeted outbox claim. No production secrets were rotated.
