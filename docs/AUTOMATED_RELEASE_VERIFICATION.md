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
