# FlyMind — фактическая hosted-проверка, 17 октября 2026

Статус: **STAGING / TEST CHAT VERIFIED**, но это тестовые аккаунт/группа в
существующем проекте, **не отдельный staging Supabase**. Production выключен.
Этот отчёт заменяет устаревшие activation blockers в документах от 14 октября.
Исторический [preflight](SUPABASE_REMOTE_PREFLIGHT.md) описывает состояние ДО
разрешённого пользователем deployment; его исходные контрольные суммы сохранены.

## База и сохранность

Цель независимо подтверждена CLI/MCP: **Canvas-pusher**, ref
`irjasmzytjeohwfpdnrl`, регион `ap-northeast-2`.
После нового dry-run штатным `db push --linked --skip-vault --yes` применены
ровно семь миграций `202610140000`–`202610140006`. Их байты/SHA-256 совпали с
[предварительно восстановленной копией](supabase-remote-preflight.json).
`db reset`, удаление/импорт production-данных не использовались.

| Legacy-таблица | До | Сразу после миграций | После тестового bootstrap |
| --- | ---: | ---: | ---: |
| canvas_state | 336 | 336 | 336 |
| course_grades | 32 | 32 | 38 |
| health_checks | 14 | 14 | 14 |

Дополнительные 6 grades принадлежат отдельному test-chat account. Все исходные
336/32/14 строк повторно сверены по SHA-256 после тестов: **точное совпадение**.
Четыре старых user_id не объединялись и не приписывались новому владельцу.

RLS включён на всех public-таблицах. Anon legacy SELECT закрыт, service-role
CRUD сохранён, worker RPC недоступны authenticated. На реальной hosted БД выполнен
[scripts/verify_hosted_rls.sql](../scripts/verify_hosted_rls.sql): положительная
изоляция четырёх временных владельцев, запрет чужих/unmapped записей, чтение двух
Storage objects только их временным владельцем, anonymous deny. Все тестовые
Auth/account изменения завершены ROLLBACK. Это **SQL role tests**, не вход
человека через Supabase Auth.

Bucket `flymind-private`: public=false, только application/gzip, максимум4MiB.
Фактически 2 compressed objects, суммарно293657bytes. БД около12.82MB (включая
платформенные схемы; размер меняется). Телеметрия скачана и проверена по SHA-256.

## Backup

`secret-flymind-backups/20261017T141004Z-verified/` и отдельный
`secret-flymind-backup-key` сохранены, Git-ignored, права0700/0600.
Fernet decrypt/hash проверен снова. Предыдущая полноценная локальная PostgreSQL17
реставрация с точными row hashes и репетицией семи миграций остаётся основанием
recoverability. Перед deployment дополнительно зашифрован архив настроек Auth/
Supabase и исходника старого webhook (`hosted-before-release.tar.gz.fernet`).
Это не экспорт secret values, паролей platform roles или новых Storage blobs.
Backup предшествует новым тестовым записям; нельзя автоматически восстановить
его поверх текущей БД и потерять более поздние записи.

## Canvas и Telegram

Новый токен реально работает: HTTP200×14, 6 курсов, 20 assignments, 91 file,
2 announcements, failed scopes0. Pagination hops0 — многостраничная выдача
проверена тестами, но в этом реальном наборе не встретилась.

Silent bootstrap:113 snapshots,20 verified assignments, events0, errors0,
Telegram sends0. Реальный deadline RPC: upcoming4,overdue3,today0,week2,month2,
all10,undated3 на момент проверки. Снимки показывают время последнего успешного
сканирования и становятся stale через30минут. Grade не означает submission.

Новый bot `@canvasheimdall_bot`, отдельная подтверждённая test-группа.
Развёрнут **flymind-telegram-webhook** в том же Supabase. Использует namespaced
`FLYMIND_TELEGRAM_*` secrets, точный bot/user/chat и секретный Telegram header.
Gateway JWT выключен потому, что Telegram его не отправляет; приложение проверяет
собственную авторизацию. Старые общие bot credentials не перезаписывались.
Официальные семь Bot API commands зарегистрированы для test chat.

Реальные контролируемые HTTP updates → hosted webhook → Telegram Bot API:
/start,/menu,/deadlines,/stats,/status,/brain — done, повтор подавлен;
7 deadline callback views — реальные успешные editMessageText.
/check корректно сообщил, что dispatch отключён; никакого ложного «готово».
4 negative checks (missing/wrong secret, actor/chat mismatch) вернули403.
Это API-проверка, **не подтверждение ручного нажатия каждой кнопки в клиенте**.
[Обезличенные результаты](hosted-webhook-test.json).

Старый небезопасный `telegram-webhook` v10 после резервирования исходника заменён
проверенным handler с обязательными secret/user settings. Старые настройки их не
содержат, поэтому endpoint теперь fail-closed: реальный POST возвращает503.
Возможность получать grades через незащищённый старый endpoint закрыта.

Меню русифицировано. Нулевая оценка теперь отображается как0%, а не «без оценки».
Физкультуре не присваивается автоматически4.0. GPA явно оценочный: веса5/2 кредита
— соглашение старой реализации, не официальный университетский транскрипт.

