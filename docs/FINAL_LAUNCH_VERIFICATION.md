# FlyMind: финальная проверка release UX — 18 октября 2026

Текущая цель — существующий Canvas-pusher, `irjasmzytjeohwfpdnrl`,
ветка `feat/flymind-neural-poc`, PR1. Network Media не затронут.
Production-флаги остаются выключены. Этот отчёт дополняет исторические
HOSTED_RELEASE_VERIFICATION и DEADLINE_NOTIFICATION_VERIFICATION.

## Реализовано и размещено

- `/start` и `/menu`: три inline-кнопки, два ряда: Дедлайны / Успеваемость;
  Обновить сейчас. Постоянная reply keyboard удаляется.
- Три видимых фильтра: Ближайшие / Просроченные / Все. Все семь старых RPC views
  сохранены внутри API. Навигация и первая страница оценок редактируют сообщение.
- Повторное нажатие с идентичным текстом считается безопасным no-op.
- Новое задание, напоминание, оценка и изменение срока имеют короткие русские
  emoji-шаблоны. Ноль не заменяется отсутствующим значением. В обычных сообщениях
  нет GF/neuron/job/event IDs и научных пояснений; они остаются в /brain/Observatory.
- Пороги24/12/6/3/1, silent bootstrap, outbox, модель и topology не изменены.

`flymind-telegram-webhook` v6 реально deployed в тот же Supabase с прежней
привязкой только к test-группе. Legacy function v13 не перезаписывалась.

