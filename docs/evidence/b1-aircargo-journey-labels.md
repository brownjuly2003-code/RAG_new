# B.1 — Journey labels on the 100 air-cargo cases

**Slice:** phase B.1 of [`plan_23_08_2026.md`](../../archive/docs/plans/plan-2026-08-23.md) ·
**Evidence class:** `agent_labelled` · **Date:** 2026-08-25

## What was asked

The brief's phase 0 (`D:\New_steps\rag.md`) asks for one thing before any
further release machinery: *label the existing 100 air-cargo cases by
journey, outcome and root cause*, and verify that "100% of cases have a
journey/outcome or an explicit out-of-scope". Audit finding FIN-13 says the
same in one line: the repository holds 100 air-cargo cases and 17 synthetic
resolution scenarios, and nothing joins them.

## What a label says

A label is a claim about the **request**, not about the implementation, so it
stays true when the kernel changes. It lives inline on each case in
`evaluation/curated_cases_aircargo.jsonl` under `label`, and
`evaluation/aircargo_labels.py` is what makes it checkable:

| Field | Meaning |
|---|---|
| `journey` | which of the three contracts of brief §4.4 would own the request, or `out_of_scope` when none would |
| `expected_terminal` | the outcome a correct product should reach for the request **as written**, in the kernel's own `TerminalOutcome` vocabulary |
| `root_cause` | what stops the resolution kernel from reaching that outcome today |
| `binds_shipment` | whether the request names a shipment a journey could run against |
| `confidence` | how firm the proposal is, so review starts where it is weakest |
| `labelled_by` / `approved_by` | who proposed, who approved — these two decide `evidence_class`, which is derived and never stored as a claim |

The journey rule, applied to every case: a request belongs to `customs_docs`
when it asks what documents or data a shipment needs against the applicable
policy; to `exception_escalation` when it asks how an exception on a shipment
is routed to a human with an evidence brief; to `shipment_status` when it
needs the current state of a shipment or its ground leg; and to
`out_of_scope` when no contract would own it — HR, employment, privacy,
corporate contracts and domain definitions all land here.

## The numbers

| | |
|---|---|
| Cases labelled | **100 / 100** |
| Belong to a kernel journey | **34** — 17 `exception_escalation`, 11 `customs_docs`, 6 `shipment_status` |
| `out_of_scope` | **66** |
| **Bind a shipment** | **0** |
| `expected_terminal = verified` | **100** |
| `real_labelled` | **0** — no batch approved yet |
| Confidence | 77 high · 21 medium · 2 low |

## What the labelling found

**1. Not one case starts a journey.** All 100 name no shipment, so
`root_cause` is `no_shipment_binding` for the 34 in-journey cases and
`no_contract_for_intent` for the other 66. Nothing in this corpus can reach an
observation, a policy decision or a claim — which means it cannot produce a
verified-resolution number, a VRY, or a `pass^k`, no matter how the kernel
improves. B.3 of the plan ("first real numbers on the 100 labelled cases")
cannot be run against this corpus as it stands.

This is the brief's own NO-GO check firing: *"NO-GO / пересмотр, если … 100
cases не отражают реальные обращения"* (§15). They do not. They are questions
**about** air-cargo work, not requests **inside** it.

**2. The corpus exercises no safety path.** `expected_terminal` is `verified`
for 100 out of 100: every case is a knowledge question with a
document-grounded answer. Not one has a correct outcome of clarification,
escalation, or refusal. A uniform column is a weak label — and here it is
evidence: this corpus cannot measure the escalation, disclosure-policy or
refusal behaviour that the kernel exists to guarantee.

**3. The cases are agent-authored; only the documents are real.** The 201
source documents were copied from a real corpus into the `aircargo` tenant on
2026-05-30, and the questions over them were written by an agent
(`325d63c`, `6b7417d`, `32e841f`) — not sampled from support traffic. The
audit's shorthand "100 real air-cargo cases" is looser than the provenance
supports. So an approval by the domain-owner proxy makes **the labelling**
real, not **the cases**; the manifest records this as
`case_source: agent_authored_over_real_documents`, and no artefact here may
be read as 100 real labelled cases.

## What phase B needs next

