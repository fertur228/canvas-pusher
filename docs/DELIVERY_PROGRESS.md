## Production rollout — 2026-10-19

- [x] New namespaced PAT installed by owner; real hosted `/check` dispatch/completion passed.
- [x] Duplicate webhook update suppressed; one completion send with persisted message ID.
- [x] Existing production baseline reused without bootstrap/reset or historic new-assignment alerts.
- [x] Private recipient configured; one authorized smoke delivered through outbox.
- [x] Production shadow mode and five-minute main-branch scheduler enabled.
- [x] Two controlled production scans succeeded with no duplicate sends; cloud watchdog succeeded.
- [ ] Two actual `event=schedule` scanner runs with job and scanner step success.

[Current release evidence](PRODUCTION_LAUNCH_20261019.md). The sections below record earlier states.

## Earlier resume check — 2026-10-19

- [x] Remote read access restored after the owner explicitly lifted the pause.
- [x] Selected Edge credential is legacy `GITHUB_PAT`; its digest is unchanged since the HTTP 401 probe. `FLYMIND_GITHUB_PAT` is absent.
- [x] Primary Bot API identity and separate production binding match private owner evidence.
- [x] Existing production baseline is preserved: 20 assignments, zero outbox jobs. No repeat bootstrap.
- [x] Fresh Canvas GET check: 14 HTTP 200 responses, 6 courses, 20 assignments, no failures.
- [x] Original 336/32/14 row hashes still match; eight migrations and private Storage intact.
- [ ] Owner must privately install a repository-scoped credential using [dispatch setup](DISPATCH_CREDENTIAL_SETUP.md), then real webhook dispatch and production rollout can continue.

[Sanitized read-only evidence](resume-readonly-verification.json). No messages or database writes in this check.

## Verified milestone — 2026-10-18

- [x] Personal Chrome gate removed; real isolated Auth/API/headless replay and cleanup passed.
- [x] PR1 merged to main84026aa after green CI and backup/data/RLS gates.
- [x] Legacy grades protected; multiple-enrollment null-score regression fixed.
- [x] Separate production binding and silent bootstrap:0events/0messages; disabled after preparation.
- [x] Real main cloud Canvas/FlyWire/Storage test, real operator manual lifecycle and duplicate completion passed.
- [ ] New scoped GitHub dispatch credential: legacy server token returns401; owner helper prepared.
- [ ] Actual hosted /check with new credential, primary smoke, activation and2scheduled cycles.
- [x] Test window closed; production/scanner/delivery gates OFF; all data retained.

> Актуальный release18октября: PR1 merged, real Auth/headless и main cloud E2E passed.
> Production выключен: серверный GitHub PAT возвращает401. Личная Chrome-сессия не нужна.
> [Фактический отчёт и единственный внешний credential шаг](PRODUCTION_RELEASE_20261018.md).

> Актуальное решение18октября: личная Chrome-сессия не является release gate.
> Реальный Auth/RLS/headless replay и независимый Telegram rollout:
> [AUTOMATED_RELEASE_VERIFICATION.md](AUTOMATED_RELEASE_VERIFICATION.md).
> Ниже сохранены исторические результаты, где этот gate ещё считался обязательным.

# FlyMind delivery progress

## Final release verification — 2026-10-18 (in progress)

- [x] Current feature branch/PR1 verified; original head ec5f42c, CI green, gates OFF.
- [x] Owner Auth now exists and matches private owner evidence + test account.
- [x] All8 migrations present; original336/32/14row hashes unchanged; encrypted backup verified.
- [x] Hosted SQL owner/foreign/anonymous/Storage/RPC isolation repeated with rollback.
- [x] Three inline menu buttons and three visible deadline filters implemented.
- [x] Real Telegram exposed ReplyKeyboardRemove edit limitation; corrected with temporary-message cleanup.
- [x] Corrected FlyMind webhook v6 deployed to test group; legacy webhook unchanged.
- [x] Real Canvas preflight14HTTP200,6courses,20assignments,91files,2announcements.
- [x] Deno17, Vitest28, TypeScript/build, browser4local+2private HTTP-mock, localPG17 passed.
- [ ] Actual owner browser sign-in/private replay (owner asked to sign in; password never requested).
- [x] Python201 passed (172 dependency warnings); real Telegram client /start rendered3inline buttons.
- [x] Hosted commands, three filters, repeated identical edit and4negative auth checks passed.
- [x] Code268edd1 CI39065375940 passed (offline+database); Linux controls/batch included.
- [x] Cloud39065422453: two real scans verified,112.11s,events0/errors0,duplicate sends0.
- [x] Observatory account-scoped health/history/trigger;3private+4local browser tests.
- [ ] Actual private owner browser replay remains pending; no merge/production activation.
- [ ] Conditional merge, real /check completion on main, production bootstrap/activation and two scheduled cycles.

## Текущее hosted-состояние — 2026-10-17

