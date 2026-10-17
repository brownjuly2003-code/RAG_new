# Проверка внешнего пилота участка 1.6 на Sol 6.1 xhigh

Дата: 2026-10-07. По прямому разрешению владельца один встроенный агент
`gpt-6.1-sol`, reasoning `xhigh`, проверил расчёты, тесты и существующий
раздел 1.6 спецификации с Acceptance contract. Это разрешение относится к
данной проверке. Основной агент сверил код, логи и численные результаты.

**106 тестов прошли, независимый расчёт 124 строк совпал.** Обнаружена
несовместимость регистрации новых выборок с verifier. Текущий пилот она
не затрагивает; исправление проверено 2026-10-07 (раздел ниже). Редакция 11 ещё
не написана; её холодное ревью и закрытие всего участка 1.6 остаются впереди.

Проверенный код: `fc44c7abdbf256f25dfc5c3842946cb1725dee8c`.
Агрегаты и их тесты сохранены в `3f847e1`; происхождение измерений,
ограничения и SHA — в [капсуле пилота](../../../docs/evidence/external-bases-pilot.md)
и [receipt](../../../reports/external/64a72e5/pilot/receipt.json).
При аудите реальные measure, retrieval и модели не запускались, вопросы
holdout и locked не читались. Диагностические примеры использовали фикстуры.

## Проверки на Mac

Sol проверил исходный код в отдельном снимке
`/Users/julia/RAG_new_sol61_slice16_20261007_b6e7a8d962fa`:

```text
python -m pytest tests/test_external_pilot.py tests/test_external_parts.py tests/test_external_gold.py tests/test_power.py tests/test_external_bases.py -q -p no:schemathesis -p no:cacheprovider --basetemp=.tmp/pytest-sol61-slice16 --tb=short
```

Результат: **72 passed, 1 warning, 8.09s, exit 0**. Первый запуск дал
43 passed и 29 ошибок фикстур: `git archive` не включил ignored-каталог
`.tmp`, нужный родитель `basetemp`. После создания каталога в снимке
сделан один адресный повтор; код проекта не менялся.

Основной агент проверил новые артефакты и документы в снимке
`/Users/julia/RAG_new_pilot_artifact_20261007_fc44c7a` с явным overlay
девяти файлов будущего коммита `3f847e1`:

```text
python -m pytest tests/test_external_pilot_artifact.py tests/test_external_connection_artifact.py tests/test_docs_hygiene.py tests/test_docs_quality.py tests/test_docs_publication.py -q -p no:schemathesis -p no:cacheprovider --basetemp=.tmp/pytest-pilot-green --tb=short
```

Результат: **34 passed, 1 warning, 6.36s, exit 0**. Оба прогона использовали
`/Users/julia/RAG_new_gr4_venv/bin/python` и
`PYTHONPATH=/Users/julia/RAG_new_mf_gate_site`. Предупреждение однотипное:
существующий Starlette/AnyIO `DeprecationWarning`.

Локальные логи: `.tmp/sol61-slice16-20261007/pytest-fixed.log` и
`.tmp/pilot-20261007/green.log`; команды SSH и SHA overlay сохранены рядом.

## Независимый расчёт

Sol пересчитал все 124 строки
[sizes.json](../../../reports/external/64a72e5/pilot/sizes.json) без импорта
кода проекта: квантиль Student через incomplete beta и бисекцию,
variance, design effect, SE, MDE, effect_for_rule и мощности.
Расхождений нет: максимальная ошибка квантиля `7.11e-15`, остальных
величин `2.84e-15`. SHA агрегатов и sizes совпали с receipt.

| Выборка шага 1 | Размер | MDE | Эффект для мощности правила 0.8 |
|---|---:|---:|---:|
| ConditionalQA primary | 165 страниц | 0.069329 | 0.070719 |
| ConditionalQA several_sections | 145 страниц | 0.074009 | 0.074009 |
| WixQA ExpertWritten | 200 вопросов, 154 кластера | 0.091070 | 0.091070 |

