# FlyMind: автоматическая проверка приватного контура, 18 октября 2026

Этот документ заменяет прежнее требование держать личную Chrome-вкладку открытой.
По прямому указанию владельца Telegram выпускается независимо от Observatory.
Фактический owner-browser replay остаётся **не подтверждён агентом**. Пароль
владельца не извлекался и не менялся; личный профиль браузера не использовался.

## Проверено реальными сервисами

`PYTHONPATH=. .venv/release/bin/python scripts/verify_hosted_auth.py --isolated-hosted-test`
создаёт две временные Auth identity через административный API, затем входит
обычным password grant через публичный ключ. Пользовательский JWT проверяет RLS,
свой account/health/event/experiment, запрет чужих и legacy records, worker RPC и
приватный Storage. У identity нет доступа к существующим записям владельца.

Тестовый академический event явно синтетический. Нейронный artifact — настоящий
неизменённый `strong-1.json.gz`:1500нейронов,834spikes. Его SHA-256 проверяется
после настоящего download. Headless Playwright открывает фактический HTTPS preview
https://flymind-preview.flymind-observatory.pages.dev/ без HTTP mocks, входит
тестовым пользователем и проверяет selector,health,history,spikes,voltage,3D canvas,
play/pause/scrub,comparison и очистку данных после logout. JS errors0.
Service-role key не передаётся процессу браузера. Пароли временные, только в памяти.

Точные временные user/account/event/health/storage resources журналируются приватно
и удаляются в finally; чужие ресурсы не удаляются. Повтор запрещён при незавершённой
очистке предыдущего теста. [Обезличенный результат](hosted-auth-headless-verification.json).
Это **реальный тест изолированного пользователя**, не owner-browser validation.
Telegram сообщений этот тест не отправляет.

## Исправление перед production bootstrap

Выявлено, что личный chat ID уже имеет8исторических `course_grades`. Прежний worker
upsert заменил бы эти записи при bootstrap. Теперь текущие оценки хранятся только
в `flymind_snapshots`, `kind=report`, `entity_key=0:course_grades`, account-scoped,
с optimistic revision и временем успешного чтения. `/stats` читает этот снимок.
Legacy таблицы сохраняются. Пустой успешный список очищает только текущий снимок,
ошибка Canvas оставляет предыдущий. Сохранение не создаёт уведомлений или neural jobs.
Ноль остаётся оценкой, null — отсутствием оценки; GPA приблизительный, без
выдуманного4.0для физкультуры. Schema migrations не требуются.

## Release gates

- Восемь hosted миграций присутствуют; повторное применение не требуется.
- Encrypted backup: Fernet authentication, ciphertext/plaintext SHA-256, PGDMP
  header, прежняя полноценная изолированная реставрация подтверждены.
- Первые семь migration SHA неизменны.
- SQL hosted RLS tests выполнены с обязательным ROLLBACK.
- Merge, ручной completion, primary binding, bootstrap и scheduled cycles
  фиксируются отдельными фактическими результатами выпуска; успешный браузерный
  тест сам по себе не включает доставку.

Quick stop: `CANVAS_WORKER_ENABLED=false`. Не переключать `FLYMIND_ENABLED=false`
при работающем master gate: это может вернуть legacy path. Независимый neural stop:
`FLYMIND_NEURAL_ENABLED=false`; primary notification outbox продолжает работать.

## Проверки этого изменения

- Python:204passed,172warnings,83.53s, включая scientific regression.
- Ruff critical checks:E9/F63/F7/F82 passed; secret working-tree/history scan0findings.
- Deno17passed; Vitest36passed; TypeScript/Vite build passed.
- Playwright4local+7HTTP-mockprivate passed; отдельно hosted headless без mocks passed.
- Отдельный PostgreSQL17:8migration/RPC/RLS/manual/schema-contract checks passed.
- Real test-account Canvas scan:2026-10-18T14:28:23Z,errors0/events0,
  send.done16/simulate.done15/edit.done15 без роста; новый grade snapshot сохранён.
- Исправленный isolated webhook реально deployed; /start,/menu,/deadlines,/stats,
  /status,/brain и3deadlinefilters+pagination проверены реальными send/edit только
  test-group. Дубли update подавлены,4неверныхsecret/chat/user проверки403.
  `/check` до merge честно закрыт. [Evidence](release-webhook-test.json).
- Все исходные336canvas/32grades/14health hashes точно совпали; RLS enabled,
  private bucket4MiB; hosted SQL owner isolation completed/ROLLED BACK.
- Known configured secret-value scan247candidate/build paths:0matches.
- Нефатальный warning:Three.js882.89kBminified/238.57kBgzip.

Финальный review также воспроизвёл прежнее P2-замечание PR: первый student enrollment
с null скрывал последующий реальный score. Два новых теста сначала упали (93 и0),
затем исправление общего current_course_score сохранило первый non-null student
score в assignment notifications, grade snapshots и GPA reports. Сеть и параметры
нейронной модели не затронуты. CI после этого изменения обязателен перед merge.