Миграции 0000–0006 и audit-health 0007 применены, legacy hashes сохранены; защищённый webhook
и Cloudflare Supabase-mode preview размещены. Реальные test-chat send/edit и
FlyWire/Storage проверки прошли. Production и основной scheduler выключены;
owner Auth/sign-in и manual completion на main ещё не проверены.
Актуальные доказательства: [HOSTED_RELEASE_VERIFICATION.md](HOSTED_RELEASE_VERIFICATION.md).
Нижележащие отчёты от предыдущих сессий являются историей, а не текущими blockers.

## Deadline reliability update — 2026-10-17

- [x] Immediate deduplicated creation alerts, silent bootstrap retained.
- [x] Exactly24/12/6/3/1h; persisted skipped/covered threshold audit.
- [x] Current-band coalescing, submitted/changed/expired queued reminder suppression.
- [x] Emoji presentation without internal IDs/scientific debug in ordinary messages.
- [x] Real Canvas read/rate-budget evidence; five-minute source cron with gates OFF.
- [x] Local Python195 passed, including finite staging-scenario regression; Deno15,
      Vitest28, TypeScript/build, browser4local+2private-mocked passed.
- [x] Local PostgreSQL17: all8 migrations, RPC/RLS/Storage/manual lifecycle and
      suppressed-job health regression passed; original7 migration files unchanged.
- [x] Backup authenticated decrypt verified; linked dry-run shows only health correction0007.
- [x] CI39049349780 SUCCESS:189Python+6optional-cache skips, all web/SQL/scientific checks.
- [x] Hosted39049711232 SUCCESS:11real test-group messages,1suppressed after submission,
      0duplicates;11neural associations/2verified private artifacts. Temporary test flag OFF.
- [x] Migration0007 applied with legacy hashes/grants preserved. Detailed evidence:
      [DEADLINE_NOTIFICATION_VERIFICATION.md](DEADLINE_NOTIFICATION_VERIFICATION.md).
- [ ] Production remains disabled; no merge authorized by this notification task.

## Remote preflight update — 2026-10-17

- [x] MCP/CLI target independently confirmed: Canvas-pusher, irjasmzytjeohwfpdnrl.
- [x] Actual legacy schema/grants/functions audited; 336/32/14 rows, four user IDs.
- [x] Seven pending migrations confirmed by remote CLI dry-run; none applied remotely.
- [x] Full encrypted database backup and password-free role export saved outside Git.
- [x] Full local restore verified by all legacy row SHA-256 checksums.
- [x] All seven migrations rehearsed against restored real schema/data; rows unchanged.
- [x] Four-owner SQL RLS and private Storage isolation verified locally, fixtures rolled back.
- [x] New local Canvas credential: 14 HTTP200, 6 courses, 20 assignments; read-only.
- [x] Real bot getMe/identity/test-chat separation checks; no Telegram messages sent.
- [x] Regression: 83 Python, 13 Deno, 28 Vitest; TypeScript/Vite build passed.
- [ ] Owner approval for migration of the existing hosted database remains required.
- [ ] Hosted legacy tables still have RLS disabled and broad anon/authenticated grants.
- [ ] Hosted webhook v10 still lacks the new secret-header/actor protections.
- [ ] Hosted Auth owner, FlyMind schema/telemetry, new webhook, test delivery and Cloudflare deployment remain pending.

Details, backup scope and evidence: [SUPABASE_REMOTE_PREFLIGHT.md](SUPABASE_REMOTE_PREFLIGHT.md).
The implementation milestones below are historical and do not imply hosted activation.

Status: locally implemented and verified; **external access required** for activation.
Branch feat/flymind-neural-poc. No production activation or main merge.

## Completed

- [x] Preserved existing Phases 1–3, authentic source bytes, model parameters and exports.
- [x] Audited source, schema, workflow, tests and credential availability without printing secrets.
- [x] Pagination, bounded retry, submission events, explicit silent bootstrap, persisted reminders.
- [x] Transactional CAS/outbox, leases, ambiguous-send quarantine, bounded workers and recovery.
- [x] Owner Auth/RLS, private bounded hashed Storage, shared-artifact-safe retention/orphan cleanup.
- [x] Secure webhook secret/actor/chat checks, durable update IDs, escaped responses and /brain.
- [x] Real/zero/shuffled controls, 22 synthetic product scenarios and ARM/x86 Linux benchmarks.
- [x] Authenticated Observatory history/replay/health; unchanged local scientific viewer.
- [x] Pinned CI, master scheduler gate, independent watchdog and opt-in weekly retention.
- [x] Production static build, browser checks, Cloudflare config and rollback instructions.
- [x] Real local PostgreSQL and local Supabase Auth/PostgREST/Storage validation.
- [x] Real Canvas GET attempted safely: HTTP401, zero mutations and Telegram messages.
- [x] Repository/history signature checks, dependency audits and reviewed scientific license.
- [x] Required architecture/model/deployment/security/operations/cost/Russian release documents.
- [x] Logical commits and safe feature push; final PR/CI evidence recorded in release handoff.

## Evidence

Initial baseline: 118 Python tests. Final full local suite: **137 passed**,
172 dependency deprecation warnings,83.40s. Ubuntu CI:131 passed/6 optional-cache skips.
Frontend:28 Vitest, TypeScript/build,4 local browser,
2 private mocked-HTTP browser tests. Webhook:3 Deno tests. Ruff critical checks pass.