В пилоте 50/40 пар, потерь нет, primary variance 0.020/0.025;
зарегистрированная variance остаётся 0.10 при ICC=1 и Student.
Две руки ConditionalQA и WixQA укладываются в 37.334487 или 33.289647 часа
при потолке 64 часа. Две выборки ConditionalQA — альтернативы по гипотезе.
Мощности условны: при эффекте +0.05 правило даёт 0.500/0.471/0.334,
а NI при истинном нуле — 0.123/0.112/0.087. Пилот не доказывает выигрыш
будущего механизма и не даёт SHIP-вердикта.

Скрипты `audit_numbers.py`, `check_selected.py` и результаты `numbers.json`,
`selected-numbers.json` сохранены в `.tmp/sol61-slice16-20261007/`.

## Замечания к коду и действующему тексту

1. **Исправлено 2026-10-07: verifier отвергал новые selections.**
   [Спецификация](../../../docs/specs/semantic-precision-metrics.md), строки 2038–2042,
   разрешает добавить выборку отдельным коммитом. Но
   [external_parts.py](../../../evaluation/external_parts.py), строки 297–313
   и 375–388, сравнивает весь набор selections с `build_base`, создающим
   только `pilot`. `select_step` в
   [external_base.py](../../../scripts/external_base.py), строка 370, вызывает
   этот verifier. На Mac корректная baseline-копия pilot читается через
   `read`, но `verify` даёт `ValueError: wixqa: the registered parts are not
   those the rules give`. Это препятствует последующим регистрациям.
2. **Доступ к отдельной selection исправлен 2026-10-08 (раздел ниже).**
   На момент аудита `is_open` в `external_parts.py` учитывал только base
   и part. Запись opened для выборки из одного synthetic-вопроса позволяет
   прочитать весь part из трёх. Спецификация, строки 2021–2024, прямо
   откладывала эту защиту до редакции 11. Реальный `opened` остаётся пуст;
   пример не устанавливает раскрытие настоящих locked-данных.
3. **Ранний отказ по существующему выходному пути добавлен 2026-10-08.**
   [external_pilot.py](../../../scripts/external_pilot.py), строки 903–908
   и 945–946, вычисляет результат до `_write_once`; последняя запрещает
   другое содержимое по тому же пути. Это защита документа, а запрет
   повторного измерения в спецификации, строки 2197–2212, остаётся
   нормативным. Повторное реальное измерение не выполнялось. Проверка
   выходных путей теперь стоит перед расчётом (раздел ниже); новое имя файла
   не связывается с прежним измерением, поэтому правило реестра сохраняется.

Synthetic probe завершился с exit 0; его команда и оба результата —
`probe-ssh-script.txt` и `selection-probe.log` в каталоге проверки Sol.

## Исправление регистрации selections — 2026-10-07

Генератор и verifier теперь пересчитывают дополнительные selections по их
зарегистрированным правилам. Проверяются порядок ID, SHA, счётчики и кластеры;
исходный `pilot` остаётся обязательным и сохраняет своё правило. Команда
проверки файла принимает расширенную регистрацию, а `--write` сохраняет её
дополнительные selections. Проверка закрытой выборки не разрешает её экспорт.
Реальная регистрация, `opened`, агрегаты и размеры пилота не менялись.

12 регрессионных проверок добавлены в `tests/test_external_parts.py`:
до исправления 5 failed / 22 passed; после него **160 passed, 1 warning,
exit 0** в семи релевантных модулях, включая `test_production_baseline.py`.
Тест воспроизведения размеров отдельно связывает исторические SHA кода с
обоими агрегатами и текущие SHA с текущими файлами; все остальные поля отчёта
сравниваются полностью. `ruff` и `mypy evaluation/external_parts.py
--follow-imports=skip` прошли. Запуски выполнены на Mac в отдельном снимке
`/Users/julia/RAG_new_selections_20261007_a0e3c55`: HEAD `a0e3c55` плюс явный
overlay, SHA файлов сверены. Команды, SHA и логи сохранены локально в
`.tmp/external-selections-20261007/`. Это подготовка к 1.7, не закрытие 1.6
и не новое измерение качества. Замок на selection и ранний отказ повторного
measure из пунктов 2–3 выше этим исправлением от 2026-10-07 не реализованы.

