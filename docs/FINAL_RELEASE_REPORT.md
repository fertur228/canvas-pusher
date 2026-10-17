# FlyMind — итоговый технический отчёт, 14 октября 2026

## Текущее hosted-состояние — 2026-10-17

Семь миграций реально применены, legacy hashes сохранены; новый защищённый webhook
и Cloudflare Supabase-mode preview размещены. Реальные test-chat send/edit и
FlyWire/Storage проверки прошли. Production и основной scheduler выключены;
owner Auth/sign-in и manual completion на main ещё не проверены.
Актуальные доказательства: [HOSTED_RELEASE_VERIFICATION.md](HOSTED_RELEASE_VERIFICATION.md).
Нижележащие отчёты от предыдущих сессий являются историей, а не текущими blockers.

## Итог

**LOCALLY COMPLETE, EXTERNAL ACCESS REQUIRED.** Реализован и проверен локальный
продукт с автономными workflow, защищённым хранением и научным интерфейсом.
Production не активирован, облачный dashboard не развёрнут. Ветка
`feat/flymind-neural-poc`; main не изменён. Исходные научные данные сохранены.

Проверки выполнены на macOS ARM64, Docker Linux ARM64 и настоящем Ubuntu x86_64
GitHub runner. Успешный полный CI:
https://github.com/fertur228/canvas-pusher/actions/runs/38545771927.
Настоящий Canvas GET завершился HTTP401:
https://github.com/fertur228/canvas-pusher/actions/runs/38536417510.
Это проверка реального сервиса с отрицательным результатом, а не успешная интеграция.

## Реализованный поток

1. Canvas GET получает активные курсы, задания/оценки/статусы сдачи, файлы и объявления.
   Link-пагинация проверяет origin, API-префикс, циклы и предел страниц. Ограничены
   параллелизм, повторные запросы и Retry-After. Ошибка API не превращается в пустой курс.
2. Нормализованный снимок, события и outbox сохраняются транзакционным PostgreSQL RPC
   с compare-and-swap. Первый запуск требует явного тихого bootstrap. Напоминания
   используют сохранённые пороги, переживают опоздание scheduler и не требуют часового окна.
3. Worker сначала отправляет обычное уведомление и сохраняет Telegram message_id.
   Блокировки/leases и стабильные event IDs защищают от конкурентных дублей.
   Неопределённый результат sendMessage становится ambiguous и требует сверки оператором.
4. Затем фиксированный encoder выбирает исходный weak/strong профиль LC4/LPLC2.
   Изолированный дочерний процесс использует настоящую FlyWire-топологию и прежнюю LIF-модель.
   Ошибка нейросимуляции не отменяет первичную доставку.
5. Результат сжимается, хешируется и сохраняется в private Storage; PostgreSQL хранит
   небольшие метаданные и связь с событием. Одинаковые профили внутри worker используют
   один расчёт/артефакт с явно сохранённым исходным временем записи.
6. В режиме enrich readout добавляет экспериментальную срочность редактированием уже
   доставленного сообщения. Shadow сохраняет результат без редактирования.
7. Observatory после Supabase Auth показывает историю, trigger, состояние очередей,
   реальные модельные записи и replay. Локальный научный режим остаётся независимым.

## Компоненты и файлы

- `src/core/scanner.py`, `diff_engine.py`, `src/main.py`: общий надёжный scanner,
  безопасные журналы, статусы ошибок и совместимость исходного Canvas Pusher.
- `src/flymind/`: events, sensory, neural/child, pipeline, store, worker, reports,
  telegram, watchdog, maintenance, live_check, telegram_check, demo, evaluate.
- `supabase/migrations/202610140000..0005_*`: совместимые legacy-таблицы, event/outbox,
  owner RLS, heartbeat, audit попыток, webhook replay, retention и ограничения Storage.
  `supabase/optional/` содержит независимый Cron-watchdog; автоматически не применялся.
- `supabase/functions/telegram-webhook/`: проверка секрета/пользователя/чата,
  дедупликация update_id, экранирование HTML, сохранённые команды и `/brain`.
- `dashboard/src/`: Auth, private data source/history/health и сохранённый научный viewer.
  `dashboard/public/_headers`, `_redirects`, `wrangler.toml`: статический Cloudflare target.
- `.github/workflows/`: scanner, полная проверка, отдельное безопасное Canvas-чтение,
  health-watchdog и отключённый по умолчанию weekly retention.
