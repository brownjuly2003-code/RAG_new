# Design audit of the label-verification protocol — GPT-6-Astra, 2026-10-04

Plan step 1.3b registers how two models verify the development-set drafts
(decision D11). Before any code was written, the lead's draft of the rule —
the sixth revision of [the development ruler](../../../docs/specs/semantic-precision-metrics.md)
and the requirement for the tool, [label-verification.md](../../../docs/specs/label-verification.md)
— was given to GPT-6-Astra (OpenAI, through the Codex companion, read-only)
with seven questions: agreement with the plan (G38 а, б; D3, D10, D11), holes
in the decision rule, the wide scan, disagreements between the two texts,
leaks and blindness, the family map and reserve, and whether `gold_error` can
be gamed. It returned 22 findings: 13 blocking, 8 «should», 1 nit.

**Disposition: all 22 applied before the texts entered the repository.** The
committed texts are the revised ones; the audited draft is not in the
repository. Three findings were applied in a stricter form than the auditor's
minimal wording:

- №3 (limits of a repair): the question text is frozen — a repair changes the
  label, never the question; a new question is a replacement (G38 в).
- №10 (file names inside corpus text): every corpus file name in an outgoing
  text is replaced by the document's pseudonym, any other `.md` name by a
  neutral token.
- №11 (the `scope` template): the `scope` text is not sent at all; the
  protocol also says that an owner-confirmation note inside a case is not
  evidence.

Because the question is frozen, the wide scan is made once for every case and
serves both rounds. The auditor is the model family that reviews MyFlow
slices here; it is also the vendor of the draft author (`gpt-6.1-sol`), which
is why it audits the rule and does not verify cases.

## Findings as returned (Russian, verbatim)

1. **blocking — `spec-amendment.md`, `gold_error`.**
   Цитата: “The case leaves … the critical-error count of every arm”. Подтверждение существования подходящего отрывка не подтверждает правильность ответа руки. Рука может процитировать верный отрывок, дать опасный ответ и получить исключение из критических ошибок. Исключение также стирает ошибки другой руки. Это новый стимул, которого прежнее правило не создавало.
   **Минимальная правка:** “`gold_error` removes only penalties caused by the erroneous unresolvable label; faithfulness, citation correctness and independently established critical errors of each answer remain scored.”

2. **blocking — `label-verification.md`, `plan` и `check`; `spec-amendment.md`, исправление.**
   Цитаты: “when a case fails the deterministic rules of the pilot verify script”; “the repair … passes the verify script”; “Set-level rules … do not apply to the verified set”. Эти требования несовместимы при смене класса. `validate_metadata` проверяет ровно 30 кейсов, исходные квоты, компоненты и footprint; `load_artifacts` — исходный SHA JSONL. Корректно переклассифицированный кейс не пройдёт полный pilot verifier. Исключение только для готового verified set не исправляет запрет на стадии `plan`.
   **Минимальная правка в обоих текстах:** полный неизменённый pilot verifier применяется к исходному пилоту; исправления проходят перечисленные проверки отдельного кейса и источников, без исходных квот, JSONL SHA и исходного графа кейсов.

3. **blocking — `spec-amendment.md`, границы исправления.**
   Цитата: “the repair keeps the case id, the seed-selected section and the question style”. Остальное фактически разрешено менять: информационную потребность, partner sections, документы, дату и автора. Можно заменить трудный вопрос простым под тем же ID либо добавить документ из зарегистрированного holdout reserve. Сохранение seed-section этого не предотвращает. Последствия изменения семейства или компонент не описаны.
   **Минимальная правка:** сохранять автора, corpus version, `as_of`, исходную информационную потребность, seed-section и стиль; перечислить разрешённые исправления. Новые источники разрешать только вне резерва; после изменения источников пересчитывать footprint и компоненты. Новую информационную потребность считать заменой, относящейся к ещё открытому G38 «в».

4. **blocking — `label-verification.md`, проверка применённого набора.**
   Цитата: “a `model_verified` case without two confirming verdicts”. Для пары `5a = confirm / unverifiable`, при остальных успешных проверках, `decide` обязан подтвердить кейс, а буквальное требование `check` — отклонить. Аналогично 5c вообще возвращает уровень, а не подтверждение.
   **Минимальная правка:** заменить на “a `model_verified` case whose two valid verdicts do not satisfy the protocol’s confirmation predicate”.

