# FlyMind — фактический выпуск18октября2026

Проверка продолжения 19 октября: remote read access восстановлен. Прежний
`GITHUB_PAT` не менялся с 17 марта; `FLYMIND_GITHUB_PAT` отсутствует. Это выбранный
сервером credential, а не работающий локальный `gh` OAuth credential. HTTP 401
не позволяет различить истечение срока, отзыв и иной невалидный токен.
Новый токен должен быть создан владельцем и введён в скрытый terminal prompt.
Production baseline сохранён, jobs=0; первичная Telegram identity повторно
подтверждена без отправки сообщений. Свежий Canvas GET: 14×200, 6 курсов,
20 заданий, errors=0. Исходные row hashes и восемь миграций совпадают.
[Санитизированные результаты](resume-readonly-verification.json).

Статус: **STAGING VERIFIED — PRODUCTION DISABLED**.
Личная Chrome-сессия больше не требуется. Внешний blocker конкретный: старый
серверный GitHub PAT возвращает401; новый repository-scoped credential пока не
установлен. Это не проблема Supabase Auth, Canvas или научного движка.

## Git и внедрённые исправления

PR1 **MERGED**18октября14:41:01UTC:
https://github.com/fertur228/canvas-pusher/pull/1

Main: `84026aa74098db8aaf4396086d26aad961e23fd7`.
Reviewed source: `70b0367fa81579c453c73befa7d26a76622355c5`.
CI: [39136639045](https://github.com/fertur228/canvas-pusher/actions/runs/39136639045)
и [39136643214](https://github.com/fertur228/canvas-pusher/actions/runs/39136643214)
SUCCESS, offline/database.

- `73aa3cb`: текущие grades в account-scoped snapshot; никакой записи worker в
  legacy course_grades. Zero/null и оценочный GPA без выдуманного4.0для физкультуры.
- `b6a4872`: воспроизводимый реальный Auth/RLS/Storage/headless replay без личного Chrome.
- `a02abbf`: фактические результаты и сохранность legacy данных.
- `70b0367`: исправлено подтверждённое P2 review замечание: первый null enrollment
  не скрывает последующий реальный score, включая0. Тесты сначала воспроизвели дефект.
- После merge в feature-ветке `d04ff3a`: локальный безопасный scoped-token helper,
 4теста и secret scanner для github_pat_. [CI39138087566](https://github.com/fertur228/canvas-pusher/actions/runs/39138087566) SUCCESS.
  Это операторский setup tool; исполняемый cloud runtime остаётся main84026aa.

## Supabase, Canvas и безопасность

Только существующий Canvas-pusher: `irjasmzytjeohwfpdnrl`.
Восемь миграций0000–0007 присутствуют. Повторно не применялись. Все исходные
336canvas_state/32course_grades/14health_checks совпали с backup по полным row hashes,
включая повторную проверку ПОСЛЕ production bootstrap. Шесть старых test-grade rows
также оставлены; нынешний worker пишет текущие оценки в flymind_snapshots.

Encrypted backup и отдельный ключ сохранены. Fernet authenticated decrypt,
plaintext/ciphertext SHA-256 и PGDMP header повторно проверены; предыдущая полная
изолированная PostgreSQL17 реставрация подтверждена. Backup не включает новые
Storage bytes/новые Auth/settings после его даты; автоматический restore поверх
новых данных запрещён.

RLS включён, bucket private с пределом4MiB. SQL owner/foreign/anonymous/worker-RPC
проверки выполнены с ROLLBACK. Новый production owner mapping дополнительно проверен
SQL-ролями. Исторические четыре user_id не объединялись. Старый insecure endpoint
fail-closed503. Новая function использует namespaced secrets и exact bot/user/chat.
Временная credential-diagnostic function создана только для read-only statuses и
удалена; существующие функции/пользователи не удалялись. Network Media не трогался.

Существующий owner Auth UUID сверён с приватным owner evidence и реальным Auth API.
Новый отдельный production account привязан к тому же владельцу и проверенному
private Telegram recipient; test account и вся его история сохранены.
Production account после подготовки снова disabled, baseline сохранён.

Реальный Canvas:6курсов/20заданий/91file/2announcement. Все операции GET.
Production silent bootstrap завершён18октября14:50:27UTC:0events/0errors/0messages.
Проверенный deadline RPC:upcoming4,overdue3,today0,week2,month2,all10,undated3.
Сортировка и отсутствие submitted assignments проверены. Grade не считается submission.

## Реальные облачные исполнения

| Run | Что реально проверено | Результат |
| --- | --- | --- |
| [39138507178](https://github.com/fertur228/canvas-pusher/actions/runs/39138507178) | main:2Canvas scans, Supabase, Telegram test group, настоящий FlyWire/Storage | SUCCESS;139.91s worker portion;0errors/0new scan events/0duplicate sends |
| [39138683754](https://github.com/fertur228/canvas-pusher/actions/runs/39138683754) | main:отдельный read-only Canvas preflight | SUCCESS;никаких DB writes/Telegram |
| [39138826508](https://github.com/fertur228/canvas-pusher/actions/runs/39138826508) | main:операторский dispatch сохранённого manual request, настоящий scan | SUCCESS;verified15:06:00UTC,events0/errors0 |
| [39138951739](https://github.com/fertur228/canvas-pusher/actions/runs/39138951739) | trusted workflow_run completion, затем повтор того же finalizer | SUCCESS дважды;request completed,1Telegram send attempt,0duplicates |

Последний real persisted Canvas check:15:06:00.649195UTC =20:06:00Asia/Almaty.
Все перечисленные run — **workflow_dispatch/workflow_run, не scheduled**.
Два scheduled production cycles НЕ проверены и не объявляются успешными.

GitHub anomaly: первый операторский run39137536308 остался queued без jobs, тогда
как cancel API сообщил already completed. Причину платформенной рассинхронизации
не удалось доказать. Выполнен один явно обозначенный операторский recovery по ТОМУ
ЖЕ persisted request. Atomic manual_start допустил только winner39138826508.
Поздний старт первоначального run проверенно отвергается; исходная история не удалена.
Обычный webhook не делает автоматических повторных dispatch при uncertain outcome.

Это доказывает cloud scanner и completion lifecycle, но **не исправляет истёкший
серверный PAT**. Настоящий HTTP `/check` через hosted webhook остановлен до dispatch:
GitHub401,request не создан, ложного «синхронизация завершена» нет. Успешный
операторский CLI credential не экспортировался в Supabase и не выдаётся за работающий
webhook credential. [Completion evidence](operator-main-completion-verification.json).

## Telegram и нейронный контур

Webhook deployed: flymind-telegram-webhook, только существующая verified test group.
Реальные /start,/menu,/deadlines,/stats,/status,/brain, фильтры, pagination, send/edit,
удаление старой persistent keyboard, duplicate updates и4negative auth checks passed.
Три inline menu actions и три visible filters сохранены. [Evidence](release-webhook-test.json).

В новом outbox E2E доставлены2сообщения с сохранёнными IDs: явно синтетическое
тестовое задание и реальный completion report. Повтор finalizer не создал второй
result send. Primary messages: **0**; production smoke НЕ выполнен до credential gate.
Test queue:send.done18/simulate.done16/edit.done16; новых pending/ambiguous jobs0.

Новый main/Linux neural run:1500real neurons,25206edge rows/276399contacts,
344spikes,282active cells,GF2/2;CPU4.416s,wall5.006s,lifetime peak189.74MiB.
Compressed artifact162418bytes; private upload/download SHA-256 совпал.
Shadow edit подавлен; первичное сообщение уже доставлено независимо от simulation.
[Actual measurements](release-main-neural-verification.json).

Стимул инициирован явно синтетическим academic event без дедлайна и с0points.
Новых реальных university assignments во время scans не появилось. Canvas не менялся.
Сеть/параметры не изменялись. Biological validation=false; deadline encoding/readout
— инженерные соглашения, а не доказанное понимание университетских сроков мухой.

Reminders ровно24/12/6/3/1h, creation alert на первом обнаружении, initial bootstrap
silent, поздние thresholds coalesced, submitted/deadline rechecked перед delivery.
Regression и прежний реальный deadline test checkpoint сохранены. Повтор checkpoint
не выдаётся за11новых Telegram deliveries.

## Observatory

Действующий private preview:
https://flymind-preview.flymind-observatory.pages.dev/

Реальные Supabase password grants двух временных изолированных пользователей,
user JWT/RLS, private download+SHA, frontend decoder и headless hosted replay passed.
Account selector,health,history,834spikes,voltage,3D canvas,play/pause/scrub,comparison,
soma1497/1500,logout;JS errors0. Service-role key не попадал в браузерный процесс.
Временные users/records/object удалены по точному журналу, cleanup проверен.
Никаких HTTP mocks или личного Chrome profile.

**Actual owner-browser replay остаётся не подтверждён агентом.** Это честно
отдельная отметка, больше не Telegram release blocker по указанию владельца.
[Report](hosted-auth-headless-verification.json), [reproducible procedure](AUTOMATED_RELEASE_VERIFICATION.md).

## Тесты и состояние flags

- Python локально206passed/172warnings/80.08s, затем4helper tests passed.
- Merge CI:200passed+6optional upstream-cache skips; эти6локально прошли.
- Helper CI:204passed+6skips. Научные Linux controls и multi-event simulation passed.
- Deno17;Vitest36;TypeScript/Vite build;Playwright4local+7private HTTP-mock;отдельно
  real hosted headless без mocks. PostgreSQL17local/16CI RPC/RLS/migrations passed.
- Ruff critical checks и actionlint1.7.12 passed.
- Secret/history/configured-value scans:0findings; backup/env/key ignored.
- Нефатальные dependency warnings и Three.js882.89kB/238.57kBgzip остаются.

После тестового окна:
CANVAS_WORKER_ENABLED=false,FLYMIND_ENABLED=false,DELIVERY_MODE=disabled,
FLYMIND_PRODUCTION_AUTHORIZED=false,FLYMIND_TEST_CHAT_VALIDATION=false,
FLYMIND_MODE=shadow. Edge FLYMIND_MANUAL_SYNC_ENABLED=false.
Workflow definition active с cron2-59/5, но master gate запрещает scanner jobs.
Production account disabled, snapshots/history сохранены. Test webhook остаётся
в test scope. Retention не активирован, ничего из старых records/artifacts не удалено.

## Стоимость, автономность и следующий необходимый шаг

Cloud executions реально состоялись на GitHub Linux без localhost. MacBook для
архитектуры не нужен; **текущий автономный production monitoring ещё выключен**.
При5min это до8640runs/30days. Ориентир60–120s/job ⇒8640–17280runner-min/month;
в PUBLIC repo standard Ubuntu runners бесплатны. При20neural events/day и~162KB
artifact около97MB/month до reuse/retention. Сейчас6objects/~0.91MB.
Supabase Free/Pages используются без покупки; квоты и scheduling не дают SLA.
[Official Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions),
[best-effort schedule](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule),
[Supabase](https://supabase.com/pricing),[Pages limits](https://developers.cloudflare.com/pages/platform/limits/).

Единственное требуемое действие владельца сейчас: создать новый scoped GitHub token
и ввести его скрыто через `python -m src.flymind.dispatch_setup`.
[Точные permissions и команда](DISPATCH_CREDENTIAL_SETUP.md). Не отправлять token
в чат. Нужны ActionsRW/VariablesR/ContentsR только canvas-pusher; личный Chrome
и owner password не требуются. После этого остаются исполнительские gates агента:
реальный webhook /check, controlled primary smoke, production shadow activation и
две фактические scheduled cycles. Они не были подменены mocks/manual runs.

Quick stop: CANVAS_WORKER_ENABLED=false. Neural-only stop:FLYMIND_NEURAL_ENABLED=false,
сохраняя FLYMIND_ENABLED=true при активном master. Delivery stop:DELIVERY_MODE=disabled.
Не очищать jobs/messageIDs/snapshots, не возвращать insecure webhook, не делать
автоматический backup restore поверх новых writes. [Rollback](ROLLBACK.md).