- `tests/flymind/`, `tests/neural/`, scanner tests, dashboard unit/browser tests:
  отказоустойчивость, изоляция, reproducibility и реальные локальные SQL/API проверки.
- `scripts/check_repository.py`, `check_platform_reproducibility.py`,
  `Dockerfile.neural`, lockfiles: проверка публикации и воспроизводимые среды.
- Документы README, ARCHITECTURE, NEURAL_MODEL, DEPLOYMENT, SECURITY_REVIEW,
  OPERATIONS, ROLLBACK, COST_ESTIMATE, DELIVERY_PROGRESS и этот отчёт.
  JSON-отчёты измерений находятся рядом; первоначальные эксперименты не переписаны.

## Биология и измеренные результаты

Реальные данные: взрослый Drosophila melanogaster, FlyWire FAFB v783, 1500 root IDs,
25206 строк рёбер, 17186 направленных пар, 276399 синаптических контактов.
GF: `720575940622838154` и `720575940632499757`. Настоящие soma-координаты доступны
для 1497 клеток; альтернативная раскладка явно обозначена как неанатомическая.
Линии обозначают связность, а не реконструированную морфологию нейритов.

| Условие | GF слева/справа | Все спайки | Активные клетки | Readout |
| --- | --- | --- | --- | --- |
| Baseline | 0 / 0 | 0 | 0 | minimal |
| Weak, реальная сеть | 2 / 2 | 344 | 282 | moderate |
| Strong, реальная сеть | 3 / 4 | 834 | 418 | elevated |
| Weak, передача отключена | 0 / 0 | 420 | 210 | moderate |
| Strong, передача отключена | 0 / 0 | 838 | 314 | moderate |
| Strong, 3 shuffled-контроля | 2/3, 3/2, 2/3 | 827–828 | 416 | moderate |

Латентность GF от начала стимула: weak 751.1/750.0 мс; strong 179.8/179.6 мс.
Прямая стимуляция GF отсутствует. Нулевая передача обнуляет GF, но внешняя стимуляция
сенсорных клеток сохраняет популяционную активность. Shuffled-контроль сохраняет
направленные степени/суммы контактов и страты весов/neuropil/NT, меняет партнёров;
это явно синтетическая контрольная сеть, не биологические данные.

Проведено 17 прогонов с повторами, тремя seed перестановки и вариациями стимула.
Weak-fast: ноль спайков; strong-slow: GF 9/13 и 2032 спайка, 296 активных клеток.
Фиксированный readout учитывает также число активных клеток, поэтому более высокий
GF сам по себе не гарантирует elevated. Никакой подгонки весов под классификацию нет.

На 22 синтетических Canvas-сценариях: 2 ложных elevated и 0 пропущенных критических
случаев относительно инженерного правила «несдано и осталось <=3 ч». Детерминированный
baseline совпадает с этим правилом по определению; это не независимая человеческая
разметка. **Преимущество нейросети в приоритизации не доказано.** Топология действительно
влияет на вычисление, но академический смысл задают encoder и readout. Поэтому
обязательная срочность остаётся детерминированной, neural — экспериментальное дополнение.

Сигналы в UI — записи симуляции, а не измеренные потенциалы живой мухи. Универсальная
LIF-физиология, NT/receptor assumptions, gain/recruitment и частичная GF-афферентация
80.49%/82.82% остаются ограничениями. LC4-only активирует GF: зависимость от LPLC2
не воспроизведена в сопоставленном биологическом протоколе. `biological_response_validated=false`.
Источник/лицензия CC BY-NC 4.0 и хеши сохранены; коммерческое использование требует
отдельной проверки прав.

Первый Ubuntu CI обнаружил различие float64 SHA между ARM и x86. Диагностика показала
точное совпадение спайков/дискретных данных, численные отклонения <=3.64e-12 и точные
хеши повторов на одной платформе. Исправлена ошибочная межплатформенная предпосылка
теста: все численные поля проверяются с абсолютным пределом 1e-10, спайки/параметры
точно, native-повторы — побитово. Исходные данные и биологические параметры не менялись.

## Проверки

- Полный локальный pytest: **137 passed**, 172 dependency warnings, 83.40 с.
- Полный Ubuntu CI: **131 Python passed, 6 skipped**, Deno, Vitest, TypeScript/Vite, 4 локальных и 2 приватных
  браузерных сценария, PostgreSQL 16 и реальные нейронные абляции проходят.
- 6 CI skips относятся к необязательному полному upstream scientific cache, который
  не публикуется в репозитории. Основной граф, модель и bundled exports проверяются.