## Нейронный контур

Оригинальные1500 FlyWire FAFB v783 IDs,25206 edge rows/276399 synaptic contacts
и параметры модели сохранены. Два явно синтетических Canvas события использованы
для реальной Supabase/Telegram/Brian2/Storage цепочки; реальные задания не менялись.

| Профиль | GF spikes | Активные клетки | Все spikes | CPU | Wall с импортом/export | Peak RSS |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| weak | 2/2 | 282 | 344 | 2.207s | 14.754s | 217.61MiB |
| strong | 3/4 | 418 | 834 | 1.961s | 13.048s | 218.67MiB |

Это текущие macOS measurements, не Linux runner timings. Реально доставлены
2 первичных сообщения и2 enrichment edits, message IDs сохранены. Все6 jobs done.
Повтор ingest:0 новых событий,0 повторных доставок; hashes2objects совпали.
[Измерения](hosted-neural-test.json). Уровни moderate/elevated задаются инженерными
thresholds; biological_response_validated=false. Fly не «понимает» дедлайны.

## Observatory и Auth

**Реально развернут** private Supabase-mode preview:
https://flymind-preview.flymind-observatory.pages.dev

Immutable deployment: https://0928fa3a.flymind-observatory.pages.dev

HTTPS200, CSP/X-Frame-Options/nosniff проверены. В реальном Chrome виден экран
owner sign-in. В17файлах3,821,886bytes статической сборки не обнаружены известные
секреты из private config. Service key отсутствует; только URL/anon public key.
Cloudflare OAuth успешно обновлён. Новый Supabase проект не создавался.

Auth signup закрыт, site_url и redirects заданы для preview/production Pages.
**Owner email ещё не предоставлен**, auth.users пока0; owner_id test account NULL.
Не придуманы email/пароль и не присвоен случайный Auth UUID. Поэтому фактический
owner sign-in и полный приватный browser replay ещё НЕ пройдены. Backend Storage
и neural data реальны; эти успехи не заменяют missing owner-login gate.

## GitHub и автономность

Secrets обновлены приватно: CANVAS_API_URL,CANVAS_API_KEY,SUPABASE_URL,
SUPABASE_SERVICE_KEY,TELEGRAM_BOT_TOKEN,TELEGRAM_CHAT_ID,TELEGRAM_USER_ID,
TEST_TELEGRAM_CHAT_ID,TELEGRAM_WEBHOOK_SECRET. Значения не опубликованы.

Production gates: CANVAS_WORKER_ENABLED=false,FLYMIND_ENABLED=false,
FLYMIND_MODE=shadow,DELIVERY_MODE=disabled,FLYMIND_PRODUCTION_AUTHORIZED=false.
Основной scanner остаётся disabled_inactivity. На старой main нет нового master
safety gate: включать его до reviewed merge нельзя.

Реальный облачный read-only Canvas run **SUCCESS**:
https://github.com/fertur228/canvas-pusher/actions/runs/39043798824
26s job, фактические Canvas14×200/6курсов/20заданий. Он не зависит от localhost.

Добавлен отдельный конечный `FlyMind controlled hosted test chat` workflow:
без cron, только явный opt-in, фиксированный test/shadow режим, отдельный
FLYMIND_TEST_ACCOUNT_ID, запрет production chat/authorization. Это подготовка
облачного повторного full-worker теста без включения legacy scheduler.

`/check` требует completion workflow на main. PR1 не merged; истинный
workflow_dispatch → workflow_run completion остаётся закрытым rollout gate.
Регулярная autonomous production работа **пока не включена**.

## Предупреждения и ограничения

- Three.js chunk882.89kB/238.57kB gzip: warning размера, не ошибка сборки.
- Supabase `RLS enabled, no policy` у3 worker-only таблиц — намеренный запрет
  браузерного доступа; доступ остаётся у service_role.
- `flymind_storage_owner` callable anon/authenticated — намеренный boolean helper
  для restrictive Storage policies; anon всегдаfalse, authenticated проверяет
  auth.uid(). Он не выдаёт rows и не изменяет данные. SECURITY DEFINER search_path
  задан. Его нельзя произвольно отозвать, сломав ограничения чужих buckets.
- Legacy `update_updated_at_column()` имеет mutable search_path, но SECURITY
  INVOKER и только NEW.updated_at=NOW(). Он не повышает привилегии. Семь проверенных
  миграций не переписывались ради скрытия advisory warning.
- Реальные429/timeouts не провоцировались нагрузкой; failure recovery проверен
  автоматическими fault-injection тестами, а не выдан за сбой живой платформы.
- Primary Telegram chat не использовался для произвольных тестовых сообщений.

## Дальнейший обязательный человеческий шаг

Указать свой email для private Observatory. Пароль/токены не отправлять в чат.
Затем владелец задаёт пароль самостоятельно в защищённой процедуре Supabase Auth
(Create user для явно указанного owner); агент связывает точный Auth UUID с
подтверждённой Telegram identity и проверяет actual login/private replay.
Без этого production не активируется. Новые Canvas/Telegram токены не нужны.