5. **blocking — `spec-amendment.md`, тяжесть ошибки.**
   Цитаты: “or across the `critical` boundary”; “One-step severity differences … not rejections”. Зарегистрировано `high`, оба проверяющих дали `critical`: первая фраза требует отказа, вторая запрещает отказ.
   **Минимальная правка:** “One-step severity differences that do not cross the `critical` boundary are published as disagreements, not rejections.” Явно записать порядок `low < moderate < high < critical`.

6. **blocking — `spec-amendment.md`, неоднозначность самой шкалы 5c.**
   Цитата: “`critical`: … an unlawful act; `high`: … a legal or regulatory breach”. Одна и та же незаконная операция подходит под оба определения, а переход между ними решает судьбу кейса.
   **Минимальная правка:** задать приоритет и непересекающиеся основания: например, `critical` для прямо перечисленных опасных или запрещённых действий, `high` для остальных материальных, кадровых и регуляторных последствий. Уточнить, что выбирается максимальный применимый уровень для конкретного ошибочного ответа.

7. **blocking — `spec-amendment.md`, проверки 5a/5b.**
   Цитаты: “the rule comes from that document, not from an external norm it only cites”; “`unverifiable` … when … the rule’s force rests on an external norm whose text is not supplied”. Один проверяющий может применить первое предложение и дать `reject`, другой — второе и дать `unverifiable`. Результат меняется с отказа на подтверждение без изменения доказательств. T64-06 спрашивает содержание внутренней политики, прямо исключая проверку действующего закона; карточка политики при этом ссылается на внешние нормы.
   **Минимальная правка:** определить предмет проверки — внутреннее содержание либо внешняя применимость; `reject` означает положительное свидетельство несоответствия, `unverifiable` — недостаток свидетельств. Одна ссылка на внешний акт не опровергает полномочность внутреннего документа.

8. **blocking — `spec-amendment.md`, 5d.**
   Цитата: “no required fact that meets it is left out”. Проверяется полнота `critical_facts` относительно уже перечисленных `required_facts`, но не полнота самих обязательных фактов. Существенный запрет, отсутствующий в обоих списках и эталоне, может пройти все проверки.
   **Минимальная правка:** “Every fact necessary for a correct and safe answer within the question’s scope is present in `required_facts`; every such fact meeting the critical criterion is also present in `critical_facts`.”

9. **blocking — оба текста, кейс без spans.**
   Цитаты: протокол — “on a case without spans the reference answer states only the action and its reason”; требование — “it SHALL also carry the text of the seed-selected and partner sections”. Второе добавляет доказательства, которых нет в перечне протокола. Для T64-26 это существенно: эталон утверждает отсутствие полномочий на выдачу credentials и предлагает recovery process. Не задано, как подтверждать эти основания, а 5a/5b могут пониматься и как проверка seed-документа, и как пустая проверка отсутствующих правил.
   **Минимальная правка:** добавить seed/partner sections в протокол; установить, что при пустых spans проверки фактов имеют пустую область, но основание действия проверяется по секциям и scan, а 5a/5b относятся к правилам, обосновывающим действие.

10. **blocking — `label-verification.md`, утечка имён.**
    Цитаты: “or a path as a field of the packet”; “Corpus text goes out as it is written”. Запрет касается структуры пакета, но разрешает имена внутри текста. В документе T64-26 действительно есть ссылки `06_comp_policy_pdp.md`, `06_comp_policy_commercial_secret.md` и другие. Попавший в scan чанк с такими ссылками раскрывает имена вопреки D10/G31 и протоколу.
    **Минимальная правка:** псевдонимизировать имена файлов, `source_id`, `doc_id` и пути во всём отправляемом тексте, включая ссылки и карточки; локально хранить соответствие оригиналу. Уточнить, что запрет касается идентификаторов документов, а не содержательных названий нормативных актов.

