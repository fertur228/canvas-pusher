# FlyMind

Canvas LMS monitoring and durable Telegram notifications, with an experimental neural
enrichment layer using the real adult Drosophila FlyWire connectome. The Neural
Observatory replays recorded model activity locally or through authenticated Supabase.

**Experimental, not biologically validated.** Real connectivity does not imply that a
fly understands deadlines. Operational urgency is deterministic. The fixed neural
model adds a separately labelled signal; it cannot suppress mandatory notifications.

- Canvas assignments, changed deadlines/grades/submission status, files, announcements
  and reminders with complete same-origin pagination and transient failure handling.
- Transactional snapshot/event/outbox persistence, leases, retries and ambiguous-send
  quarantine. No impossible exactly-once Telegram guarantee.
- Authentic 1,500-neuron/276,399-contact graph, fixed Brian2 LIF, no training and no
  direct Giant Fiber injection. Reproducible real/zero/shuffled scientific controls.
- React/TypeScript scientific dashboard: batched 3D graph, genuine soma coordinates
  where available, neuron inspector, raster, voltages, population, comparison/playback.
- Private owner Auth/RLS/Storage, bounded compressed telemetry, health and recovery.
- Finite GitHub Actions workers + Supabase + static Cloudflare Pages; no paid VPS.

## Run locally

```sh
python3 -m venv .venv/neural
.venv/neural/bin/pip install -r requirements-neural.lock
npm ci --prefix dashboard
npm --prefix dashboard run dev
```

Local scientific replay works without Canvas/Supabase/Telegram credentials.
Build: `npm --prefix dashboard run build`. Tests: `.venv/neural/bin/python -m pytest -q`,
`npm --prefix dashboard test`, `npm --prefix dashboard run test:e2e`,
`npm --prefix dashboard run test:e2e:private`.

Offline full event demonstration (synthetic academic events, captured Telegram, real
neural computation): `python -m src.flymind.demo --output /tmp/flymind-new-demo`.
Scientific evaluation: `python -m src.flymind.evaluate --output /tmp/flymind-evaluation.json`.
Run each export into a new path to preserve reproducible originals.

## Activation and evidence

The scheduled worker master gate CANVAS_WORKER_ENABLED defaults off. FlyMind defaults
off; its delivery defaults disabled and enrichment defaults shadow.
Production needs an explicitly mapped owner/account, silent bootstrap and test-chat
validation. Do not activate against an ambiguous database or Telegram recipient.

See [deployment](docs/DEPLOYMENT.md), [architecture](docs/ARCHITECTURE.md),
[model](docs/NEURAL_MODEL.md), [operations](docs/OPERATIONS.md),
[rollback](docs/ROLLBACK.md), [security](docs/SECURITY_REVIEW.md),
[costs](docs/COST_ESTIMATE.md), [progress](docs/DELIVERY_PROGRESS.md) and
[Russian release report](docs/FINAL_RELEASE_REPORT.md).

## Attribution

Scientific data: FlyWire FAFB v783 / pinned annotations, **CC BY-NC 4.0**, see
[data provenance](data/neural/README.md) and the source manifest for citations and
checksums. Retain attribution and the non-commercial restriction. Model assumptions,
model recordings and synthetic shuffled controls are distinguished from biological
measurements. No private academic records belong in this public repository.
