# FlyMind — подтверждённая автономная работа, 19 октября 2026

**Production Telegram работает автономно через Supabase Cron → GitHub Actions.**
Два последовательных запуска от реальных облачных часов завершились успешно.
Важное ограничение: первоначальный критерий двух нативных GitHub-событий
`event=schedule` не пройден. Их emitter не восстановился; рабочий облачный timer
создаёт `workflow_dispatch`. Это автоматические, а не ручные запускаемые агентом
сканирования. Источник запуска не переименован в доказательствах.

## Подтверждённые запуски

| Источник / время UTC | GitHub run | Итог |
|---|---|---|
| Supabase Cron, 16:50:00 | [39288864521](https://github.com/fertur228/canvas-pusher/actions/runs/39288864521) | success; job и scanner-step success |
| Supabase Cron, 16:55:00 | [39289622617](https://github.com/fertur228/canvas-pusher/actions/runs/39289622617) | success; job и scanner-step success |

Оба run исполняли `main` **4577094cbf32b076f71cf00cee7307769b1c9317**.
Каждый сопоставлен с уникальным tick в database ledger и конкретным успешным
`cron.job_run_details` (1 и 2). HTTP202 сопоставлен с фактическим завершением worker,
а не принят за завершение синхронизации. После включения timer агент не отправлял
workflow dispatch. [Машинные доказательства](scheduler-cloud-verification.json).

Контрольный snapshot второй пары: **16:56:32 UTC / 21:56:32 Asia/Almaty**.
Последующая read-only проверка17:09 UTC подтвердила snapshot17:06:39 UTC и healthy: runtime продолжил работу.
Health healthy; незавершённых, ambiguous и dead outbox jobs — 0. Во время двух timer-циклов два исходных durable send jobs остались двумя:
повторных и исторических уведомлений не возникло. Позднее завершился отдельный
manual refresh; его один новый completion увеличил итог до трёх durable sends.
Первый/второй worker заняли 105/87 секунд. Все runtime-компоненты находятся в облаке;
localhost, личный Chrome и включённый MacBook им не нужны. Физически выключение
MacBook не выполнялось.

## Telegram и Canvas

Бот: https://t.me/canvasheimdall_bot. Bot API подтвердил правильный private chat,
bot identity и целевой защищённый webhook; pending updates — 0. Все семь команд
зарегистрированы в owner chat scope: `/start`, `/menu`, `/deadlines`, `/check`,
`/stats`, `/brain`, `/status`. Глобальный список команд намеренно пуст.
Три inline-кнопки и безопасное удаление старой reply keyboard были внедрены и
проверены ранее; их реализация не изменялась в этом выпуске.

Новый серверный `FLYMIND_GITHUB_PAT` работает. Реальный личный `/check` ранее дал
[scanner39253501947](https://github.com/fertur228/canvas-pusher/actions/runs/39253501947)
и [completion39253717268](https://github.com/fertur228/canvas-pusher/actions/runs/39253717268),
оба success; состояние completed, сообщение сохранено, повтор update подавлен.
Новая функция также проверила этот серверный PAT и успешно выполнила два dispatch.
Новый токен не извлекался из Supabase и не публиковался.

После merge независимо появился ещё один настоящий manual request:
[39289986779](https://github.com/fertur228/canvas-pusher/actions/runs/39289986779),
main4577094, success; request completed, Canvas verified, errors0, completion
доставлен с одной попытки и сохранённым message ID. Этот run не был инициирован
наблюдателем и не засчитан как scheduled. Tick17:00 корректно вернул recent_scan
и не создал лишний worker после него. [Отдельное доказательство](production-new-main-check-verification.json).

Текущий проверенный снимок содержит 18 актуальных assignments. Исторические snapshots
не удалялись. В списке невыполненных: 8 всего, 2 на ближайшую неделю, 1 просроченное,
3 без даты. Данные не stale. Названия, оценки и личные идентификаторы в отчёт не
включены. [Текущая проверка бота и снимков](production-current-bot-verification.json).

Silent bootstrap повторно не выполнялся. Сохраняются immediate creation alerts даже
без deadline и ровно24/12/6/3/1 ч reminders, подавление устаревших порогов и повторов,
учёт подтверждённой submission, отдельная обязательная доставка при neural failure.
Наблюдатель не отправлял новые Telegram-сообщения. В production сохранены один
разрешённый smoke и два completion от отдельных manual requests. Отдельные `/check`
acknowledgements не включены в число durable send jobs.
Новые университетские задания для теста не создавались.

## Что изменено и развёрнуто

PR1 был merged ранее. После полного CI и review merged
[PR3](https://github.com/fertur228/canvas-pusher/pull/3). Перед merge закрывались новые
manual requests, проверялось отсутствие активной работы, временно отключался master
flag. Дерево main совпало с проверенным head `ab9e023`; затем флаги восстановлены.

- Edge `flymind-scheduled-dispatch`: HMAC-SHA256, 90s freshness, точная production
  identity, release flags, проверка активных workers/недавних scans, один dispatch.
- Migration `202610190008_scheduler_bridge.sql`: отдельный закрытый ledger и
  service-only RPC с advisory lock. До network POST сохраняется ambiguous;
  потеря ответа не вызывает слепую повторную отправку.
- Private Vault secret и `flymind-canvas-timer`, `*/5 * * * *`. После dry-run
  timer включён в16:49:53 UTC. Native workflow остаётся active; если он заработает,
  проверки текущей работы/heartbeat уменьшают дублирующиеся сканирования.
- Workflow получил только correlation input `scheduler_tick` и prefix `timer-`;
  manual completion не путает его с UUID запроса владельца. Scanner/outbox/neural
  model/Telegram presentation не переписывались.

Production: `CANVAS_WORKER_ENABLED=true`, `FLYMIND_ENABLED=true`,
`DELIVERY_MODE=production`, `FLYMIND_PRODUCTION_AUTHORIZED=true`,
`FLYMIND_MODE=shadow`, `FLYMIND_NEURAL_ENABLED=true`, `NEURAL_TELEMETRY_ENABLED=true`.
Нейронное обогащение не изменяет обязательные сообщения в shadow mode.

## Данные и безопасность

Цель — только `irjasmzytjeohwfpdnrl`; Network Media не затрагивался. Теперь записано
9 migrations: исходные 0000–0007 не повторялись и не редактировались. Исходные 336
Canvas / 32 исторических grades / 14 health records повторно совпали по SHA-256,
включая проверку после двух новых cloud scans. RLS и private Storage сохранены.
Зашифрованный backup и отдельный ключ доступны; authenticated decryption и SHA
снова проверены. Backup не заменялся и не восстанавливался поверх hosted data.

Реальные отрицательные проверки: неверная/просроченная HMAC — HTTP 403; anonymous ledger/RPC
запрещены; повторный и перекрывающийся service claim в test account подавлены.
Создан только один явно помеченный test timer audit record, без dispatch/Telegram.
`net` имеет provider-managed SQL grants, но не экспонируется через PostgREST:
реальный anonymous запрос406/PGRST106. В его очереди нет ключа/PAT/учебных данных.
Обходить provider grants не пытались. Подробности — [security review](SECURITY_REVIEW.md).

Supabase MCP потребовал повторной авторизации; использована отдельно действующая
CLI-авторизация того же проекта. Новая интерактивная авторизация для runtime не
требуется. Известных secret signatures в 258 candidate files/Git history не найдено;
это ограниченный scan, не математическое доказательство отсутствия любых секретов.

## Проверки и научная часть

Точный release head: CI [39287097237](https://github.com/fertur228/canvas-pusher/actions/runs/39287097237)
и [39287090458](https://github.com/fertur228/canvas-pusher/actions/runs/39287090458),
все 4 обязательных checks success. Python: 206 passed / 6 optional-cache skipped;
Deno: 23 passed; Vitest: 36 passed; TypeScript/build success; browser: 4 + 7 passed;
PostgreSQL RPC/RLS/Storage/manual lifecycle/timer checks success. Локально полный
научный pytest дал 211 passed до добавления ещё одного workflow contract test;
этот новый тест также прошёл отдельно. Assertions не ослаблялись.

Linux CI снова выполнил подлинный фиксированный FlyWire model: 1500 neuron IDs,
276399 contacts. Weak: 344 spikes / 282 active / GF 2+2; strong: 834 / 418 / GF 3+4.
Strong simulation CPU 1.807 s, total CPU 2.748 s, wall 2.739 s, lifetime peak 197.3 MiB.
Повторяемость real/zero weak/strong подтверждена. Это модельные измерения, не
биологическая валидация или доказательство пользы для приоритизации дедлайнов.
[Новые измерения Linux CI](scheduler-release-neural-evidence.json).

Eligible production events во время двух scan не возникли, поэтому production
`last_neural_success` ещё null. Не выдаём CI/test-account runs за новые нейронные
ответы на реальные университетские события. Ранее подтверждённые реальные
Linux/Supabase/test-chat neural E2E и шесть private artifacts сохраняются.

Observatory остаётся по адресу https://flymind-preview.flymind-observatory.pages.dev/.
Реальные isolated Auth/JWT/RLS/private Storage/SHA/hosted headless replay прошли
ранее; пользовательский Chrome не использовался. Именно owner-browser replay
агентом не подтверждён, что не блокирует независимый Telegram runtime.

## Стоимость, ограничения и остановка

Среднее 96 s на worker → около 460.8 runner min/day, 13824 min/30 days при 288 cycles/day.
Публичный репозиторий использует стандартные бесплатные GitHub runners. Новый
таймер добавляет около 8640 Edge invocations/30days и небольшие ledger rows.
Платные планы, runners и VPS не подключались. Private artifacts пока≈0.912MB. Это
оценка, а не измеренный месяц и не гарантия бесплатной работы при любом росте.

GitHub официально сообщил о деградации Actions 19 октября; native scheduled emitter
в этой сессии не восстановился. [Инцидент](https://www.githubstatus.com/incidents/8tzbpcnl75jp).
Fallback устраняет зависимость от native cron emitter, но использует GitHub runners
и не устраняет outage всего Actions. Пять минут — период timer, не SLA доставки.
Vite large-chunk warning и Brian2/pyparsing deprecations остаются известными,
успешные tests/build они не блокировали. Научная модель остаётся experimental.

Быстрый stop новых scans/dispatch:

```sh
gh variable set CANVAS_WORKER_ENABLED --repo fertur228/canvas-pusher --body false
```

Уже запущенный job эта переменная не останавливает: при необходимости проверить
и отменить конкретный активный run. Timer-only stop — `cron.alter_job(...,active:=false)`
из [ROLLBACK.md](ROLLBACK.md). Neural отдельно выключается через
`FLYMIND_NEURAL_ENABLED=false`; не выключать весь `FLYMIND_ENABLED`, чтобы не
вернуться к legacy delivery. Не удалять snapshots, сообщения, очереди или ledger.

От владельца сейчас не требуется новый токен, Chrome или работающий ноутбук.
Можно пользоваться `/start`, `/deadlines` и `/check` в личном чате.
