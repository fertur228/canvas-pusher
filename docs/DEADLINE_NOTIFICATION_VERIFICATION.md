# Проверка обязательных уведомлений FlyMind — 2026-10-17

Рабочая ветка: `feat/flymind-neural-poc`, PR#1 открыт. Production scheduler и
primary-chat delivery выключены; merge не выполнялся. Network Media не затронут.

## Что изменено

- Новое задание создаёт одно событие и попадает в primary outbox в обнаружившем
  скане при любом сроке/баллах, включая null и 0. Silent bootstrap сохранён.
- Пороги: **24/12/6/3/1 час**.48h и дополнительные overdue-уведомления удалены.
- Атомарно сохраняются пересечённые пороги и причины: queued, skipped_late,
  covered_by_creation, covered_by_deadline_change, silent_bootstrap, submitted,
  expired. queued означает постановку в outbox; доставка подтверждается message_id.
- Из>24h сразу в 2h: одно напоминание 3h,24/12/6 помечены пропущенными. Новое
  задание на 4h: только creation, затем отдельные 3h/1h. Изменение срока покрывает
  текущий порог собственным уведомлением, последующие работают с новой версией.
- Перед send/retry повторно читается snapshot: submitted, другой срок/версия,
  истёкший или устаревший порог отменяют отправку. Ошибка чтения БД не разрешает
  отправку непроверенного напоминания. Отменённая задача не запускает Brian2.
- Primary delivery выполняется до neural work; бюджет 25 для edits больше не
  ограничивает первичные уведомления. До 1000 попыток/10 мин за запуск; при rate
  limits/сбоях outbox сохраняет задания. Неоднозначный send не повторяется вслепую.
- Emoji-сообщения содержат название, курс, Almaty deadline, оставшееся время,
  статус сдачи, баллы/оценку и безопасную Canvas-ссылку. В обычных сообщениях нет
  event ID, GF counts или ожидания симуляции. Enrichment остаётся экспериментальным.

## Тесты

Локально: **195 Python passed**,172 dependency warnings,83.37s; Deno15; Vitest28;
TypeScript/Vite build; Playwright4local+2private HTTP-mock. Ruff critical checks,
compileall, diff checks и repository/history secret-signature checks прошли.
Первый запуск со старым `.venv` остановился на несовместимых Brian2/NumPy;
полная проверка выше выполнена в документированном `.venv/neural`, без изменения
биологической модели или ослабления тестов.

CI на 90823403c9f3062ed247f18f3d9da95f86027e10 полностью SUCCESS:
https://github.com/fertur228/canvas-pusher/actions/runs/39049349780
Python189passed/6skipped (необязательный source cache),172warnings,57.34s;
Deno15,Vitest28,TypeScript/build,4+2browser tests, PostgreSQL16 RPC/RLS/Storage,
Linux scientific controls, real-neural synthetic batch. Локально PostgreSQL17
также применил все 8 миграций и проверил новый audit-health invariant.

Прежние тесты, требовавшие 48h или двойное creation+reminder, заменены точными
assertions нового обязательного поведения. Добавлены границы всех 5 порогов,
4h/undated/zero/unknown points, late/crossed bands, grade≠submission,
A→B→A deadline versions, UTC equivalence, concurrent CAS, stale queued reminders,
30creation notifications в одном drain, Telegram retry/uncertainty и neural failure.
Отказы сервисов тестируются через явно обозначенные fixtures/mocks; реальных
сбоев Telegram или Canvas не фабриковали.

## Реальный Canvas и polling

`docs/deadline-canvas-preflight.json`:14GET→HTTP200,6 курсов,20 заданий,91 файл,
2 объявления,0 ошибок,0 мутаций,0Telegram;29.996s. Cost56.88694, minimum remaining
quota592.09832. Параллелизм уменьшен 8→2; pagination/retry/Retry-After сохранены.

В исходнике cron=`2-59/5 * * * *`;288 запусков/сутки,8640/месяц; около 4032Canvas
GET/сутки. Оценка 8640–17280runner min/месяц при 60–120s/job. Репозиторий реально
PUBLIC, стандартные Ubuntu runners бесплатны. Это не укладывается в 2000 мин
частного Free-репозитория. Платный billing не активировался.

