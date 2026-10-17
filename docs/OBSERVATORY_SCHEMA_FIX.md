# Hosted Observatory account-query correction — 2026-10-18

Target: Canvas-pusher `irjasmzytjeohwfpdnrl`, existing Cloudflare preview,
feature branch `feat/flymind-neural-poc`. No migrations or hosted records changed.

## Root cause and reproduction

The account selector added in `de266f6` ordered `flymind_accounts` by `created_at`.
Supabase MCP confirmed the actual columns after all eight migrations:
`id`, `telegram_chat_id`, `canvas_origin`, `owner_id`, `enabled`,
`initialized_at`, `telegram_bot_id`, `telegram_user_id`. There is no `created_at`.

Real PostgREST reproduction, using server-side credentials solely to isolate query
parsing: `select=id,telegram_chat_id,enabled&order=created_at.asc` returned
HTTP **400**, SQLSTATE **42703**. The same query ordered by `id.asc` returned
HTTP **200**, one row. Credentials and response records were not logged.
This reproduction does not claim an authenticated owner browser request.

The original catch block collapsed query failure and a successful empty result
into one misleading mapping/session message. HTTP mocks accepted arbitrary order
columns, so previous browser tests did not catch the schema mismatch.

## Correction and regression

- `dashboard/src/accountQuery.json` defines the exact account projection and `id`
  ordering. The component consumes this contract.
- `tests/flymind/postgres_checks.py` now executes that frontend query as the
  authenticated role against a disposable PostgreSQL database with every actual
  migration applied. An invalid order column makes the database CI job fail.
- Private browser fixtures assert the exact outgoing projection/order.
- Safe diagnostics distinguish query/schema, authentication, access, service and
  network failure. Only scope, HTTP status and validated error code are shown;
  server message/details, tokens and academic content are not logged/displayed.
- A successful empty account response has its own owner-mapping message.
- Refresh retries account discovery as well as health/history, preserving the
  chosen account when it remains accessible. Account-scoped replay remains intact.

## Evidence

- MCP confirmed eight migrations and account RLS enabled.
- Hosted SQL `SET LOCAL ROLE authenticated` with the existing mapped owner claim:
  one account, one health row, 15 experiment associations, five private artifacts.
  Unrelated claim: zero of each. Transactions rolled back. This is SQL RLS evidence,
  not a substitute for an owner-authenticated browser replay.
- Legacy counts remain 336 Canvas, 38 grades (32 original plus six prior test),
  14 health. Private bucket remains `public=false`.
- Vitest: 36 passed. TypeScript and production build passed.
- Browser: four local plus seven private HTTP-mock tests passed, including the
  real immutable engine export, schema mismatch, 401, 403, missing mapping, 503
  and successful retry. The 503 test waits for the SDK's 1+2+4 second backoff and
  asserts all three automatic retries; the first test timeout was corrected.
- Local PostgreSQL17 migrations/RPC/RLS/Storage/manual lifecycle and new frontend
  query contract passed. Database records, RLS and scientific artifacts unchanged.

## Release gate

Deployment and owner browser verification are recorded in the delivery report.
The available Chrome tab was at the sign-in screen on inspection; no existing
authenticated session was extracted or bypassed. Sessions intentionally remain
in memory only, so a new deployed build requires a fresh owner sign-in.
PR merge, production delivery and scheduler activation remain gated on real replay
and the subsequent established release checks.