Labelling was the cheap half and it is done. The expensive half is unchanged
and now precisely stated: **phase B needs cases that bind a shipment.** Two
routes, and only the first produces `real_labelled`:

1. **Real requests** — 100 support requests that named a shipment, from a
   domain owner (Q2). Each is labelled and approved the same way.
2. **Explicitly synthetic instances** against the fixture TMS — cheap, but it
   is what the repository already has 17 of, and adding more does not move
   FIN-02.

Until one of those exists, the honest phase-B number is the one above:
0 cases that a resolution journey can run.

## How a reviewer approves a batch

Twenty cases at a time, in the order below. The tool is the only supported
way to record an approval, so the dataset, the manifest digest and the
`real_labelled` count cannot drift apart:

```bash
python scripts/aircargo_labels.py report --batch 1      # the table below
python scripts/aircargo_labels.py approve --batch 1 --approver julia
python scripts/aircargo_labels.py verify                # the gate
```

To dispute one row, change `label.journey` (and its `root_cause`, which the
loader will hold to the same claim) in the dataset, then re-run
`python scripts/aircargo_labels.py manifest`. The 2 `low` and 21 `medium`
confidence rows are where disagreement is expected — they carry a note saying
which way each could also read.

## Tests

`tests/test_aircargo_labels.py` — 13 tests. The three that matter: every
checked-in case carries a valid label; the manifest still describes the
dataset byte for byte; and `evidence_class` cannot be claimed by writing it
into the file — a label that says `real_labelled` without an approver is a
load error, not a stronger claim.

## Review batches

### Batch 1 — cases 1–20

