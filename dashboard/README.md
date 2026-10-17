# FlyMind Neural Observatory

Локальный научный dashboard: React 19, TypeScript, Vite 7, React Three Fiber / Three.js,
Recharts. Он читает реальные экспорты существующего Neural Engine; симуляция в браузере
не запускается. Модель экспериментальная, **не биологически валидированная**.

## Запуск

Нужен Node.js 20.19+ или 22.12+.

```bash
cd dashboard
npm ci
npm run dev
```

Открыть URL, напечатанный Vite: обычно http://127.0.0.1:5173/.
Готовая телеметрия уже находится в `public/data/`; Python и backend для просмотра не нужны.

```bash
npm run build
npm run preview
```

`dist/` — полностью статический сайт. Для будущего Cloudflare Pages: root directory
`dashboard`, build command `npm ci && npm run build`, output directory `dist`.
Workers, постоянно работающий сервер, Supabase и платная служба не требуются.
`public/_headers` задаёт revalidation для данных и immutable cache для hashed JS/CSS.
Развёртывание в этой задаче не выполнялось.

## Работа с интерфейсом

- Три вкладки baseline / weak / strong сохраняют общий cursor для сравнения.
- Play/pause, reset, скорость 0.05×–2× и scrubbing используют записанное время в ms.
- 3D: вращение левой кнопкой, zoom колесом, pan правой кнопкой. Click на GPU-инстансе
  выбирает нейрон; поиск принимает полный root ID, тип или side.
- Входы GF, связи выбранной клетки, все пары; минимальное число синапсов и фильтр
  spiking cells + selection меняют только отображение. Максимум 2 000 крупнейших
  подходящих пар показан явно; весь датасет сохранён в телеметрии.
- Инспектор показывает реальные ID, медиаторные аннотации, предполагаемый знак модели,
  soma и крупнейших направленных партнёров. Клик по партнёру меняет выбор.
- Raster содержит каждый spike event; строки следуют исходному порядку root ID.
  Для отдельных клеток используйте поиск: полный raster плотнее экранного разрешения.
- Потенциалы показываются только у шести записанных клеток. При отсутствии записи
  интерфейс явно сообщает об этом; восстановленных потенциалов нет.
- Population plot — точные counts в 10 ms bins. Сравнение использует общий clock,
  а не искусственно сдвинутые peaks. Стимул — экспортированный, некалиброванный drive.

## Какие данные реальные

1 500 настоящих FlyWire FAFB v783 IDs, 25 206 строк измеренной связности,
17 186 направленных пар, 276 399 синапсов. Все neuropil и raw NT annotations сохранены.
Видимые линии агрегируют строки одной направленной пары; число synapses — сумма
исходных count, без нормализации или изменения весов.

Спайки и потенциалы — **записанные результаты вычислительной модели**, не измерения
живой мухи. Для трёх опытов экспортированы соответственно 0 / 344 / 834 спайка,
0 / 282 / 418 активных клеток, GF 0/0, 2/2, 3/4. Параметры, веса, topology и первичные
экспериментальные файлы не изменяются.

Есть два разных пространственных режима:

- **Type-group graph** — детерминированная неанатомическая раскладка всех 1 500 клеток.
  Расстояния/оси безразмерны и не имеют биологического смысла.
- **Real soma** — 1 497 настоящих soma из SHA-256-verified `annotations.tsv` закреплённого
  commit `ebd66db2596fcc39c6950fb54ea3efa00f7fe8a0`. Исходные voxel coordinates сначала
  переводятся из 4×4×40 nm в µm, затем центрируются и равномерно масштабируются для камеры.
  Три клетки без soma пропускаются вместе с их линиями; замен нет. GF soma присутствуют.