- Deno: 3 теста; Vitest: 28; браузер: 4 local + 2 private. Private browser transport
  замокан, но воспроизводит настоящие gz-эксперименты. TypeScript/build без ошибок.
- Настоящий локальный PostgreSQL: все 6 миграций, CAS, outbox/leases, RLS, Storage
  policies, heartbeat, audit, replay и retention. Использовалась изолированная БД.
- Настоящие локальные Supabase Auth/PostgREST/Storage: owner разрешён, другой
  authenticated user и anonymous не получают приватные данные; browser не вызывает
  worker RPC; guessed/public URLs запрещены; авторизованный gzip проверен SHA.
  Общий артефакт сохраняется при истечении только одной ссылки.
- Локальный Supabase end-to-end: 3 события, реальные weak/strong расчёты, 3 captured
  sends/3 edits, 0 дублей. Реальных Telegram-сообщений в этом тесте нет.
- Ruff critical rules, repository/history known-secret scan, npm audit обоих проектов
  и pip-audit двух lockfiles проходят. Python type checker в проекте не настроен.

Не скрытые ограничения проверок: deprecated Brian2/pyparsing API warnings;
предупреждение о крупном лениво загружаемом 3D chunk (~883 KB minified /239 KB gzip);
advisory старых SHA-pinned action Node runtimes. Браузерная авторизация с настоящим
hosted Supabase и фактическая Telegram-доставка остаются внешними gates.
Исторические CI-логи недоступны: GitHub вернул HTTP410, их содержимое не аттестовано.

## Производительность и стоимость

Измерено на настоящем Linux x86_64 GitHub runner, а не перенесено с macOS:

- Strong: CPU симуляции 1.67–1.69 с; wall симуляции 1.66–1.68 с.
- Загрузка графа 0.152–0.154 с; импорт/подготовка около 0.70 с; полный процесс 3.05–3.06 с.
- Peak RSS процесса около 197 MiB; сжатый результат evaluation 121377 байт.
  Это размер evaluation JSON, не обещание такого же размера полного артефакта replay.
- 17 научных прогонов: 64.31 с wall в измеренном CI.
- Batch из 4 событий: 9.90 с wall, 9.96 с child CPU, peak child RSS 188.60 MiB.
  4 sends/4 edits captured, 0 повторных доставок; 2 уникальных gzip, 293646 байт всего.
- Лимиты: default 5 neural jobs, 25 deliveries на drain, 600 с budget worker,
  child timeout 30 с, Linux CPU 25 с/address space 1.5 GiB/output 8 MiB.

Цель $0/месяц достижима в приведённых объёмах, без гарантии uptime. При 15-минутном
опросе: 96 запусков/день; оценка при 30–60 с на job — 1440–2880 минут/месяц.
Стандартные public GitHub runners бесплатны; для private repo надо проверить план.
20 relevant events/день дают до ~98 MB telemetry/месяц по консервативной оценке,
30-day retention и per-worker reuse снижают накопление. DB: оценочно 2–6 MB/месяц
плюс исходные snapshots; event tombstones остаются для дедупликации.
Официальные лимиты и допущения: [COST_ESTIMATE.md](COST_ESTIMATE.md).
Ничего платного не подключалось; private academic erasure policy ещё требует решения.

## Что работает без ноутбука

После разрешённого merge/configuration worker работает короткими GitHub Actions jobs,
Supabase хранит состояние/артефакты, Edge Function обслуживает Telegram, Cloudflare
раздаёт статический интерфейс. Постоянный Python-сервер не нужен. Есть heartbeat,
отдельный hourly watchdog и выключенный по умолчанию weekly retention; независимый
Supabase Cron watchdog подготовлен. Scheduler может опаздывать и отключаться после
60 дней неактивности public repository; SLA отсутствует.

Сейчас автономный production **не включён**: исходный workflow имеет состояние
`disabled_inactivity`, feature-ветка сама не запускает default-branch cron.
Master `CANVAS_WORKER_ENABLED=false`, FlyMind off, delivery disabled, shadow —
безопасные значения по умолчанию. GitHub variables в аккаунте не изменялись.

## Точные внешние шаги

1. Обновить GitHub Secret CANVAS_API_KEY (401), проверить CANVAS_API_URL и повторить
   безопасный `FlyMind controlled Canvas read`; подтвердить реальную пагинацию/схему.