Реальный Telegram API выявил дефект первой попытки: сообщение, отправленное с
ReplyKeyboardRemove, нельзя затем editMessageText. Исправлено: отдельное короткое
removal-сообщение, inline-меню, удаление только этого временного сообщения.
Неоднозначный старый claim сохранён для диагностики, без слепого resend.
Ограничение соответствует [официальному Bot API](https://core.telegram.org/bots/api#updating-messages).

## Реальные проверки

- Owner Auth существует; UUID/email совпали с приватным `.env.flymind.owner`;
  UUID привязан к ранее подтверждённому test account. Bot/user/chat/origin совпали.
  Пароль не читался, не создавался и не менялся.
- Все8 миграций на месте. Повторного db push не было.
- Исходные canvas_state336, course_grades32, health_checks14 совпали по полным
  SHA256. Дополнительные6test-grades сохранены отдельно. Четыре legacy user IDs
  не переназначались.
- Hosted SQL positive owner / foreign user / anon / private Storage / worker RPC
  тесты прошли; временные fixtures завершены ROLLBACK. Проверка использует
  существующий owner_id, не переназначает его ради теста.
- Анонимный REST SELECT academic tables:401. Public guessed Storage URL:400.
  Bucket public=false. Старый небезопасный endpoint fail-closed503.
- Backup: authenticated Fernet decrypt, encrypted/plaintext hashes, PGDMP header
  совпали; зафиксированная прежняя полная PostgreSQL17 реставрация сохранена.
  Первые7 миграций не изменены;0007 присутствует отдельно. Backup предшествует
  новому Auth и тестовым artifacts, не заменяет актуальный полный platform backup.
- Canvas preflight:14GET/HTTP200,6courses,20assignments,91files,2announcements,
  failed scopes0,mutations0. Cost54.28,minremaining551.48; реального429 не было.
- Webhook:7команд,3фильтра,пагинация,повторные updates, повторный identical edit,
 4negative secret/chat/user checks. Все реальные API send/edit выполнены только
  в подтверждённой test-группе. `/check` честно сообщил, что запуск закрыт.
  [Sanitized evidence](release-webhook-test.json).
- В native Telegram вручную через UI отправлен `/start@canvasheimdall_bot` в
  подтверждённой группе. Получен новый three-button menu, постоянная клавиатура
  отсутствует. Реальные client clicks на фильтры не засчитываются: native click
  automation не предоставила надёжного подтверждения; API edits проверены.
- Preview HTTPS200, CSP/nosniff/frame/referrer headers присутствуют:
  https://flymind-preview.flymind-observatory.pages.dev/
  В браузере пока виден owner sign-in. **Приватный owner browser replay не пройден**.
  Реальный аккаунт и SQL RLS не заменяют этот gate. Владелец приглашён войти сам.

## Регресс

- Python:201passed,172dependency warnings,80.57s; neuroscience regression включён.
- Deno:17passed. Vitest:28passed. TypeScript и Vite production build passed.
- Playwright:4local+2private HTTP-mock passed; mocks явно не hostedAuth gate.
- Изолированный local PostgreSQL17:8миграций,transaction/RPC/RLS/Storage/manual lifecycle passed.
- Secret/history signature scan:0findings; exact configured secret-value scan237
  repository/build files:0matches. Private env/backup/key Git-ignored.
- Vite warning Three.js chunk882.89kB/238.57kB gzip остаётся; build не падает.
- Локальный Python3.11 в /tmp был повреждён. Восстановлен CPython3.11.17 в
  игнорируемую `.venv/runtimes`, pinned lock dependencies, `.venv/neural` исправлен.
  Biology/model dependencies не обновлялись произвольно.

## Не пройденные release gates

1. Владелец должен войти в открытую Chrome Observatory-вкладку. Пароль не отправлять
   агенту. Далее можно проверить private download, визуализацию и replay в реальном UI.
2. До этого PR1 не merge и primary chat не включается. `/check` real
   workflow_dispatch → default-branch workflow_run finalizer ещё не проверен.
3. Отдельная production binding/silent bootstrap, production smoke и две
   **scheduled** cloud cycles не выполнены. Конечный test workflow их не заменяет.

Quick stop остаётся `CANVAS_WORKER_ENABLED=false`. Независимое выключение neural:
`FLYMIND_NEURAL_ENABLED=false`, сохраняя `FLYMIND_ENABLED=true` и outbox.
`DELIVERY_MODE=disabled` останавливает FlyMind delivery. Не удалять histories/jobs,
не восстанавливать старый insecure webhook. Полная процедура: [ROLLBACK.md](ROLLBACK.md).

## Облачное выполнение текущего кода

[Run39065422453](https://github.com/fertur228/canvas-pusher/actions/runs/39065422453)
SUCCESS на268edd1. Два последовательных настоящих скана в Linux: оба verified,
errors0/events0, send.done не вырос, повторных сообщений0. Worker portion112.11s.
Последняя синхронизация2026-10-17T20:10:19.361366Z =18октября01:10:19Asia/Almaty.
[Sanitized cloud evidence](release-cloud-verification.json).

Повтор deadline validation занял0.52s: прочитан уже завершённый checkpoint,
11старых test-messageIDs/12events сохранены. Это **не11новых доставок и не новые
нейронные запуски**. Cloud run был конечным workflow_dispatch, не cron. Временный
FLYMIND_TEST_CHAT_VALIDATION сноваfalse. Все production master flags выключены.

Storage5objects/749721bytes,15experiment associations (включая suppressed),
DB13,405,331bytes на момент проверки. При unchanged scans нет новых artifacts.
При5min cron:8640runs/месяц, ориентир60–120s/job ⇒8640–17280runner-min/month.
Для PUBLIC repo стандартные Ubuntu runners бесплатны; приватный план потребует
пересчёта. Бюджет20events/day ×~150KB≈90MB/month до reuse/retention. Сейчас
production cron не включён; это оценка, не фактическое месячное потребление.
[Free-tier assumptions](COST_ESTIMATE.md). Платные сервисы не активировались.

Main остаётсяf1d0b496e363cc11142fba457f0521f5264cc6f0. PR1 открыт; regular scanner
в disabled_inactivity. Включать old main нельзя: в ней нет нового master gate.
Последние два успешных hosted workflow:
39049711232 (предыдущая deadline release) и39065422453 (текущая UX release).
Они не являются двумя scheduled production executions.


CI текущего кода268edd1: [39065375940](https://github.com/fertur228/canvas-pusher/actions/runs/39065375940)
SUCCESS, оба jobs offline/database. Включены Linux neural ablations, multi-event
real simulation с captured Telegram, PostgreSQL16, Deno, frontend/browser и build.
Hosted cloud tests отделены от captured/mock Telegram в CI.


## Account-scoped Observatory correction

Перед отдельной production binding выявлен дефект: прежний health SELECT LIMIT1
мог возвращать test-health вместо production-health того же владельца. Исправлен
явный выбор аккаунта из RLS-scoped flymind_accounts; health/errors/history/trigger
запрашиваются для выбранного account_id. По умолчанию предпочтён enabled private
chat. При переключении очищается старый replay/cache; другой ответ не принимается.
Это не изменение схемы/RLS и не создание production account.

Добавлен браузерный regression: два synthetic accounts с разным состоянием;
production degraded не скрывается healthy test account; смена account убирает
старый replay и trigger. Локально3private HTTP-mock+4local browser tests passed,
Vitest28, TypeScript/build passed. Этот regression не заменяет hosted owner login.

Linux CI268edd1:195Python passed,6optional upstream-cache skips,172warnings,60.49s.
Локально эти6тестов также выполнены (201passed). Ruff critical checks passed.
Бот и numeric primary recipient повторно сверены read-only getMe/getChat;
primary messages0. Официальные7commands подтверждены getMyCommands в test scope.