| Case | Question | Journey | Terminal | Root cause | Conf. | Note |
|---|---|---|---|---|---|---|
| `aircargo-probation-data` | Какие данные нужны для ответа по испытательному сроку? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-probation-extend` | Можно ли продлить испытательный срок сотруднику? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-probation-dismissal` | Что важно для увольнения по результатам испытательного срока? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-dismissal-check` | Что проверить перед ответом об увольнении работника? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-dismissal-lawyer` | В каких случаях при увольнении нужен юрист? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-dismissal-order` | Может ли ассистент подготовить приказ об увольнении? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-leave-sources` | Какие источники проверять перед ответом по отпуску? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-leave-compensation` | Может ли ассистент рассчитать компенсацию за отпуск? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-leave-risk` | Что считать рисковым кейсом по отпуску? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-matliab-check` | Что проверить по материальной ответственности работника? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-matliab-disputed` | Когда полная материальная ответственность работника спорна? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-templates-choose` | Как выбрать подходящий шаблон договора? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-templates-checklist` | Что обязательно проверить в договоре перед согласованием? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-templates-insufficient` | Когда стандартного шаблона договора недостаточно? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-secret-check` | Что проверять по режиму коммерческой тайны? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-secret-not-auto` | Когда сведения не стоит автоматически считать коммерческой тайной? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-secret-disclosure` | Что делать при разглашении коммерческой тайны? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-pdp-scope` | Какие вопросы относятся к персональным данным? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-pdp-data` | Какие данные нужны для ответа по защите персональных данных? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-pdp-uncertain` | Когда по персональным данным нельзя давать уверенный ответ? | out_of_scope | verified | no_contract_for_intent | high | — |

### Batch 2 — cases 21–40

| Case | Question | Journey | Terminal | Root cause | Conf. | Note |
|---|---|---|---|---|---|---|
| `aircargo-claims-delay` | Клиент требует компенсацию за задержку грузового рейса — что нужно для первичного ответа? | exception_escalation | verified | no_shipment_binding | high | — |
| `aircargo-claims-damage` | Груз пришёл с повреждением упаковки — какие доказательства запросить? | exception_escalation | verified | no_shipment_binding | high | — |
| `aircargo-claims-lawyer` | Когда по претензии нужно подключать юриста или compliance? | exception_escalation | verified | no_shipment_binding | high | — |
| `aircargo-claims-forbidden` | Что нельзя делать ассистенту при работе с претензией? | exception_escalation | verified | no_shipment_binding | medium | A rule of the escalation journey rather than a request inside it. |
| `aircargo-expedition-vs-carrier` | Чем экспедитор в авиагрузе отличается от авиаперевозчика? | out_of_scope | verified | no_contract_for_intent | medium | Air-cargo domain knowledge; no journey resolves a definition. |
| `aircargo-expedition-mawb-hawb` | Клиент путает MAWB и HAWB — какие факты нужны для ответа? | shipment_status | verified | no_shipment_binding | medium | Clearing up MAWB vs HAWB for a customer reads the shipment's own waybill records. |
| `aircargo-expedition-risks` | Где основные риски в ответе по авиаэкспедиции? | out_of_scope | verified | no_contract_for_intent | medium | A question about answering safely, not about a shipment. |
| `aircargo-road-cutoff` | Машина идёт на терминал как road feeder service — что проверить до cut-off? | shipment_status | verified | no_shipment_binding | medium | Pre-cut-off readiness of the road feeder leg is shipment state; its document half is customs_docs. |
| `aircargo-road-penalty` | GPS показывает опоздание, но рейс ещё не закрыт — можно сразу обещать клиенту штраф? | shipment_status | verified | no_shipment_binding | high | — |
| `aircargo-road-seal` | Пломба на машине не совпала с terminal record — какие источники нужны? | exception_escalation | verified | no_shipment_binding | medium | A seal against terminal record is a discrepancy; the ask is which sources establish it. |
| `aircargo-road-driver-pdn` | Клиент просит паспорт водителя и телефон для пропуска — что безопасно ответить? | shipment_status | verified | no_shipment_binding | medium | A disclosure request about a shipment's ground leg; journey 1 owns the policy check. |
| `aircargo-business-trip-advance-report` | Какие документы сотрудник должен сдать после командировки? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-business-trip-foreign-approval` | Кто согласует командировку сотрудника за пределы РФ? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-remote-work-monitoring-limits` | Что запрещено контролировать у удаленного сотрудника? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-remote-work-equipment-compensation` | Что компания предоставляет удаленному сотруднику и какую компенсацию интернета допускает? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-maternity-duration-normal` | Сколько длится отпуск по беременности и родам при нормальных родах? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-maternity-dismissal-ban` | Можно ли уволить беременную сотрудницу по инициативе работодателя? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-internal-transfer-consent` | Когда при внутреннем переводе нужно письменное согласие работника? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-internal-transfer-documents` | Какие документы HR готовит при переводе сотрудника? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-contract-termination-open-awb` | Что проверить перед расторжением air cargo договора, если есть открытые отправки? | out_of_scope | verified | no_contract_for_intent | medium | Needs shipment state to answer, but no journey owns contract termination. |

### Batch 3 — cases 41–60

| Case | Question | Journey | Terminal | Root cause | Conf. | Note |
|---|---|---|---|---|---|---|
| `aircargo-contract-termination-fields` | Какие поля обязательны в чеклисте расторжения договора? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-road-contract-aircargo-fields` | Какие авиационные параметры нужны в договоре автоперевозки груза? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-dangerous-goods-fields` | Какие поля нужны для допуска dangerous goods к air cargo рейсу? | customs_docs | verified | no_shipment_binding | high | — |
| `aircargo-dangerous-goods-clearance` | На что опираться при проверке опасного груза перед авиарейсом? | customs_docs | verified | no_shipment_binding | high | — |
| `aircargo-customs-clearance-fields` | Какие данные нужны для таможенного оформления авиагруза? | customs_docs | verified | no_shipment_binding | high | — |
| `aircargo-customs-special-cargo-manual-check` | Когда таможенный кейс нужно отправить на ручную проверку? | exception_escalation | verified | no_shipment_binding | medium | Manual check is the handoff; the completeness check before it is customs_docs. |
| `aircargo-waybill-first-mile-fields` | Какие поля нужны в путевом листе для airport first mile? | customs_docs | verified | no_shipment_binding | high | — |
| `aircargo-waybill-escalation-events` | Какие события по путевому листу требуют эскалации в юридический отдел? | exception_escalation | verified | no_shipment_binding | high | — |
| `aircargo-trade-compliance-hold` | Когда нельзя снимать compliance hold по авиагрузовой отправке? | exception_escalation | verified | no_shipment_binding | medium | Releasing a compliance hold is a human decision on a blocked shipment. |
| `aircargo-trade-compliance-screening` | Что фиксирует Compliance Officer при санкционном скрининге маршрута? | customs_docs | verified | no_shipment_binding | medium | Sanctions screening is a completeness-and-policy record on the route, not an exception. |
| `aircargo-incident-response-bridge` | Кто участвует в incident bridge при утечке AWB или booking data? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-incident-response-required-fields` | Какие поля обязательны в плане реагирования на инцидент ИБ? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-access-control-need-to-know` | На каком принципе строится доступ к AWB и customer data? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-access-control-review` | Какие поля нужны для пересмотра матрицы доступа? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-employment-contract-essential-terms` | Какие существенные условия нужно проверить в трудовом договоре? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-employment-contract-special-form` | Когда базового шаблона трудового договора недостаточно? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-driver-job-documents` | Какие документы оформляет водитель-экспедитор перед рейсом? | customs_docs | verified | no_shipment_binding | medium | Tagged HR, but the ask is the transport document set a driver carries for a leg. |
| `aircargo-driver-dangerous-goods-refusal` | Может ли водитель отказаться от опасного груза без обучения и допуска? | out_of_scope | verified | no_contract_for_intent | medium | A labour-law question about the driver, not about accepting the shipment. |
| `aircargo-sick-leave-required-fields` | Какие поля обязательны при оформлении больничного? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-sick-leave-lawyer-escalation` | Когда по больничному нужно подключать юриста? | out_of_scope | verified | no_contract_for_intent | high | — |