## Ранний отказ повторного measure — 2026-10-08

`scripts/external_pilot.py` отклоняет существующий `--out` или `--aggregates`
до чтения базы и записей прогонов, даже при совпадающем содержимом.
Совпадение двух выходных путей, включая путь через `..`, — ошибка аргументов.
`sizes` продолжает читать сохранённые документы. Защита привязана к путям:
она не запрещает новый выходной путь и не заменяет реестр запусков.

В `tests/test_external_pilot.py` добавлены шесть проверок и изменено ожидание
повторного вызова CLI: **red 7 failed / 25 passed; green 101 passed,
1 warning, exit 0** в семи модулях пилота, частей, gold, баз, артефактов
пилота и подключения, мощности. `ruff`, `mypy` и `git diff --check` прошли.
Mac-снимок `/Users/julia/RAG_new_pilot_guard_20261008_d29aec0`: HEAD `d29aec0`
с явным overlay; SHA сверены. Команды и логи — локально в
`.tmp/pilot-measure-20261008/`. Тесты используют синтетические данные;
реальный пилот не пересчитывался. Это подготовка, не закрытие участка 1.6.

## Что должна закрыть редакция 11

Нужно согласовать deciding и NI-метрики, nomination базы и страты,
роль второй базы и собственного holdout, исходы противоречащих результатов;
зарегистрировать baseline, acceptance и refinement selections с SHA,
размерами, знаменателями, мощностью и стоимостью; ограничить opened
выборкой и механизмом, определить одно чтение, возобновление и исчерпание.
Для refinement нужны estimator и правила потерь, для равного бюджета —
допуски, для MultiHop-RAG — advisory metrics и знаменатели.

Устаревшие «395 вопросов» в Acceptance уже отменены разделом 1.6,
строки 2045–2054. До редакции 11 действует только transferability-роль
внешней базы. Новая редакция должна устранить эту временную разницу,
сохранить ограничения мощности, missingness и переноса Simulated →
ExpertWritten, а затем пройти отдельное холодное чтение.

## Доступ к точной selection — 2026-10-08

Разрешение `opened` теперь требует `base`, `part`, `selection`,
`cases_sha256` и `by: "acceptance 4.1"`. SHA связывается со списком ID в
его порядке. Оно разрешает только названную выборку: весь закрытый part,
другая selection с теми же ID, расширенный или изменённый список,
устаревший SHA и старое разрешение только на part отклоняются. Экспорт
отказывает до чтения вопросов и создания выходного файла. Проверка
регистрации и `--write` сохраняют существующие `opened` без расширения
разрешений. Спецификация обновлена в пределах этого контракта доступа.

Первая регрессия: **red 9 failed / 26 passed**. Дополнительная проверка
пересборки выявила **2 failed / 35 passed**: verifier отвергал регистрацию
с разрешением, а `--write` стирал его. После обоих исправлений на Mac
**190 passed, 1 warning, exit 0**:

```text
python -m pytest tests/test_external_parts.py tests/test_external_pilot.py tests/test_external_gold.py tests/test_external_bases.py tests/test_external_pilot_artifact.py tests/test_external_connection_artifact.py tests/test_power.py tests/test_production_baseline.py -q -p no:schemathesis -p no:cacheprovider --basetemp=.tmp/pytest-selection-guard-builder-green --tb=short
```

`ruff` и `mypy evaluation/external_parts.py --follow-imports=skip` прошли.
Снимок `/Users/julia/RAG_new_selection_guard_20261008_f60bdf1`: HEAD
`f60bdf1` с явным overlay, SHA четырёх файлов сверены. Команды, SHA и
логи сохранены локально в `.tmp/external-selection-guard-20261008/`.
Тесты синтетические; настоящая регистрация и измерения не менялись.
Это подготовка к 1.6: привязка к механизму, одно чтение, возобновление и
исчерпание по-прежнему требуют редакции 11; весь участок не закрыт.