2. Выбрать явно отдельный free staging Supabase, предоставить URL/server key только
   серверной среде. Проверить legacy grants, применить 6 миграций без reset, создать
   owner Auth user, отключить public signup и связать flymind_accounts.owner_id.
3. Создать отдельный Telegram test chat; настроить TEST_TELEGRAM_CHAT_ID, отличный
   от TELEGRAM_CHAT_ID, и bot token. Выполнить telegram_check с постоянным state file:
   send + edit + повтор + сверка message_id. Основной чат не подставляется автоматически.
4. Провести тихий `python -m src.flymind.worker --bootstrap`, затем несколько staging
   shadow-прогонов полного пути с реальными Canvas/Supabase/Telegram и replay.
5. Восстановить Cloudflare OAuth интерактивным `npx wrangler login` либо дать scoped
   CLOUDFLARE_API_TOKEN и account ID. Создать именованный preview Pages project,
   собрать Supabase-mode с public key и проверить private UI/Auth/Storage на preview.
   Старая OAuth-сессия истекла, noninteractive refresh не удался; deployment не было.
6. Настроить секрет webhook, exact chat/actor, `/brain` Observatory URL и проверить
   команды в test chat. Не восстанавливать старый handler без проверки secret header.
7. После review/merge владельцем настроить account/delivery variables, включить
   CANVAS_WORKER_ENABLED и workflow, сначала shadow. Production/enrich разрешить
   только после пройденных gates и однозначного адресата. Main автоматически не merge.
8. Сначала dry-run retention, затем при согласованной политике включить
   FLYMIND_RETENTION_ENABLED. Установить независимый watchdog и уведомления об ошибках CI.

Точные команды/env и rollback находятся в DEPLOYMENT.md / OPERATIONS.md / ROLLBACK.md.
Выключение neural через FLYMIND_NEURAL_ENABLED=false сохраняет надёжный outbox.
Возврат FLYMIND_ENABLED=false включает более слабый legacy-путь и не является
рекомендуемым rollback нейронной части.

## Git и границы результата

Логические feature-коммиты: ee0d578 (исходная научная основа), 08a5dfd (backend/security),
c6a1ca0 (Observatory), 8a25df8 (CI/tooling), 984ab7f/73e0384 (диагностика native
воспроизводимости), 03e7939 (измерения/test-chat), a492921 (activation gates).
Operations commit: d02a15c; release documentation: ec6fd8a.
PR: https://github.com/fertur228/canvas-pusher/pull/1 — открыт для review, не merged.
Последующие коммиты только фиксируют handoff evidence; точный HEAD доступен в PR.
Feature-ветка отправлена; force-push, merge main, production migration/deployment и
сообщения в основной Telegram-чат не выполнялись. Внешние gates нельзя заменить
успешными mock-тестами. Этот результат не является заявлением production readiness.

Изолированные локальные тестовые Supabase/PostgreSQL остановлены после проверок,
данные сохранены; чужие локальные проекты не останавливались. Финальный scan всех
доступных Git commits и статического bundle не нашёл известных сигнатур секретов.

## Дополнение: Telegram assistant, 14 октября 2026

Реализованы постоянное меню, семь команд, проверенные кэшированные дедлайны с
фильтрами и пагинацией, отслеживаемая ручная синхронизация с результатом после
фактического завершения GitHub workflow, поддержка замены бота без потери истории
и безопасный локальный ввод/публикация новых credentials. Добавлена миграция0006.
Подробности и точные команды: [TELEGRAM_ASSISTANT.md](TELEGRAM_ASSISTANT.md).

Локально: Python154/154, Deno13/13, PostgreSQL16/RLS/транзакции пройдены,
frontend28/28 и сборка пройдены. Первый feature-коммит b6f7e17 прошёл Linux CI
38571466375 (145Python +6 пропусков необязательного кэша; 4+2 браузерных теста).
Точные области реальных и mock-проверок: telegram-assistant-validation.json.

Повторная реальная read-only проверка Canvas38570459817 получила401 со старым
GitHub Secret. Новый токен владельца ещё не установлен. Реальные Telegram сообщения,
setMyCommands/setWebhook, hosted migrations и production activation НЕ выполнялись.
Default branch не изменён; workflow_run completion требует развёртывания там после
одобренного владельцем merge либо отдельного staging-репозитория. Научные параметры
и эталонные датасеты сохранены. Статус: локальная реализация готова; hosted активация
и реальный сквозной тест требуют внешних credentials и выбранного staging окружения.