[Определения координат закреплённого источника](https://github.com/flyconnectome/flywire_annotations/blob/ebd66db2596fcc39c6950fb54ea3efa00f7fe8a0/supplemental_files/Supplemental_files_columns.md)
различают anchor `pos_x/y/z` и soma `soma_x/y/z`. Здесь используются именно soma.
Скелеты доступны отдельно через [источник аннотаций / Zenodo](https://github.com/flyconnectome/flywire_annotations/tree/ebd66db2596fcc39c6950fb54ea3efa00f7fe8a0#skeletons--nblast-scores),
но не включены в текущий bundle и не проверены для каждого из 1 500 IDs.
Сферы — символические glyphs, не размеры клеток. Стрелки между soma/узлами показывают
направленную adjacency; они не изображают форму нейритов или координаты контактов.

Потенциалы экспортированы losslessly в Float64. В графиках применяется min/max envelope,
сохраняющий исходные extrema и sample indices; прямые линии между оставшимися точками
— графическая интерполяция, не новая запись. Число у cursor берётся из предыдущего
исходного sample. Подсветка узлов = spike в предыдущие 20 ms, не визуальная реконструкция
распространения потенциала по аксону.

Ограничения первой фазы сохраняются: generic LIF, некалиброванный visual drive,
неподтверждённая receptor polarity, неполные GF/сенсорные входы, отсутствие gap junctions,
VNC и behavioral output; LPLC2 dependence не валидирована совпадающим visual protocol.
Исходные GF input coverage — 80.49% / 82.82%. Лицензия данных: CC BY-NC 4.0.

## Экспорт и контракт

Полный контракт: [TELEMETRY.md](TELEMETRY.md). Перед повторным экспортом исходные
экспериментальные JSON.gz должны существовать. Из `dashboard/`:

```bash
npm run data:export
# Или явно выбрать suite:
python3 scripts/export_telemetry.py --suite ../data/neural/runs/escape-resumed-20261014/escape-suite.json
```

Экспортер использует только Python stdlib. Он читает первичные файлы и пишет только
производные `dashboard/public/data/`; не импортирует Brian2 и не меняет engine.
Если annotation cache отсутствует, soma не экспортируются, графовый режим остаётся
доступен. Для точного воспроизведения комплектных spatial assets нужен закреплённый cache.

## Проверки

```bash
npm test
python3 -m unittest discover -s tests -p 'test_*.py' -v
npm run build
npm run test:e2e
```

E2E используют установленный Google Chrome (macOS default path или Chrome channel на
других ОС). Можно задать `PLAYWRIGHT_CHROME_PATH=/path/to/chromium` перед командой.
Playwright при необходимости запускает Vite сам. Для проверки статической сборки:

```bash
npm run test:e2e -- --config playwright.static.config.ts
```

Tests сравнивают каждый edge row, каждый spike и каждый voltage sample с первичными
экспортами; проверяют координаты, детерминизм, неизменность источников, SHA-256,
ошибочную версию/повреждённые файлы, replay, browser interactions и mobile overflow.

## Архитектура и производительность

- `scripts/export_telemetry.py`: offline presentation export.
- `src/telemetry.ts`: v1 types, runtime validation, endian-aware binary decoding.
- `src/data.ts`: `TelemetrySource` contract и HTTP adapter. Для публичного static/Storage
  URL достаточно `VITE_TELEMETRY_BASE_URL=https://host/path` при сборке; bucket не создан.
- `src/analysis.ts`: derived rendering-only adjacency, positions, replay и envelope.
- `src/components/`: GPU viewer, canvas raster, Recharts signals, neuron inspector.
- `src/App.tsx`: shared experiment/selection/replay state.

1 instanced mesh для 1 500 glyphs + 1 batched line geometry для всех показанных рёбер
и стрелок: два GPU draw calls. Нет React-компонента на синапс или нейрон.
Paused view использует demand rendering; replay UI обновляется примерно до 30 Hz,
DPR ограничен 1.5. Геометрия, positions и adjacency memoized. Three viewer загружается
отдельным lazy chunk; charts тоже отделены от основного bundle.

Все data assets вместе: 2 040 629 bytes до HTTP compression; расчетный gzip размер
325 299 bytes (сумма отдельных assets, каталог дополнительно ~2 KB). Float64-сигналы
без повторяющихся JSON timestamp arrays. Числа gzip — не замер network transfer;
локальный Vite может отдавать файлы без compression.

## Следующие интеграции

Будущий PostgreSQL adapter должен читать metadata каталогов/запусков, а Supabase Storage
adapter — возвращать immutable assets или signed URLs с тем же SHA-256 contract.
Проверка аутентификации/доступа нужна только при подключении закрытого хранилища;
service-role keys никогда не должны попадать в клиент. Схемы, bucket, RLS и миграции
пока не созданы. Нужны также отдельное согласование deployment, при необходимости
подключение verified skeletons/контактов и независимая биологическая валидация.

## Проверенный локальный результат

Финальная сборка TypeScript/Vite успешна; 20 Vitest, 5 Python integration tests и
4 browser scenarios прошли. Browser scenarios выполнены и на dev, и на статическом
`dist` (4/4 в каждом режиме). Проверены также выбор реальной GF кликом по GPU-инстансу
и recoverable checksum error. Ошибок JavaScript в основном сценарии нет.

Chrome SwiftShader зафиксировал **2 draw calls**. JS heap в одном snapshot:
**60.22 MiB**; это не peak RSS процесса и не hardware FPS benchmark.
Vite оставляет одно advisory о размере Three.js/R3F vendor chunk: 882.89 KB minified /
238.57 KB gzip. Его размер не скрыт повышением warning threshold.
Машиночитаемый результат — [validation.json](validation.json).
