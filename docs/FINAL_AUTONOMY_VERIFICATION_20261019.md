# FlyMind — автономная production-работа подтверждена

Проверено 2026-10-19T17:13:29.561861+00:00 (UTC). **Бот LIVE, автоматический polling ACTIVE.**
Рабочий таймер — Supabase Cron `flymind-canvas-timer`, каждые пять минут.
GitHub получает `workflow_dispatch` от облачного таймера; это не native `schedule`
и не ручные тестовые запуски.

## Реальные последовательные циклы

| Cron UTC, 19.10.2026 | Cron runid | GitHub scanner | Snapshot UTC | Результат |
| --- | --- | --- | --- | --- |
| 17:05:00 | 4 | [39291086071](https://github.com/fertur228/canvas-pusher/actions/runs/39291086071) | 17:06:39 | success, errors=0, events=0 |
| 17:10:00 | 6 | [39291807325](https://github.com/fertur228/canvas-pusher/actions/runs/39291807325) | 17:11:49 | success, errors=0, events=0 |

Каждый цикл связан с persisted tick UUID, HTTP 202, успешными worker/scanner steps,
проверенным Canvas sync и записанным snapshot. HTTP 202 сам по себе не считается
завершением. Дублирующих GitHub runs для этих ticks нет; очередь после обоих чиста.
[Полные обезличенные доказательства](recovery-consecutive-cycles.json).

Дополнительно независимо перепроверены первые циклы 16:50/16:55 UTC:
[39288864521](https://github.com/fertur228/canvas-pusher/actions/runs/39288864521),
[39289622617](https://github.com/fertur228/canvas-pusher/actions/runs/39289622617).
В 17:00 таймер вернул `recent_scan` после ручного `/check` — корректное подавление
лишней работы, не пропущенный успешный scanner. В 17:05 polling продолжился.

## Ответы владельцу

| Вопрос | Проверенный результат |
| --- | --- |
| @canvasheimdall_bot LIVE? | Да; owner/private-chat/bot binding и secure webhook подтверждены. |
| Автоматический polling активен? | Да, `*/5 * * * *`, облачный Supabase Cron fallback. |
| Два реальных запуска от часов прошли? | Да, таблица выше; плюс ранее подтверждённая пара 16:50/16:55. |
| Snapshots обновляются? | Да, последний 2026-10-19T17:11:49.521492+00:00; все исходные 20 assignment snapshots сохранены, 18 актуально подтверждены Canvas. |
| Outbox здоров? | Да: 3 `send.done` с message IDs; pending/running/dead/ambiguous — 0. |
| `/check` работает с серверным credential? | Да; свежий запрос 16:57 UTC, scanner и completion success, одна попытка доставки результата. |
| Reminders правильные? | Ровно 24/12/6/3/1 ч; submitted подавляются, смены срока учитываются, пропущенные пороги объединяются. |
| Neural engine работает? | Да, фиксированная настоящая FlyWire модель прошла Linux CI и local suite; production `last_neural_success=null`, поскольку новых подходящих событий не было. |
| Observatory доступна? | Да, HTTP 200; private Storage/SHA проверены. Ранее реальные isolated Auth/RLS/headless replay пройдены. |
| Стоимость? | Оценка $0/месяц при текущем масштабе и бесплатных лимитах; платные сервисы не включались. |
| MacBook должен работать? | Нет. В runtime участвуют Supabase, GitHub Actions, Canvas и Telegram. |
| Остались внешние блокеры? | Блокирующих работу сейчас нет. Native cron не подтверждён; GitHub сообщает восстановление, но outage всего Actions затронет и fallback. |

Новые assignments, включая задания без срока, уведомляются при первом успешном
обнаружении. Silent bootstrap не повторялся. Обычная доставка выполняется перед
нейронной обработкой и не требует её успеха. Никаких искусственных учебных событий
или повторного launch smoke в личный чат не отправлялось.

Меню: **📅 Дедлайны · 📊 Успеваемость · 🔄 Обновить сейчас**.
Команды `/start`, `/deadlines`, `/stats`, `/check`, `/brain`, `/status` зарегистрированы
для проверенного private chat; `/menu` также поддерживается.
Свежий `/check`: [scanner 39289986779](https://github.com/fertur228/canvas-pusher/actions/runs/39289986779),
[completion 39290199906](https://github.com/fertur228/canvas-pusher/actions/runs/39290199906).
Запись completed в 16:59:18 UTC, единственный completion job — done, attempts=1,
message ID сохранён. [Доказательство](recovery-manual-check-verification.json).
Это проверенный hosted HTTP-запрос, не утверждение о нажатии кнопки в клиенте Telegram.

## Релиз, безопасность и контроль состояния

[PR #3](https://github.com/fertur228/canvas-pusher/pull/3) merged 16:48:52 UTC.
Runtime commit main: **4577094cbf32b076f71cf00cee7307769b1c9317**.
Его дерево совпало с проверенным `ab9e023aa78a2346b581481eee0a481885aad84b`.
Все обязательные checks прошли:
[CI 39287097237](https://github.com/fertur228/canvas-pusher/actions/runs/39287097237),
[CI 39287090458](https://github.com/fertur228/canvas-pusher/actions/runs/39287090458).
Review P1 о JWT gateway исправлен и thread resolved. Новых runtime/model changes
при финальной проверке не потребовалось; последующее сохранение отчёта меняет только документацию.

Повторные local проверки: **212 Python, 23 Deno, 36 Vitest**, TypeScript/build — pass.
Все девять migration contracts/RLS/Storage/manual/timer checks прошли в CI на точном
release head; hosted migration history и исходные 336/32/14 row hashes сверены вновь.
Backup успешно аутентифицирован, расшифрован в памяти и проверен по SHA; не восстановлен
поверх production. Никакие аккаунты, credentials, snapshots или message IDs не сбрасывались.

HMAC: неверная/просроченная подпись 403; завершённый tick — `duplicate_or_recent`,
без dispatch. Анонимный/browser доступ к ledger/RPC запрещён. Vault/Edge digests
совпадают, timer enabled=true, dry_run=false. Неопределённый результат POST не
пересылается автоматически. GitHub concurrency сериализует worker; transactional
snapshot/outbox CAS и event IDs предотвращают повторную доставку при пересечении таймеров.
Master gate false проверен regression test, без остановки работающего production.
[Security evidence](recovery-security-verification.json),
[independent audit](recovery-independent-verification.json).

Включён существующий независимый `flymind-stale-heartbeat`, только для production:
каждые пять минут, delayed после 30 минут, failed после 90. Первый реальный запуск
17:10 UTC: success / UPDATE 0 — свежие данные не изменены. Telegram он не вызывает.
Отдельный hourly GitHub watchdog остаётся active; прошлый stale scanner им был обнаружен.
[Monitoring evidence](production-watchdog-verification.json).

Текущие GitHub flags:

```text
CANVAS_WORKER_ENABLED=true
FLYMIND_ENABLED=true
DELIVERY_MODE=production
FLYMIND_PRODUCTION_AUTHORIZED=true
FLYMIND_MODE=shadow
FLYMIND_NEURAL_ENABLED=true
FLYMIND_MAX_NEURAL=2
FLYMIND_RETENTION_ENABLED=false
```

`NEURAL_TELEMETRY_ENABLED` эффективно true через workflow default. Timer Edge:
`FLYMIND_SCHEDULE_ENABLED=true`, `FLYMIND_SCHEDULE_DRY_RUN=false`.
Новый `FLYMIND_GITHUB_PAT` обслуживает и `/check`, и fallback; legacy PAT не используется
таймером. Его будущая недействительность затронет оба dispatch-пути.

## Observatory, стоимость, остановка

[Neural Observatory](https://flymind-preview.flymind-observatory.pages.dev/) сохранена.
Шесть private artifacts: 912139 bytes, все SHA совпали. База около 14.18 MB.
Модель: 1500 настоящих FlyWire neurons / 276399 contacts; параметры и connectivity
не менялись. Experimental readout не является биологической валидацией.

Оценка 288 cycles/day: около 8640 Edge calls и 13824 runner minutes за 30 дней
по первым двум измеренным jobs. Стандартные runners публичного репозитория бесплатны
по [GitHub billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions);
[Supabase Free](https://supabase.com/pricing) и
[Cloudflare Pages](https://developers.cloudflare.com/pages/functions/pricing/) покрывают текущий масштаб.
Пятиминутный период — не SLA. [Инцидент GitHub](https://www.githubstatus.com/incidents/8tzbpcnl75jp)
закрыт; последняя проверка Status API — All Systems Operational.

Быстрая остановка новых сканирований:

```sh
gh variable set CANVAS_WORKER_ENABLED --repo fertur228/canvas-pusher --body false
```

Остановить только fallback без удаления истории:

```sql
SELECT cron.alter_job(jobid, active := false)
FROM cron.job WHERE jobname = 'flymind-canvas-timer';
```

Уже исполняющийся worker сохраняет свои переменные — при аварии проверить и отдельно
отменить конкретный run. Neural можно остановить через `FLYMIND_NEURAL_ENABLED=false`,
сохранив `FLYMIND_ENABLED=true`. Не сбрасывать outbox/snapshots/reminders и не возвращать
небезопасный legacy webhook. [Полный rollback](ROLLBACK.md).
