# FlyMind Observatory telemetry v1

`schema = "flymind.observatory/v1"`. Неизвестная версия отклоняется, а не интерпретируется
по догадке. Это presentation contract над неизменённым Engine JSON v1, не новый
биологический датасет. Первичная реализация включает три опыта одного исходного графа.

## Catalog → graph → experiments

`catalog.json` задаёт `graph.path + sha256` и три experiment entries с ID, path, SHA-256,
summary counts, duration, contrast, r/v. Каталог — точка входа `TelemetrySource`.
`files` содержит raw/gzip sizes и хэши. Все timestamps в ms, voltages в mV,
полные uint64 root IDs всегда строки; числовые ID недопустимы.

`graph.json` хранит:

- `neurons`: ordered objects с точными source annotations, строковым `root_id`, role и
  `soma_voxel: [x,y,z] | null`. Порядок является единственным index dictionary.
- `edges`: ordered tuples `[pre_index, post_index, synapse_count, neuropil_index, raw_nt_index]`.
  Одна tuple = одна исходная measured neuron-neuron-neuropil строка. Нельзя трактовать
  каждую tuple как единичный синапс или молча заменить raw NT знаком модели.
- `neuropils`, `raw_transmitters`: словари категорий; `edge_columns` явно описывает tuple.
- `dataset`: исходный manifest, citations, лицензия, SHA-256 CSV, selection и limitations.
- `manifest_sha256`, `spatial`: coordinate source SHA-256, ссылка на закреплённые определения,
  voxel scale [4,4,40] nm, soma coverage и `morphology_in_bundle=false`.

`baseline.json`, `weak.json`, `strong.json` содержат:

- source path, SHA-256 первичного JSON.gz, activity hash и hashes пяти файлов engine code;
- `graph_sha256` для запрета смешивания разных сетей;
- все engine parameters, model assumptions, `biological_response_validated=false`;
- `spikes`: sorted `[time_ms, neuron_index]`, **каждое событие без downsampling**;
- `activity`: full-run spike counts/rates для всех 1 500 исходных IDs;
- `readout`: исходные GF spike times, latency, depolarization/peak и sampling metadata;
- `stimulus`: исходные waveform samples и геометрия с `biologically_calibrated=false`;
- `population`: bins `[start_ms, all, LC4, LPLC2, GF]`, bin width 10 ms; точная агрегация;
- `voltage`: `path`, SHA-256 и descriptors для отдельного binary asset;
- исходные scientific limitations.

## Lossless voltage payload

`*.voltage.bin` — последовательность **IEEE-754 Float64 little-endian** без header.
Descriptor: `neuron_index`, `byte_offset`, `length`, `start_ms=0`, `step_ms`, `phase`,
`signal="recorded_simulation_voltage"`. Offsets в bytes; length в samples.
GF: 11 000 samples на клетку, step 0.1 ms, phase `before_thresholds`.
Четыре sensory cells: по 1 100 samples, step 1 ms, phase `start`.
Последний sample находится до duration, конечный state не подменяет последний sample.

`time[i] = round(start_ms + i*step_ms, 9)`: это lossless regular-grid timestamp encoding
для этих экспортов. Экспортер проверяет исходные time arrays; irregular sampling
отклоняется и потребует расширения контракта. Значения потенциалов не округляются,
не quantize и не интерполируются при хранении. Не записанные клетки не имеют descriptor.

Браузер проверяет checksum перед JSON/binary decoding, затем schema, graph counts,
ID/index bounds, sorted spikes, совпадение counts, запрет прямой GF injection,
finite values и binary ranges. Неверные/stale файлы дают recoverable loading error.

## Derived presentation

Суммирование measured edge rows по направленной паре, type-group layout, soma-centering,
flash window, plot envelope и bins не изменяют нейронную динамику. Binary sample arrays
остаются доступными целиком в памяти даже при downsampling графика. Время воспроизведения
никогда не запускает симуляцию и не создаёт новые spikes. Никаких искусственных
axon propagation traces или potential reconstruction нет.

Крупные будущие эксперименты можно сегментировать на time chunks и загружать через
новый `TelemetrySource`, сохраняя IDs, unit contract и source hashes. Пока разбиение
по experiment + graph + binary достаточно для этого 1 500-клеточного набора.