Successful full Linux CI: https://github.com/fertur228/canvas-pusher/actions/runs/38545771927.
Real local Supabase evidence: local-supabase-validation.json. Linux scientific and batch
reports: neural-product-evaluation-linux-x86_64.json and neural-batch-validation-linux-x86_64.json.

Initial Linux test failure was investigated: exact spikes, float representation drift
<=3.64e-12 between ARM/x86, identical native repeats. Cross-platform numerical tolerance
1e-10 plus exact spikes/parameters and native hashes replaces an invalid universal-SHA
assumption. Scientific parameters and reference exports were not changed.

## External gates — intentionally not activated

- [ ] Renew CANVAS_API_KEY (actual first request returned401), verify CANVAS_API_URL,
      then repeat real schema/pagination check.
- [ ] Identify hosted isolated Supabase staging and provide server credentials/owner Auth mapping.
- [ ] Provide separate TEST_TELEGRAM_CHAT_ID + bot token; actual send/edit not yet performed.
- [ ] Restore Cloudflare authentication (expired OAuth) and identify preview project/account.
- [ ] Complete hosted full-path shadow validation and authorized production recipient gates.
- [ ] Owner review/merge main; configure CANVAS_WORKER_ENABLED and explicitly re-enable old
      workflow currently disabled_inactivity. No autonomous production schedule currently active.

Historical CI logs returned410: content audit unavailable. No claim of completed live
production RLS/log audit. No paid resources or production data modifications.

PR opened: https://github.com/fertur228/canvas-pusher/pull/1. No merge/deploy.
Local validation services stopped with backups retained; unrelated projects untouched.
Final available-history and static-build known-secret-signature scans: zero findings.

## Telegram product completion — 2026-10-14

- [x] Persistent menu and all seven owner-only commands; cached deadlines, grades,
      neural status and system health preserved.
- [x] Additive migration0006: bot-scoped update IDs, verified snapshots, paginated
      deadline RPC and locked manual-request lifecycle; owner RLS/privileged grants.
- [x] Manual dispatch checks flags/branch/completion workflow; actual workflow_run
      completion produces one persisted report, independently of academic backlog.
- [x] Undated new assignments, points/title updates, Canvas effective override dates,
      correct submission semantics, bounded escaped messages and safe Canvas links.
- [x] New-bot discovery, separate test-group identity, commands/webhook setup and
      private credential rotation tools. Disabled-idle scanner gate before secret updates.
- [x] Final local Python154 passed (78.16s), Deno13 passed, real PostgreSQL16 checks
      passed, Ruff critical checks passed. Frontend28 tests and TypeScript/build pass.
- [x] Core commit b6f7e17 pushed; GitHub CI38571466375 passed: Python145 +6 optional
      cache skips, Deno11, Vitest28, browser4 local +2 private HTTP-mock tests.
      Additional local rotation/null-validation tests are in the follow-up commit.
- [x] Credential/history signature scan: zero findings; authentic neural data/model untouched.
- [ ] Real Canvas token rotation: actual read-only run38570459817 returned401. The
      previously configured GitHub credential was still installed; replacement not available.
- [ ] Hosted migration0006, owner/bot binding, real Bot API configuration and test-chat
      delivery remain external activation gates. No production messages or deployment.
- [ ] Completion handler must exist on default branch; feature branch remains unmerged.

Detailed activation commands: TELEGRAM_ASSISTANT.md. Machine-readable evidence:
telegram-assistant-validation.json. Existing production data have not been changed.

## Hosted release checklist — 2026-10-17 (latest)

- [x] Explicit owner deployment authorization; exact existing Canvas-pusher target verified.
- [x] Encrypted backup/key verified; additional hosted settings/source archive encrypted.
- [x] Exactly seven unchanged migrations applied and recorded remotely.
- [x] Original legacy hashes preserved after migration and test bootstrap.
- [x] Hosted RLS/Storage owner/foreign/anon SQL checks passed with fixture rollback.
- [x] Old insecure webhook retired fail-closed503; isolated newbot webhook deployed.
- [x] Newbot commands, real sends/edits, duplicate and negative authorization checks.
- [x] Real Canvas silent bootstrap;20verified assignments and113snapshots.
- [x] Two actual FlyWire runs uploaded privately;2primary+2enrichment deliveries.
- [x] Supabase-mode Cloudflare preview deployed;HTTPS/auth gate verified in Chrome.
- [x] Real read-only cloud Canvas run39043798824 succeeded.
- [x] Full Python154 baseline plus new guard regression;Deno15;Vitest28.
- [x] Two successful real cloud two-scan workers; repeated scans have zero duplicate sends.
- [x] Cloud Linux synthetic event delivered, simulated and uploaded privately; three artifacts decode losslessly.
- [ ] Explicit owner email/Auth password setup, owner mapping and actual private browser replay.
- [ ] Review/merge gates and real default-branch /check completion.
- [ ] Scheduled primary-chat production rollout (intentionally disabled).