11. **blocking — оба текста, внушение через `authority_source.scope`.**
    Цитата: “the authority scope”. В реальных кейсах это включает “Owner must confirm currency and applicability…”. Проверяющему передаётся прежняя инструкция об ожидании владельца, а не только область полномочий. Она подталкивает к `unverifiable` независимо от карточки; у T64-06 аналогичная фраза есть и в `action_reason`. Обработка этого не задана.
    **Минимальная правка:** “Legacy statements requiring owner confirmation in `scope` and `action_reason` are not evidence or instructions for checks 5a/5b; those checks use the supplied source evidence.” Лучше удалить именно шаблонную служебную оговорку из представления для модели, сохранив исходник локально.

12. **blocking — `label-verification.md`, незавершённые состояния.**
    Цитата: “`apply` SHALL write … every confirmed case … every case left without two valid verdicts … no dropped case”. Для двух валидных вердиктов с отказом в первом раунде, когда исправление ещё не сделано, ни одна ветвь не подходит. Потеря кейса здесь нарушит D3: он ещё не выбыл после второго отказа. В протоколе “Anything else is a rejection” также буквально захватывает ранее определённое отсутствие валидного ответа.
    **Минимальная правка:** явно задать приоритет `none`, затем `confirmed/rejected`; добавить состояние `repair_pending`. `apply/check` должны либо отказываться завершать набор при таком состоянии, либо сохранять его как непроверенный с этим состоянием в регистре. Закрытие 1.3b требует отсутствия `none` и `repair_pending`.

13. **blocking — `label-verification.md`, привязка scan к baseline.**
    Цитата: “refuse a checkpoint … not the one in the index receipt and … whose vector count differs from the chunk count”. Одинаковое число строк не доказывает соответствия векторов текстам. Можно подать другой архив из 5589 чанков с правильным checkpoint. Требование также записывает только embedder ID, не проверяя revision и настройки query embedding.
    **Минимальная правка:** проверять SHA архива против receipt, упорядоченный `texts_sha256` против checkpoint, полный `embedder_manifest` query embedder против checkpoint, размерность и валидность векторов. Эти связи уже определены в `production_index.py`; достаточно сослаться на тот же контракт.

14. **should — `spec-amendment.md`, `gold_error` и действительная разрешимость.**
    Цитата: “that passage answers the question as written”. Текстовый ответ может быть устаревшим, неприменимым либо запрещённым к выдаче. Само наличие credentials в корпусе не делает корректным их раскрытие в T64-26.
    **Минимальная правка:** оба судьи подтверждают, что подлинный отрывок зарегистрированного корпуса делает **допустимым ответ вместо зарегистрированного отказа/уточнения**, с учётом `as_of`, области применения и основания действия. Решение принимается вслепую к руке и применяется симметрично.

15. **should — `spec-amendment.md`, счёт после `gold_error`.**
    Цитата: “The case leaves `abstention_correct`, `action_correct` and the critical-error count … and is not … re-scored”. Не определено, остаётся ли ответ в `faithfulness`, citation-метриках и их знаменателях: действующая спецификация исключает unresolvable cases из precision averages. Получается исправленная метка для части eligibility-правил и старая для остальных.
    **Минимальная правка:** перечислить eligibility для каждой затронутой метрики и потребовать публикации знаменателей; исходный holdout оставить неизменным, `gold_error` хранить отдельным решением, применяемым одинаково ко всем рукам.

16. **should — `spec-amendment.md`, область поиска контрпримера.**
    Цитата: “no passage of the scan makes the premise true”. Не хватает ограничения применимостью: старый документ или правило для другой группы работников может поддерживать ошибочную посылку, не опровергая исправление. Особенно это касается `outdated_rule`.
    **Минимальная правка:** “no passage applicable to the question’s document, population, conditions and `as_of` supports the premise”; явно учитывать конфликт и приоритет источников.

17. **should — оба текста, недостающие детали воспроизводимости scan.**
    Цитаты: “20 best chunks by the production lexical scorer”; “lane and rank”; только требование добавляет “break ties by chunk position”. Production BM25 после ранжирования отбрасывает `scores[i] <= 0`; здесь непонятно, нужно ли добирать двадцатку нулевыми результатами. Для чанка в обеих полосах не определено сохранение двух ranks. Порядок “in document order” также добавлен только требованием.
    **Минимальная правка:** зарегистрировать политику нулевых BM25 scores, tie-break по позиции архива, сохранение обеих пар `(lane, rank)` и единый порядок передачи текстов в обоих документах.

