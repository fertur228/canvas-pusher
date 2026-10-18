# FlyMind: проверка удалённого Supabase — 17 октября 2026

**Исторический preflight до deployment.** Текущее применение миграций и hosted
проверки описаны в [HOSTED_RELEASE_VERIFICATION.md](HOSTED_RELEASE_VERIFICATION.md).

Это журнал фактических проверок, а не подтверждение production-активации.
Исходный commit: `38202b77d7942f622d713cbef59c026b21592e1d`, ветка
`feat/flymind-neural-poc`, репозиторий `fertur228/canvas-pusher`.
PR [#1](https://github.com/fertur228/canvas-pusher/pull/1) открыт; проверки
`offline` и `database` для этого commit завершились SUCCESS.

## Подтверждённая цель

- MCP URL и локальный CLI link: `https://irjasmzytjeohwfpdnrl.supabase.co`.
- Management API: проект `Canvas-pusher`, `ap-northeast-2`, `ACTIVE_HEALTHY`.
- Удалённый PostgreSQL: 17.6. История прикладных миграций пуста.
- Network Media не является целью. Его код, база и контейнеры не изменялись.

Точные COUNT, а не оценки статистики: `canvas_state` — 336,
`course_grades` — 32, `health_checks` — 14. В каждой таблице встречаются
**четыре различных user_id**. Нельзя автоматически приписывать все строки
новому владельцу FlyMind. Auth users/sessions и Storage buckets/objects: 0.

Проверены колонки, ограничения, индексы, триггеры, функции, политики и grants.
В public нет views/FK. Существующий BEFORE UPDATE trigger canvas_state вызывает
`update_updated_at_column()` (security invoker). UUID default зависит от
`extensions.uuid_generate_v4()` / uuid-ossp. Восстановление должно сохранять
эти зависимости, а не только JSON строк.

## Обнаруженные риски

1. **Во всех трёх старых public-таблицах RLS выключен**, политик нет;
   anon/authenticated имеют SELECT/INSERT/UPDATE/DELETE и другие широкие права.
   Это подтверждённая конфигурация риска раскрытия/изменения учебных данных,
   но не доказательство, что кто-либо уже воспользовался доступом.
   Миграция 0002 закрывает anon-доступ, включает RLS, оставляет service_role
   и разрешает authenticated SELECT только через явно заданный owner mapping.
2. Существующая Edge Function `telegram-webhook` ACTIVE, версия 10,
   `verify_jwt=false`. В полученном размещённом исходнике нет проверки
   TELEGRAM_WEBHOOK_SECRET/секретного заголовка и TELEGRAM_USER_ID.
   Она использует service-role key и читает course_grades. Это старая функция,
   а не проверенная новая owner-only реализация FlyMind. Здесь она не менялась.
3. В проекте ещё нет Auth-владельца или FlyMind account. Необходимо отдельно
   создать owner mapping; миграции сами этого не делают.

## Миграции

Повторно выполнено `npx supabase db push --linked --dry-run --skip-vault`:
ровно семь pending, seeds/roles пусты, удалённого применения не было.

| Миграция | Действие при согласованном применении |
| --- | --- |
| 202610140000_legacy_baseline.sql | CREATE IF NOT EXISTS старых таблиц/индекса; существующие строки сохраняются |
| 202610140001_flymind_integration.sql | Новые FlyMind таблицы, outbox/RPC/RLS, private bucket и Storage policies |
| 202610140002_flymind_legacy_privacy.sql | Закрытие широких старых grants и owner-only RLS |
| 202610140003_flymind_operations.sql | Health, attempts, webhook deduplication, service-only RPC |
| 202610140004_flymind_retention.sql | Функции opt-in retention/recovery; cleanup не вызывается миграцией |
| 202610140005_flymind_storage_limits.sql | Private gzip bucket, лимит 4 MiB |
| 202610140006_telegram_assistant.sql | Bot-scoped update IDs, verified snapshots, deadline views, manual requests |

0006 заменяет PK новой таблицы webhook_updates на `(bot_id, update_id)` и
отзывает старый unscoped webhook RPC; это не удаление старых Canvas-записей.
Новые worker RPC закрыты для браузера; SECURITY DEFINER задают search_path.
Ни одно применение этих миграций не запускает Canvas worker или Telegram send.

## Реальные внешние проверки

- Новый локальный Canvas-токен: read-only preflight **verified**, 14 запросов
  HTTP200, 6 курсов, 20 assignments, 91 file, 2 announcements, failed scopes 0.
  Проверка схем submission/timezone выполнена. Pagination hops 0: реальную
  многостраничную выдачу этот запуск не проверил. Canvas mutations 0.
- Telegram getMe/getWebhookInfo выполнены: bot ID совпадает с owner/test identity,
  владелец совпадает, test chat отдельный, webhook нового бота отсутствует.
  Сообщения, setWebhook и setMyCommands не выполнялись.
- GitHub Canvas State Tracker остаётся `disabled_inactivity`. Его не включали.
  Полный manual completion требует workflow_run на default branch; PR не merged.
- Authenticated Observatory остаётся подготовленной интеграцией: Auth owner,
  FlyMind schema/telemetry и размещённый private frontend ещё не подтверждены.
  Нового Cloudflare deployment в этой проверке нет.

## Проверенная резервная копия

Завершена полная выгрузка PostgreSQL17 в custom archive и отдельная выгрузка
ролей без паролей. Архив получен из read-only экспортированного snapshot;
контрольные суммы строк сняты в последующем read-only snapshot и совпали
с восстановлением. Это не обещание резервирования будущих изменений.

Локальное расположение (игнорируется Git, каталог 0700, файлы 0600):
`secret-flymind-backups/20261017T141004Z-verified/`.
Ключ Fernet: отдельный файл `secret-flymind-backup-key` (0600); его содержимое
не выводилось. Архив БД до шифрования — 377536 bytes; роли — 5773 bytes.
SHA-256, время и результаты: [машиночитаемый отчёт](supabase-remote-preflight.json).

**Полный архив восстановлен без ошибок** в чистый Supabase PostgreSQL17.11.0.004
в отдельном локальном контейнере без сети, портов и общих томов. Для точного
восстановления role grants bootstrap-role должен называться `supabase_admin`;
обычный initdb с bootstrap `postgres` несовместим с hosted NOSUPERUSER postgres.
При восстановлении пропускается только CREATE ROLE уже существующего bootstrap-role.

Проверено:

- SHA-256 всех строк каждой из трёх старых таблиц совпал после восстановления.
- Все семь неизменённых миграций применились к восстановленной реальной схеме.
- SHA-256 старых строк остался неизменным после всех миграций.
- RLS включён, anon grants отозваны, service-role доступ сохранён;
  браузер не может вызвать worker claim RPC.
- Для каждого из четырёх разных user_id локальный временный Auth owner видел
  ровно свои строки всех трёх таблиц, один account и свой Storage object.
  Другие владельцы изолированы; unmapped authenticated и anon доступа не получили.
- Тестовые owner/account/Storage записи создавались локально в транзакции,
  завершённой ROLLBACK. Размещённые Auth пользователи не создавались.

В приватном каталоге сохранены `restore_verify.py` и `owner_checks.py` для
повторной проверки на **новом пустом локальном** контейнере
`flymind-restore-20261017`, network=none, bootstrap-user=supabase_admin,
unix socket `/tmp`, с указанным Supabase image. Скрипты используют `docker exec`
и не принимают удалённый URL. Запускать сначала restore_verify, затем owner_checks
из Python environment с cryptography. Успешный проверочный контейнер уже удалён;
временные незашифрованные дампы и краткоживущие CLI credentials также удалены.

Это **локальный** backup, не off-site копия. Архив/ключ нужно сохранить раздельно
в доверенном хранилище перед долгосрочной эксплуатацией. SQL backup не включает
пароли platform roles, настройки/Auth-провайдеров, Edge secrets и содержимое
Storage blobs; в проверенном проекте blobs, Auth users и sessions отсутствовали.
Не публиковать приватный каталог или ключ, не восстанавливать старые открытые grants
в production без отдельного security review.

После локальной проверки MCP повторно подтвердил: remote migrations=[], FlyMind
tables=0, Auth users=0, buckets=0; старые количества 336/32/14 сохранены.

## Локальная регрессия

- Python `pytest tests/flymind -q`: 83 passed.
- Deno webhook tests: 13 passed; HTTP mock, не реальная Telegram-доставка.
- Vitest: 28 passed.
- TypeScript + Vite production build: success. Предупреждение о Three.js chunk
  882.89 kB (238.57 kB gzip) — размер загрузки, не ошибка сборки.

## Граница активации

Удалённые миграции, замена webhook, создание Auth/account и отправка сообщений
не выполнены. Backup и локальная репетиция завершены; перед изменением существующей
базы остаётся явное согласование точного набора миграций/целевого проекта.
Нельзя считать текущий production-проект изолированным staging только из-за
того, что scheduler выключен. Для полного hosted staging нужен отдельный проект.

После согласованных DB/Auth шагов: silent bootstrap с DELIVERY_MODE=disabled,
отдельный test chat, безопасный webhook, owner/foreign/anon проверки, реальный
send/edit/repeat, private telemetry replay. Слияние PR и production-доставка
остаются отдельными действиями, требующими одобрения владельца.