### Batch 4 — cases 61–80

| Case | Question | Journey | Terminal | Root cause | Conf. | Note |
|---|---|---|---|---|---|---|
| `aircargo-cargo-loss-evidence-bundle` | Какие доказательства нужны по претензии об утрате или недостаче груза? | exception_escalation | verified | no_shipment_binding | high | — |
| `aircargo-cargo-loss-required-fields` | Какие поля нужны в претензии авиаперевозчику об утрате груза? | exception_escalation | verified | no_shipment_binding | high | — |
| `aircargo-late-delivery-reply-evidence` | На какие доказательства опираться при ответе на претензию о задержке рейса? | exception_escalation | verified | no_shipment_binding | high | — |
| `aircargo-late-delivery-reply-no-admission` | Что нельзя признавать в ответе на delay или offload claim? | exception_escalation | verified | no_shipment_binding | high | — |
| `aircargo-driver-hours-required-fields` | Какие поля нужны для контроля режима водителя airport first mile? | out_of_scope | verified | no_contract_for_intent | medium | Driver-hours compliance is a fleet obligation; no shipment journey resolves it. |
| `aircargo-driver-hours-terminal-discrepancy` | Как фиксировать расхождения по flight number, пломбам или customs status? | exception_escalation | verified | no_shipment_binding | high | — |
| `aircargo-warehouse-3pl-required-fields` | Какие поля нужны в договоре с 3PL-оператором авиагрузового склада? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-warehouse-3pl-escalation` | Когда договор с 3PL-складом нужно эскалировать в юридический отдел? | out_of_scope | verified | no_contract_for_intent | medium | Escalation of a warehouse contract to Legal, not of a shipment exception. |
| `aircargo-perishable-temperature-controls` | Что проверить по perishables или pharma/cold chain перед air cargo перевозкой? | customs_docs | verified | no_shipment_binding | high | — |
| `aircargo-perishable-special-cargo-evidence` | Какие источники нужны для проверки температурного груза? | customs_docs | verified | no_shipment_binding | high | — |
| `aircargo-oversized-permit-route` | Какие параметры нужны для oversized cargo воздушным транспортом? | customs_docs | verified | no_shipment_binding | high | — |
| `aircargo-oversized-manual-check` | Когда oversized cargo уходит на ручную проверку? | exception_escalation | verified | no_shipment_binding | medium | Manual check is the handoff; the parameters that trigger it are customs_docs. |
| `aircargo-data-retention-legal-hold` | Когда нельзя удалять рейсовые документы по retention policy? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-data-retention-required-fields` | Какие поля нужны для политики сроков хранения данных? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-subject-rights-third-party-masking` | Как отвечать на запрос субъекта ПДн без раскрытия чужих данных? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-subject-rights-required-fields` | Какие поля нужны для ответа на запрос субъекта ПДн по AWB или booking? | out_of_scope | verified | no_contract_for_intent | medium | Touches AWB and booking data, but the resolving process is privacy, not a shipment journey. |
| `aircargo-customs-broker-evidence` | Какие документы нужны для договора с таможенным брокером по air cargo shipment? | out_of_scope | verified | no_contract_for_intent | low | Reads either way: documents for the broker contract, or the customs document set for a shipment. |
| `aircargo-customs-broker-escalation` | Какие события по таможенному брокеру требуют возврата к Legal и operations? | exception_escalation | verified | no_shipment_binding | medium | Events that hand a broker case back to Legal and operations. |
| `aircargo-salary-payment-dates` | Когда выплачиваются аванс и окончательный расчет по положению об оплате труда? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-salary-bonus-conditions` | При каких условиях выплачивается годовой бонус? | out_of_scope | verified | no_contract_for_intent | high | — |

### Batch 5 — cases 81–100

| Case | Question | Journey | Terminal | Root cause | Conf. | Note |
|---|---|---|---|---|---|---|
| `aircargo-overtime-limits` | Какие лимиты сверхурочной работы контролирует HR? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-overtime-protected-categories` | Кого нельзя привлекать к сверхурочной работе даже с согласия? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-harassment-complaint-data` | Что должна содержать жалоба по политике противодействия домогательствам? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-harassment-investigation-timeline` | В какие сроки назначается и проводится расследование по жалобе о домогательствах? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-conflict-interest-disclosure` | О каких фактах сотрудник обязан сообщить при конфликте интересов? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-conflict-interest-sanctions` | Какие последствия возможны за сокрытие конфликта интересов? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-cargo-insurance-evidence` | Какие доказательства нужны для страхования авиагруза? | out_of_scope | verified | no_contract_for_intent | low | Sits between the insurance contract and the shipment document set. |
| `aircargo-cargo-insurance-operational-limits` | Какие ограничения нужно проверить в договоре страхования грузов? | out_of_scope | verified | no_contract_for_intent | medium | Limits inside an insurance contract. |
| `aircargo-fuel-supply-evidence` | Какие evidence нужны по договору поставки топлива для cargo terminal? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-fuel-supply-required-fields` | Какие поля нужны в договоре поставки топлива для GSE? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-gps-monitoring-required-fields` | Какие поля нужны для GPS-мониторинга наземного плеча авиагруза? | shipment_status | verified | no_shipment_binding | high | — |
| `aircargo-gps-monitoring-scope` | До какого этапа логист сверяет GPS и документы наземного плеча? | shipment_status | verified | no_shipment_binding | high | — |
| `aircargo-weight-control-required-fields` | Какие поля нужны для взвешивания авиагруза и chargeable weight? | customs_docs | verified | no_shipment_binding | medium | Chargeable weight is a data-completeness item on the shipment record. |
| `aircargo-weight-control-discrepancy` | Что делать при расхождении по маршруту, грузу, весу или пломбам? | exception_escalation | verified | no_shipment_binding | high | — |
| `aircargo-cross-border-required-fields` | Какие поля нужны для международной авиагрузовой перевозки? | customs_docs | verified | no_shipment_binding | high | — |
| `aircargo-cross-border-special-cargo` | Какие типы special cargo уходят на ручную проверку в международной перевозке? | exception_escalation | verified | no_shipment_binding | medium | Which special cargo goes to manual check: the trigger list of a handoff. |
| `aircargo-breach-notification-required-fields` | Какие поля нужны для уведомления о нарушении ПДн в авиагрузовом процессе? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-breach-notification-participants` | Кто определяет уведомления и блокировки операций при утечке AWB или booking data? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-cross-border-pdn-required-fields` | Какие поля нужны для трансграничной передачи ПДн? | out_of_scope | verified | no_contract_for_intent | high | — |
| `aircargo-cross-border-pdn-no-transfer` | Когда трансграничная передача ПДн не выполняется? | out_of_scope | verified | no_contract_for_intent | high | — |