При штатном расписании ожидание обнаружения 0–5 мин плюс queue/setup/fetch/send;
ориентир около 1–7 мин, не гарантия. GitHub может задерживать/пропускать cron,
выполняет его только на main и отключает неактивные public repos. Сейчас обычный
workflow остаётся `disabled_inactivity`. Concurrency/cancel-in-progress:false
и транзакционные CAS/leases сохранены. Подробности/официальные источники:
[COST_ESTIMATE.md](COST_ESTIMATE.md).

## Миграция и сохранность

Новая `202610170007_flymind_suppressed_health.sql` реально применена обычным CLI
в существующий **Canvas-pusher**, ref`irjasmzytjeohwfpdnrl`. Она заменяет только
тело audit-функции: suppressed auxiliary job больше не обновляет neural success.
Никаких migration-time UPDATE/DELETE/DROP/seed, изменений Auth/RLS/grants.
SHA-256: `990dfb29ae9ad675af98d7ed129927048d67f2216b7ee4f750889495e452ebd4`.
Все 7 прежних миграций неизменны. Dry-run содержал только 0007. До применения:
backup authenticated decrypt + PGDMP header проверены; ключ отдельно и внеGit.
После: история содержит 8 миграций, SECURITY DEFINER safe search_path сохранён,
anon/authenticated execute запрещён. Исходные row hashes совпали:336canvas_state,
32original course_grades,14health_checks. Всего course_grades38 с прежними 6test-rows.

## Hosted test-chat evidence

[Cloud workflow39049711232](https://github.com/fertur228/canvas-pusher/actions/runs/39049711232)
успешен на 9082340: весь job294s. Два реальных Canvas-скана:176.825s, оба status=ok,
0 новых событий/ошибок, число отправок неизменно. Latest verified check:
2026-10-17T16:34:01.350147Z (21:34Asia/Almaty).

Синтетический deadline-план:14 шагов,88.236s,12persisted events; **11 реальных
Telegram сообщений с message ID**,1queued reminder отменён послеsubmission.
Все 24/12/6/3/1h проверены; поздний запуск отправил только 3h и сохранил
24/12/6 какskipped_late. Повторы каждого ingest:0 новых событий. Повтор завершённого
плана локальным клиентом:0 дополнительных доставок, job counts неизменны.
11neural associations complete с 2 реальными cached profiles/artifacts;1suppressed
без запуска симуляции. Оба private artifact SHA-256 проверены скачиванием.
Первичные сообщения отправлены до вычислений; shadow mode не редактировал их.

Это реальные Supabase/Telegram/FlyWire на GitHub-hosted Ubuntu, но задания и
ускоренные часы явно СИНТЕТИЧЕСКИЕ. Не тест публикации в Canvas и не доказательство
реального сбоя Telegram. Primary chat не использовался; fixtures не включались в
verified real-Canvas deadline list. Финальные очереди не имеютpending/dead/ambiguous.
FLYMIND_TEST_CHAT_VALIDATION сноваfalse. Production flagsfalse/disabled,
check_canvas.yml по-прежнемуdisabled_inactivity. Миграция 0007 deployed; код
исполнен в изолированном test-account workflow. Webhook/Cloudflare для этой
задачи не переразвёртывались,PR#1 не merged.

Машинные доказательства: [deadline-hosted-verification.json](deadline-hosted-verification.json),
[deadline-migration-verification.json](deadline-migration-verification.json).
Остались неблокирующие warnings:172Brian2/dependency deprecations, Vite large
Three.js chunk (lazy-loaded), pinned GitHub Actions targetNode20 с автоматическим
runtimeNode24. Все соответствующие тесты/build прошли; warnings не скрывались.

## Оставшиеся production gates

Явный owner Auth/sign-in и привязка production account; реальный приватный replay;
проверка `/check` с completion workflow наdefault branch; отдельное разрешение
наmerge/production rollout. После этих gates — silent production bootstrap,
проверка primary recipient и controlled production scan, повтор бездубликатов,
затем расписание. Эти действия в текущей задаче НЕ выполняются. Токены не нужны
повторно: реальный Canvas доступ уже подтверждён. Нейронная модель остаётся
экспериментальной; synaptic topology/параметры/референсные данные не менялись.