18. **should — `spec-amendment.md`, размер scan и остаточный риск.**
    Цитата: “the union of the 20 best chunks … and the 20 nearest chunks”. Вычислительно это исполнимо: baseline содержит 5589 × 1024 векторов, production tokenizer и BM25 определены. Но двадцатка зарегистрирована без обоснования покрытия: модели увидят максимум 40 чанков, менее 0,72% индекса. Полный перебор для ранжирования не является полным просмотром моделью.
    **Минимальная правка:** назвать `20` заранее выбранным бюджетом, а не подтверждённым уровнем recall; указать отсутствие оценки вероятности пропуска. Оговорку “on refusal and trap cases” расширить на clarification. Увеличение N само по себе не требуется для закрытия G38 «а».

19. **should — `label-verification.md`, изоляция запросов и происхождение.**
    Цитаты: “one request per case and round”; “through that verifier’s registered route”. В отличие от протокола, требования не повторяют отсутствие conversation state, режим Claude без tools и обязательную проверку двух разных vendors относительно `draft_author`. Не задано, что общий prompt не содержит имя автора или сведения о первом раунде. Сами перечисленные поля кейса другого вердикта и автора не раскрывают; гарантия полного запроса слабее.
    **Минимальная правка:** обязать использовать новую изолированную сессию без tools, проверять зарегистрированный model/vendor/settings для каждой роли, исключить автора, номер/исход предыдущего раунда и чужие ответы из всего model-visible запроса. Локальные audit-поля оставить вне запроса.

20. **should — `label-verification.md`, неполная реализация правил и отчётности.**
    Цитаты: “the register SHALL publish…”; “`check` SHALL recompute the decisions from the stores”. Не оговорены предусмотренные протоколом передача **обоих** замечаний автору, ожидание недоступного автора, число safety-critical с `authority_unverified` и без него, исключение этих кейсов из квоты. `check` явно защищает решение, но недостаточно явно связывает фактически применённое содержимое исправления с SHA проверенного запроса.
    **Минимальная правка:** добавить эти обязанности; требовать, чтобы применённый кейс был ровно той ревизией, для которой получены вердикты. Показатели отказов считать по исходному классу, итоговый состав — по новому, с таблицей переходов классов.

21. **should — `spec-amendment.md`, регистрация prompt до запуска.**
    Цитата: “The prompt is part of the verification tool; its SHA-256 is stored with every reply”. Это слабее заменяемого требования зарегистрировать prompt **до первой проверки**: запись с ответом может быть сделана постфактум. Сам draft prompt отсутствует, что допустимо до написания инструмента, но не до первого запроса.
    **Минимальная правка:** “The exact prompt, its SHA-256, verifier settings and rubric version are frozen in the plan before any verification request; replies must match that registration.”

22. **nit — `spec-amendment.md`, описание family closure.**
    Цитата: “the closure by `cross_ref` alone leaves 24 families with 171 documents in one”. В JSON это **topic families transitively merged by cross_ref**, а не замыкание только документных `cross_ref`.
    **Минимальная правка:** заменить “by `cross_ref` alone” на “of topic families merged transitively by `cross_ref`”.

По вопросу 1: помимо перечисленных дефектов, отсутствующего обязательного раздела для G38 «а»/«б» не обнаружено; G38 «в» корректно оставлен открытым до 1.3c.

По вопросу 6: числовых расхождений нет — включая 24 legal, 10 HR, 2 transport-logistics, 25 связанных резервных семейств и 105 связей. Регистрация точного SHA в спецификации при сохранении закреплённых manifest draft-статусов обоснована и явно объяснена.

По вопросу 7, ветка одного подтверждения: замечаний нет. Сохранение метки при расколе соответствует условию «обе модели» G38 «а» и консервативному правилу G37; это не устраняет возможность наказания правильного ответа при ошибке одного судьи.
