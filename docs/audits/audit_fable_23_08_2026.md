# Аудит RAG_new — 23.08.2026 (Fable 5)

**Аудитор:** Claude Fable 5
**Дата:** 2026-08-23
**Репозиторий:** `D:\RAG_new`, ветка `master`, HEAD `26866e9` (2026-08-23 09:55 −04:00, «docs(session): clarify next-session handoff»)
**Worktree:** clean, кроме двух untracked файлов: `audit_sol_23_08_2026.md` (сегодняшний аудит другой модели) и этот файл
**Git remote:** отсутствует
**Точка форка:** `bd07179` = HEAD публичного `RAG_Support_Assistant` (GitHub `brownjuly2003-code/RAG_Support_Assistant`, запушен 2026-08-18)
**Предыдущие аудиты серии:** Grok 16.07, GPT 23.07 (активный для наследованного потока), Fable 11.06 (`fable_com.md`, ещё по RAG_Support_Assistant), sol 23.08 (независимо, тот же день)

---

## 0. Как читать этот документ

Это **не** второй инженерный аудит того же кода. `audit_sol_23_08_2026.md` уже сделал точную инженерную работу (split-brain ядра и рантайма, SSE fail-open, MyPy-scope, pricing Mistral). Я его прочитал **после** того, как сформировал свои выводы, и в §9 даю сверку. Мой документ отвечает на другой вопрос — тот, который поставлен в задании: **насколько проект актуален и что сделает его действительно сильным**, с учётом реальной операционной модели: один разработчик, работа через агентов (Codex/Claude), слабое Windows-железо + iMac 8 GB, отсутствие заказчика и domain owner, и контекст поиска работы.

**Что проверял лично:** git-история и статистика (907 коммитов, 32 после форка), статические импорты ядра, фокусный тест-гейт ядра (запускал), состав корня/доков, пины зависимостей, CI-конфиг, код `services/session.py` (полностью), стратегический бриф `D:\New_steps\rag.md` (полностью), архитектурные доки и handoff. **Не делал:** полный suite (1 878 тестов на слабой машине), live-вызовы LLM, запуск приложения, миграции на реальном Postgres.

**Исследования:** один opus-агент по рынку AI-support 2026 (48 обращений к веб-источникам) + мои собственные веб-проверки по технологическому SOTA. Ссылки в §11. Утверждения из исследований помечены как таковые; я перепроверил ключевую научную ссылку (arXiv 2607.07405) сам.

---

## 1. TL;DR

**RAG_new — это две вселенные и три незавершённых потока.** Первая вселенная — наследованный RAG-рантайм (FastAPI + LangGraph + Chroma), зрелый, с честной eval-культурой, но с открытым планом ремедиации (шаг 4.8d3e из 10). Вторая — новое детерминированное ядро «Verifiable Resolution OS» (`resolution/`, `knowledge/`, `actions/`, `services/session.py`, миграции 024–031): ~8,7 тыс. строк кода очень высокого качества, 198 зелёных тестов за 8 секунд, — и **ноль импортов из production-кода**. За три дня (21–23 августа) в проект добавлено +36 768 строк в 139 файлах, и **ни один из 32 коммитов не тронул `api/`, `agent/`, `static/` или `main.py`**. Пользователь `/api/ask` получает ровно тот же продукт, что 18 августа.

**Главный диагноз — инверсия критического пути.** Стратегический бриф (`D:\New_steps\rag.md`, 21.08) прямо требовал начать с Фазы 0: domain owner, разметка 100 air-cargo кейсов по journey/outcome, human baseline, утверждённые VR/VRY, — и объявлял **NO-GO без domain owner** («без owner это снова generic demo», строки 956, 972–981). Вместо этого построены Фазы 2–4 (контракты, ledger, симулятор, replay-манифесты, release-safety gate) на **синтетическом корпусе из 17 кейсов**; получившиеся метрики — VR precision `0/1 → 1/2`, VRY `0/17 → 1/17` — проект сам честно называет «constructed synthetic contract evidence, not measured performance». Это семь слоёв release-машинерии для journey, который ни разу не выполнился против реального запроса.

**Актуальность — три разных ответа:**
- **Механизм** (детерминированный гейт над LLM, evidence, replay) — актуален и подтверждён наукой: pre-execution gates дают +10–12 п.п. на τ²-bench, 78 % провалов агентов — «тихие» ошибки состояния (arXiv 2607.07405, июль 2026).
- **Рыночная дифференциация** — низкая: тот же питч уже продают Lorikeet, Sierra (supervisor), Decagon (AOP), Intercom Procedures, Rasa CALM, Zowie; логистическая вертикаль занята (Expedock, Vooma, Zowie/InPost 53 % автономных решений); EU AI Act для саппорта даёт только дисклеймер (Art. 50), Annex III перенесён на декабрь 2027. Коммерческий путь для соло-проекта без SOC 2 (6–12 мес., $40–120k) ≈ 0.
- **Ценность как инженерный/карьерный актив** — высокая, но **сейчас равна нулю, потому что проект невидим**: нет remote, нет CI, нет демо, README ведёт с продукта, которого нет.

**Оценка:** как поставляемая система — **5,4/10**; как инженерная база — **8/10**; как портфельный актив в текущем виде — **3/10**, потенциал **8,5/10** при публикации и одной сквозной нити.

**Рекомендация в одну строку:** остановить производство слайсов, за 1–2 дня запушить и заморозить, за 6–8 недель провести **одну реальную нить** (shipment-status shadow → evidence bundle в UI → честные VR/VRY на 100 реальных кейсах) и опубликовать проект как *доказательство инженерной зрелости*, а не как платформу. Детали — §8.

---

## 2. Что проект представляет собой фактически

### 2.1 Хронология

| Дата | Событие |
|---|---|
| 2026-03-02 | Первый коммит RAG_Support_Assistant |
| 2026-06-11 | Аудит Fable 8,7/10; hardening-сессии |
| 2026-07-23 | Аудит GPT 6,1/10 (3× P0), план `plan_sol_23_07_26` |
| 2026-08-03 | Ремедиация переоформлена в `rag-remediation-plan-2026-08-03.md` (10 шагов) |
| 2026-08-18 | `bd07179` запушен в GitHub; suite 1 870 passed / 7 skipped |
| 2026-08-21 | Бриф `rag.md` → клон в `D:\RAG_new`; Slice A/B (архитектура, схема контракта); 9 коммитов |
| 2026-08-22 | C1–C8, D, E1–E2, F, G1–G4; 14 коммитов |
| 2026-08-23 | G5–G8, REL-03A/B/C; 9 коммитов; два аудита |

Скорость — 32 коммита и +36,8 тыс. строк за три дня — означает, что практически весь код написан агентами по спекам. Это не претензия к качеству кода (см. §6), это претензия к тому, **на что** была потрачена скорость.

### 2.2 Три потока и их состояние

| Поток | Где описан | Состояние | Что подключено к пользователю |
|---|---|---|---|
| **Trust Foundation** (ремедиация наследованного рантайма) | `rag-remediation-plan-2026-08-03.md`, `BACKLOG.md:81-150` | шаг 4 из 10 «в процессе» (4.8d3e); live-гейты TEN-01/02, OPS-01, ING-01 открыты с июля; шаги 5–10 не начаты | это и есть текущий продукт |
| **Resolution Product** (ядро) | `rag-new-architecture.md`, `docs/architecture/migration-plan.md` | C1–C8, D, E1–E2, F, G1–G8 «locally complete»; Slice H (операторские поверхности и пилот) не начат | **ничего** — `run_legacy_ask_shadow` (`resolution/application/shipment_status.py:617`) не вызывается из `api/` |
| **REL-03 durable sessions** | ADR 0006, `BACKLOG.md:3-29`, `docs/SESSION_HANDOFF.md:30-101` | A/B/C сделаны; `SessionService` (`services/session.py:226`) готов | **ничего** — `/api/ask` и SSE «not wired» (`SESSION_HANDOFF.md:41`) |

Проверка импортов (моя): `grep -rlE 'from (resolution|knowledge|actions)|services\.session' api agent main.py services ingestion llm vectordb channels integrations` → **пусто**. 20 файлов импортируют ядро — все в `tests/`, `scripts/`, `evaluation/`.

### 2.3 Цифры

| Показатель | Значение | Источник |
|---|---:|---|
| Production-код (без tests/scripts) | ≈ 52 тыс. строк | подсчёт sol; мои per-dir: `agent` 7 640, `api` 9 113, `evaluation` 7 876, `vectordb` 4 292 |
| Новое ядро | `resolution` 3 331 + `knowledge` 1 548 + `actions` 2 459 + `services` 1 370 ≈ 8,7 тыс. + `evaluation/resolution/*` | `find … wc -l` |
| Тесты | 252 файла, 71 656 строк, 1 878 функций | `grep -rE 'def test_'` |
| Миграции ядра | `024`–`031` (8 новых, head `031`) | `alembic/versions` |
| Фокусный гейт ядра (мой запуск, 17 файлов) | **198 passed, 1 warning, 7,94 s** | `pytest -p no:schemathesis --basetemp=.tmp/pytest-audit` |
| Реальные датасеты | `curated_cases.jsonl` 76, `curated_cases_aircargo.jsonl` **100**, `phase0_labels` 135, `labelled_routes` **10** (human calibration) | `wc -l` |
| Синтетический корпус ядра | **17** кейсов, `evaluation/resolution/corpora/v0.1/shipment-status.json` | `rag-new-architecture.md:133-135` |
| Документы в корне | **43** `.md`, из них **29** процессных капсул (`c4-…`, `g1-…g8-…`, `durable-…`, `index-…`, `*-telemetry.md`) | `ls` |
| `AGENT_STATE.md` | 678 KB, **12 327 строк** | `wc -l` |
| `docs/SESSION_HANDOFF.md` | 2 969 строк | `wc -l` |
| Размер `.git` | 34 MB | `du` |

### 2.4 Качество RAG (последний живой замер, 18.07, 100 air-cargo кейсов)

| Метрика | Факт | Собственный release-floor проекта |
|---|---:|---:|
| Context precision | 0,5768 | ≥ 0,63 |
| Context recall | 0,980 | ≥ 0,97 ✅ |
| Keyword FULL/PART/MISS | 97/2/1 | FULL ≥ 97 ✅ |
| Judge faithfulness | 0,8406 | ≥ 0,90 |
| Answer relevancy | 0,890 | ≥ 0,92 |

Все 7 альтернативных retrieval-плеч получили NO-SHIP (precision покупалась потерей recall). Это важно: **потолок текущей связки retrieval достигнут**, и дальнейший прирост качества лежит не в retrieval (см. F-7).

---

## 3. Проверка заявлений документации

| Заявление | Где | Факт | Вердикт |
|---|---|---|---|
| «All production packages are `mypy --strict` clean (CI-enforced)» | `README.md:94` | `ci.yml:129-130`: scope = `auth db llm/providers config/settings.py agent/… tasks utils monitoring channels tracing ingestion evaluation` + `api vectordb`; **`resolution`, `actions`, `knowledge`, `services` отсутствуют**. Плюс remote отсутствует → CI для RAG_new **не запускался ни разу** | ❌ ложно дважды |
| «Independent Resolution gate: 158 passed» | `BACKLOG.md:57` | мой более широкий набор — 198 passed | ✅ подтверждено |
| «Slices C–G locally complete» | `rag-new-architecture.md:9-17` | код и тесты есть; «locally» = только в тестах | ✅ с оговоркой: locally ≠ product |
| «Full Slice G remains open… no next local G slice auto-selected» | там же, 137–140 | честно | ✅ |
| «primitives exist but sync `/api/ask` and SSE are not wired» | `SESSION_HANDOFF.md:41` | подтверждено grep | ✅ честно |
| Architecture acceptance checklist: «Domain owner confirms…», «Security/operations confirm…», «Product owner confirms VR/VRY…» | `migration-plan.md:406-408` | все три — `[ ]` не выполнены | ⚠️ это и есть непройденная Фаза 0 |
| GitHub Actions «runs on every push» | `README.md:439` | нет remote | ❌ для RAG_new |

Общий вывод: документация проекта **исключительно честна на уровне отдельных утверждений** («owner-unconfirmed», «synthetic-only», «deployment_authorized=false» повторяются десятки раз) и при этом **создаёт ложное ощущение прогресса на уровне целого**: 40 страниц «locally complete» при нулевом изменении продукта.

---

## 4. Актуальность

### 4.1 Концепция vs рынок августа 2026 (по данным рыночного исследования)

**Что подтвердилось.** Направление брифа «не продавать RAG, продавать доказуемое разрешение» — правильная реакция на рынок: «ответы по базе знаний» действительно товар. Per-resolution pricing стал публичным и низким: Intercom Fin **$0,99/resolution**, Zendesk $1,5–2,0, Decagon ≈ $0,5 (при медианном ACV $386k), Ada $1–3,5, Agentforce $0,10/action. Реальные resolution rates — **41–50 %** против 67–90 % в презентациях; счёт «клиент не позвал человека = resolved» завышает метрику на 20–40 п.п. То есть честный VR/VRY из брифа — правильная *метрическая* идея.

**Что не подтвердилось — дифференциация.** «LLM предлагает, детерминированный слой решает» в 2026 — **table stakes**, а не moat:
- **Lorikeet** продаёт ровно этот питч: per-ticket лог каждого действия, reasoning-шага, доступа к данным и guardrail-события, история версий конфигурации («какая версия policy/workflow дала это решение»), пошаговый replay, второй агент для 100 % QA; ~80 % клиентов — финансовые институты США (SEC 17a-4, FINRA, HIPAA).
- Sierra Agent OS — supervisor-слой, проверяющий вывод против scope/policy до ответа; Decagon AOP; **Intercom Procedures** — детерминированные шаги, code snippets с гарантией «same input → same output», approval checkpoints; Zowie — явное разделение «LLM ведёт разговор, rules engine ведёт бизнес-логику»; Rasa CALM — «business logic controls high-risk actions regardless of LLM output».
- Единственно редкие элементы проекта — **bitemporal-версионирование контрактов и криптографический ledger**. По исследованию, ни один покупатель не спрашивает их по имени.

**Регуляторный попутный ветер — слабее, чем в брифе.** 2 августа 2026 вступила в силу Art. 50 (дисклеймер «вы говорите с AI»). Обязательства Annex III по Digital Omnibus перенесены на **2 декабря 2027**, и саппорт в Annex III в общем случае не входит. Спрос на evidence-ledger реален (88 % предприятий имели инцидент с агентами за год, 33 % без audit trail — по опросам 2026), но **платят за него банки/финтех/здравоохранение**, а не air-cargo.

**Вертикаль занята.** Expedock Freya (email-классификация, track-and-trace, HS-коды, квоты), Vooma (freight brokers), Logixboard, Zowie/InPost (53 % чатов без человека, −30 % звонков в первый месяц, мультиязычно). IATA ONE Record — 30+ пилотов, >70 % AWB-объёмов. Остаточная ниша — multi-party irregularity resolution (AWB-расхождения, таможенные холды, claims), где evidence bundle действительно нужен, — но она требует доступа к данным форвардера/авиалинии, то есть design partner.

**Self-hosted OSS — переполнено:** Dify 138k★, Langflow ~100k, RAGFlow ~70k, AnythingLLM 64k, Chatwoot 32k (реальный helpdesk), Onyx у Netflix на 14 000 сотрудников. У сильных есть 40+ коннекторов, сертифицированные SSO/RBAC/audit, логотипы и контракт поддержки — то, что соло-проект не может воспроизвести.

**Коммерческая реальность для соло:** SOC 2 Type II — гейт, а не значок (6–12 мес., $40–120k), плюс DPA, pentest (~$8k/год), AI data-handling policy. Ниже — «Ada ушла *от* outcome-pricing к per-conversation, потому что покупатели хотели предсказуемость», то есть даже ставка на «платить за verified resolution» не самоочевидна.

**Вывод по 4.1:** концепция *актуальна как инженерный стандарт 2026* и *неактуальна как рыночная дифференциация*. Позиционировать её надо как «грамотную реализацию текущей best practice», а не как открытие.

### 4.2 Стек vs технологическое SOTA (мои веб-проверки + sol §9)

| Компонент | Сейчас | Состояние на 08.2026 | Решение |
|---|---|---|---|
| FastAPI / LangGraph / LangChain / Pydantic | 0.139 / 1.2.9 / 1.3.13 / 2.13 | свежие; LangGraph 1.x — обоснованный default с durable execution и крупнейшим enterprise-списком (Klarna, Uber, LinkedIn, JPMorgan) | **держать**, квартальный bounded refresh |
| Генерация: `qwen2.5:7b` (Sep 2024) | default local-first | **устарел**: Qwen3-8B ≈ Qwen2.5-14B по качеству, 119 языков vs 29 (важно для RU), tool calling/structured output заметно лучше; есть Qwen3.5/3.8-семейство | **бенчмарк на 100 кейсах, затем смена** — это главный рычаг faithfulness (§F-7) |
| Эмбеддинги BGE-M3, реранкер bge-reranker-v2-m3 | default | всё ещё «универсальный мультиязычный default» в обзорах 2026; для максимума — Qwen3-Embedding-8B / Qwen3-Reranker-4B/8B, но они тяжелее для CPU | **держать**; менять только по A/B |
| ChromaDB 1.5.9 + BM25 в памяти | default | Chroma фильтрует метаданные **после** ANN и over-fetch'ит, не имеет нативной multitenancy/шардинга; «~30 % прототипов стартуют на Chroma, остальные мигрируют на pgvector/Qdrant за ~2 дня»; pgvector с RLS — рекомендуемый default для B2B на десятки–сотни тенантов | **spike pgvector** (см. F-6) — не ради моды, а ради единой trust boundary с уже существующим RLS |
| RAGAS-style eval + 7 online heuristics | есть | RAGAS остаётся легитимной библиотекой метрик, но «сильные команды комбинируют metrics framework + observability (Langfuse self-host / Phoenix) + CI-гейт (DeepEval-style pytest assertions)»; для faithfulness в CI дешёвые чекеры HHEM-2.1 / MiniCheck / Lynx | **добавить** дешёвый NLI-чекер как второй judge (не LLM-судья самого себя) |
| Агентные бенчмарки | нет | τ²-bench / τ-Knowledge — стандарт для support-агентов (pass^k, state-comparison). Проект **уже реализует их методику** (pass^1/pass^3, state grading) — это сильная сторона, но на 17 синтетических кейсах | **прогнать на реальных 100** |
| MCP | не используется (ADR-решение) | текущая ревизия спеки 2026-07-28; правильно отложен | не трогать до journey |
| API-модели (если нужен облачный fallback) | Mistral | Haiku 4.5 $1/$5, GPT-5 mini $0,25/$2, Gemini 3.5 Flash $1,5/$9 за M токенов — типичный диалог саппорта стоит **центы**, что делает «$/verified resolution vs $0,99 Fin» реальным и выигрышным аргументом | посчитать и опубликовать |

**Вывод по 4.2:** фреймворки в порядке; **три реальных технологических долга** — модель генерации 2024 года, Chroma как несогласованная граница тенантов, отсутствие независимого дешёвого faithfulness-чекера. Ничего из этого не требует переписывания.

### 4.3 Актуальность для владельца (карьера / портфолио)

По данным о найме 2026: упоминания LLM-инженерии в DE-вакансиях выросли с 3 % до 12 % за квартал; «eval literacy — главный сигнал, что человек реально строил с LLM»; рекрутеры на 80 % чаще взаимодействуют с GitHub-проектами, у которых есть **запускаемый код или живое демо**.

Ранжирование сигналов этого проекта (по исследованию, и я согласен):
1. **Eval-дисциплина** — golden sets, NO-SHIP по данным, regression gates, LLM-judge + human calibration. Самый сильный и самый прямо называемый в JD.
2. **Оркестрация агентов** — LangGraph + tool calling + HITL + **idempotent action gateway с postconditions**. Idempotency/postconditions — редкость, «interview-ready».
3. **Cost engineering** — локальная 7B vs API, $/resolution с цифрами.
4. **Multi-tenant Postgres/RLS** — компетентно, ожидаемо, «читается как senior DE», не hook.
5. **Formal-verification-фрейминг** («Verifiable Resolution OS», SHA-256 манифесты, fail-closed gates над синтетикой) — **самый слабый для найма**: спроса в JD нет, стоит ясности на 6-секундном скрине.

Сейчас проект даёт **ноль** этих сигналов, потому что не опубликован, а публичный RAG_Support_Assistant не содержит ничего из нового ядра.

---

## 5. Findings

Приоритеты: **P0** — блокирует любую ценность проекта (продуктовую или карьерную); **P1** — должен быть закрыт до публикации/пилота; **P2** — планировать.

### F-1 — P0 (стратегический): инверсия критического пути и «evidence about evidence»

**Факты.** Бриф `rag.md` задаёт критический путь: *domain owner + measurable outcome → contract schema + labelled cases → read-only resolution + evidence ledger → simulator → governed action → shadow → canary* (строки 823–839) и Фазу 0 (714–728): три journey с owner, разметка 100 кейсов, human baseline, утверждённые VR/VRY. Таблица рисков (956): «Нет domain owner → остановить vertical build на фазе 0». GO/NO-GO после 30 дней (972–981) требует domain owner первым пунктом.

Фактическая последовательность: Slice A (доки) → B (схема) → C1–C8 (персистентность, RLS, immutability, restore-smoke, Mac-Postgres) → D (shadow на фикстурах) → E (temporal) → F (governed ticket) → **G1–G8 (grader, replay-manifest, trials, corpus, ledger, comparison, release-manifest, safety gate)** → REL-03A/B/C. `migration-plan.md:406-408`: все три owner-confirmation пункта — не выполнены. Синтетический корпус — 17 кейсов; реальные 100 air-cargo кейсов **не переразмечены** по journey/outcome/root-cause (Фаза 0, п. 3 брифа). Итоговые метрики G6: VR precision `0/1 → 1/2`, VRY `0/17 → 1/17` — числа без содержания, упакованные в canonical JSON + SHA-256 с «forged/stale references fail closed».

**Почему это P0.** Каждый слайс G2–G8 производит верификационные артефакты *о предыдущем слайсе*, а не о продукте: манифест, который пинит манифест, gate, который валидирует manifest gate'а. Это самоподдерживающаяся «экономика доказательств»: работа генерирует доказательства своей же корректности, что читается как прогресс, но не меняет ни один пользовательский результат и не приближает к первому реальному кейсу. Автопилотный формат («owner explicitly delegated route selection to Codex», `BACKLOG.md:5`) закрепляет это: агент всегда выберет следующий *локально доказуемый* слайс, а не слайс, требующий внешнего решения (owner, данные, remote).

**Что делать.** Заморозить потоки G и REL-03 (никаких G9/REL-03D). Дальнейшая работа принимается только если она меняет наблюдаемое поведение `/api/ask` или число реальных размеченных кейсов. Восстановить Фазу 0 в урезанном виде (§8, этап 2): Юлия сама выступает domain-owner-proxy для shipment-status, фиксирует postconditions и размечает 100 кейсов; source of truth — явно помеченная fixture-TMS.

### F-2 — P0 (операционный): единственная копия работы и мёртвый CI

**Факты.** `git remote -v` пуст; 32 коммита (+36,8 тыс. строк) существуют только на `D:\` слабого Windows-ноутбука; `.git` — 34 MB. `.github/workflows/ci.yml` (lint, unit, integration, migrations, Helm, Bandit, pip-audit) **никогда не выполнялся** для RAG_new; при этом `README.md:94, 439` заявляет CI-enforcement.

**Риск.** Потеря диска = потеря всей работы ядра. Все «green gate» заявления — локальные прогоны агентов без независимого воспроизведения.

**Что делать (день 1, 30 минут).** Создать private GitHub-репозиторий (или ветку `rag-new` в существующем `RAG_Support_Assistant`), `git push`, убедиться, что CI зелёный или честно красный; поправить README. Это самое дешёвое действие с самым высоким leverage во всём аудите.

### F-3 — P0: split-brain ядра и рантайма

Подтверждаю **F-01/F-02 из audit_sol** без повторения деталей: ядро и `SessionService` не владеют публичным запросом; `run_legacy_ask_shadow` (`resolution/application/shipment_status.py:617-663`) существует, но не зарегистрирован. Моё дополнение: это не отдельный дефект, а **следствие F-1** — wiring требует решений, которые агент не может принять «локально доказуемо» (изменение поведения legacy-пути, риск регрессии 1 870 тестов), поэтому автопилот его системно избегает. Лечится не «ещё одним слайсом REL-03D», а изменением правила приёмки (F-1).

### F-4 — P1: три параллельных незавершённых потока без WIP-лимита

Trust Foundation остановлен на 4.8d3e (шаги 5–10 не начаты; live P0-гейты открыты с 23.07), Resolution — на G8 («open beyond synthetic»), REL-03 — на C («D not started»). Каждый переключён «paused/override» решением в `BACKLOG.md:3-79`. Три частично готовых потока хуже одного готового: ни один не даёт demo, а стоимость удержания контекста трёх потоков в handoff-документах растёт нелинейно (F-5).

**Что делать.** WIP-лимит = 1 нить (§8). Остальные потоки — в `ROADMAP.md` как «заморожено, причина, условие разморозки».

### F-5 — P1: процессная нагрузка стала главной статьёй расходов

**Факты.** 43 `.md` в корне (29 процессных капсул); `AGENT_STATE.md` 12 327 строк; `SESSION_HANDOFF.md` 2 969 строк с блоками «Superseded — Update-238/237/236…»; правило онбординга «прочитать все `.md` в корне» — по глобальным инструкциям владельца — стоит каждой сессии десятки тысяч токенов *до* начала работы. Мой июньский finding F-16 (гигиена корня) был закрыт в `09a81ce` — и регрессировал полностью.

**Почему это важно именно здесь.** Дорогой онбординг + автопилот = смещение в сторону маленьких, локально верифицируемых слайсов (быстро прочитал handoff → сделал узкий слайс → написал ещё капсулу). Это механизм, воспроизводящий F-1.

**Что делать.** Три живых документа: `CURRENT_STATE.md` (≤ 150 строк, один экран истины), `ROADMAP.md`, `EVIDENCE_INDEX.md`; капсулы → `docs/evidence/<slice>/`; `AGENT_STATE.md` → `docs/archive/agent-state-2026-03..08.md` с 100-строчным дайджестом; правило «одна капсула на слайс» отменить — evidence живёт в тестах и в `EVIDENCE_INDEX.md` одной строкой. CI-проверка ссылок и размера живых документов.

### F-6 — P1: несогласованная граница тенантов (RLS в Postgres, retrieval в Chroma)

**Факты.** Ядро проекта продаёт «cross-tenant evidence/action access = 0» через forced RLS на новых таблицах (`025_resolution_tenant_rls.py`, `029`, `030`, `031`). Retrieval при этом живёт в ChromaDB (per-tenant коллекции `rag_docs_{tenant}`) + BM25-индекс в памяти процесса. По исследованию: Chroma применяет фильтры после ANN, не имеет нативной multitenancy/шардинга; pgvector с RLS даёт единую границу на той же БД для десятков–сотен тенантов; Qdrant фильтрует до обхода HNSW. Ревьюер, проверяющий заявление «verifiable isolation», найдёт эту дыру первой.

**Что делать.** Spike (≤ 3 дня, iMac/Colab): pgvector + Postgres FTS/RRF на 100-кейсовом корпусе, измерить recall/precision/латентность против Chroma+BM25 baseline. Решение оформить ADR: либо мигрировать (единая RLS-граница, минус один сервис, минус in-memory BM25 — закрывает мой июньский F-2), либо явно задокументировать инвариант «изоляция retrieval — application-level, не RLS».

### F-7 — P1: плато качества и неверный следующий рычаг

**Факты.** Faithfulness 0,84 (< 0,90), precision 0,58 (< 0,63) при recall 0,98 и семи NO-SHIP retrieval-экспериментах. Генератор — Qwen2.5-7B (сентябрь 2024). Верификация фактов — тем же классом модели. Вывод: retrieval выжат; **следующие рычаги — модель генерации и claim-level compilation** (бриф §6.4), плюс независимый дешёвый NLI-чекер (HHEM-2.1/MiniCheck) как второй судья.

**Что делать.** Бенчмарк Qwen3-8B (Q4) и одной Qwen3.5-класса модели против Qwen2.5-7B на 100 кейсах по существующему harness'у (`scripts/`); ожидаемый эффект — faithfulness ≥ 0,90 за счёт лучшего following контекста и 119-язычной поддержки. Если NO-SHIP — честно записать и оставить.

### F-8 — P2: данные — первопричина, а не следствие

100 реальных air-cargo кейсов не имеют разметки journey/outcome/root-cause; human-calibration set — **10** строк. Синтетический корпус ядра (17) не связан с реальными кейсами. Любые VR/VRY останутся «non-business-claimable» до тех пор, пока знаменатель — не реальные обращения. Это самая дешёвая работа с самой высокой отдачей после F-2: 100 кейсов × 3 поля размечаются за один день владельцем + агентом-ассистентом.

### F-9 — P2: ни один план не откалиброван под реальную capacity

Бриф: «3–4 инженера; для одного разработчика ×2–3 и сузить journey». Sol-план: «2–4 инженера + domain owner/security/ops; при одном — 16–20 недель». Реальность: 1 человек + агенты, без domain owner, без security/ops, железо без GPU. Планы с «1 000 contended attempts на 2 репликах», «SBOM/SLSA provenance», «NetworkPolicy/PDB» — enterprise-DoD без enterprise-заказчика. Нужен план для реальной модели (§8).

### F-10 — P2: расхождение заявленных и фактических gate-scope

Подтверждаю sol F-05 (MyPy scope `ci.yml:129-130` и coverage `pyproject.toml:40-…` не включают ядро; README врёт). Дополнение: пока нет remote, любая правка scope — тоже «locally verified». Чинить вместе с F-2.

---

## 6. Что сделано действительно хорошо

- **Качество кода ядра.** `services/session.py` (560 строк): advisory-lock на identity, `FOR UPDATE` на session и turn, DB-clock как authority, epoch-fencing, идемпотентный replay по digest, терминальные переходы без перезаписи, `set_config('app.current_tenant_id', …, true)` transaction-local. Это код, который не стыдно показать на собеседовании на senior backend/DE.
- **Честность утверждений.** Ни одно «locally complete» не выдаётся за release; синтетика помечена как синтетика. Это редко.
- **Eval-культура наследованного слоя.** 7× NO-SHIP по данным, judge-репорты, calibration artifacts, pass^k-методика — всё это соответствует лучшим практикам 2026 (τ²-bench-стиль state grading).
- **Скорость исполнения через агентов** — 36 тыс. строк с 198 зелёными тестами за 3 дня. Проблема не в двигателе, а в руле.
- **Архитектурные ADR** (0001–0006) с честной аргументацией «не делать заранее» (GraphRAG, OPA, graph DB, микросервисы).

---

## 7. Стратегический выбор режима

Проект может быть только одним из трёх; попытка быть всеми тремя и породила F-1/F-4.

| Режим | Что значит «сильный» | Что требуется | Реалистичность для соло в 2026 |
|---|---|---|---|
| **A. Продукт** | пилот у design partner, VR/VRY на реальном трафике, SOC 2-путь | domain owner с данными TMS, 6–12 мес. на комплаенс, $40–120k, GTM | низкая: вертикаль занята, гейты не обходятся |
| **B. Доказательство инженерной зрелости** (портфолио + OSS-артефакт) | одна сквозная нить, живое демо, честные числа, README-first, публичный репозиторий | 6–8 недель соло + агенты, ноль внешних зависимостей | высокая; совпадает с текущей целью владельца |
| **C. Исследовательская лаборатория** | публикация «Resolution Contract + evidence ledger + replay gate» как спецификации/библиотеки | статья/README-спека, минимальный reference impl | средняя; аудитория узкая, для найма слабо |

**Рекомендация: B**, с элементом C (извлечь `resolution-contracts` как отдельно читаемый пакет со схемой и фикстурами). Переход к A — только если появится design partner с реальными данными; тогда план sol §11 становится актуальным целиком.

---

## 8. План «как сделать проект действительно сильным» (режим B, 6–8 недель, соло + агенты)

### Определение «сильный» — пять проверяемых критериев

1. **Сквозная нить.** Незнакомый человек делает `docker compose up`, задаёт вопрос о статусе отправления и видит: ответ, evidence bundle (contract version, policy decision, источники с freshness, postcondition result), replay receipt. Один E2E-тест это доказывает.
2. **Честные числа на реальных данных.** VR precision / VRY / pass^3 посчитаны на 100 размеченных air-cargo кейсов, опубликованы вместе с legacy-baseline и таблицей расхождений.
3. **Качество выше собственных floors** (faithfulness ≥ 0,90, precision ≥ 0,63) **или** задокументированный NO-SHIP с причиной.
4. **Единая trust boundary** (pgvector+RLS) **или** явный ADR-инвариант.
5. **Видимость.** Публичный репозиторий, CI зелёный, README ведёт с eval-чисел и $/resolution, 3-минутное демо, один архитектурный документ ≤ 2 страниц.

### Этап 0 — Заморозка и публикация (дни 1–2)

- Private remote, push, CI-прогон; починить README-заявления (F-2, F-10).
- `git tag freeze-2026-08-23`. Объявить в `ROADMAP.md`: потоки G, REL-03, Trust Foundation 4.8d3f+ — **заморожены**, условия разморозки записаны.
- Гигиена доков по F-5: три живых файла, капсулы в `docs/evidence/`, `AGENT_STATE.md` в архив с дайджестом. Обновить правило онбординга: читать `CURRENT_STATE.md` + `ROADMAP.md`, остальное по ссылкам.
- **Гейт:** `git remote -v` непуст; CI статус известен; корень ≤ 8 `.md`.

### Этап 1 — Одна нить: shipment-status в shadow внутри `/api/ask` (недели 1–2)

- Минимальное wiring: в `api/routers/conversation.py` после получения legacy-ответа вызывать `run_legacy_ask_shadow` под feature-flag `RESOLUTION_SHADOW_JOURNEYS=shipment-status`; результат — в SQLite-trace и в Postgres evidence-таблицы (они уже есть, миграции 024–030).
- `SessionService.admit_turn/commit_turn` — обернуть sync `/api/ask` **без** ETag/If-Match/428-семантики и без 2-replica floor (это enterprise-DoD, F-9). Достаточно: один turn на сессию, идемпотентный replay, terminal commit.
- Admin/agent UI: вкладка «Evidence» на трейсе — contract version, policy decision, claims→sources, postcondition, replay receipt (JSON-экспорт кнопкой). Без редизайна.
- **Гейт:** E2E-тест `tests/integration/test_shipment_status_e2e.py` зелёный; legacy-ответ байт-в-байт не изменился (характеризационный тест); демо-сценарий записан.

### Этап 2 — Данные: восстановленная Фаза 0 (неделя 2–3, параллельно этапу 1)

- Разметить 100 air-cargo кейсов: `journey ∈ {shipment_status, customs_docs, exception_escalation, out_of_scope}`, `expected_terminal`, `root_cause`. Владелец — domain-owner-proxy; агент предлагает, владелец утверждает; фиксировать `labelled_by`.
- Fixture-TMS: детерминированное состояние отправлений для 100 кейсов (`resolution/adapters/shipment_status.py` уже фикстурный — расширить и явно пометить «fixture source of truth»).
- Прогнать ядро на 100 реальных кейсах через существующие G1–G5 механизмы → **первые не-синтетические VR precision / VRY / pass^3**. Опубликовать как есть, даже если плохо.
- Human-calibration set: 10 → ≥ 40 кейсов с double-annotation по faithfulness (владелец + агент, разногласия фиксировать).
- **Гейт:** `evaluation/resolution/corpora/v1.0/aircargo-100.json` с провенансом; отчёт сравнения legacy vs kernel по 100 кейсам.

### Этап 3 — Рычаг качества (недели 3–4)

- Бенчмарк генераторов на 100 кейсах: `qwen2.5:7b` vs `qwen3:8b` (Q4_K_M) vs одна Qwen3.5-класса; прогон на iMac/Colab по памяти владельца (тяжёлое — не на Windows). Метрики: faithfulness (LLM-judge **и** HHEM-2.1), precision, latency, RAM.
- Claim-level compilation (бриф §6.4): ответ = список material claims → каждому evidence ID → unsupported удаляется → текст. Это одновременно поднимает faithfulness и делает evidence bundle содержательным.
- **Гейт:** faithfulness ≥ 0,90 на 3 прогонах с CI, или задокументированный NO-SHIP.

### Этап 4 — Trust boundary (неделя 4–5)

- Spike pgvector + FTS/RRF (F-6) на том же корпусе; сравнить recall@k/precision/latency с Chroma+BM25.
- ADR 0007: мигрировать (тогда BM25 in-memory и `_chunks_cache` уходят — закрывается старый F-2/июнь) или задокументировать инвариант.
- **Гейт:** таблица чисел + ADR; никаких миграций «по моде».

### Этап 5 — Публичный артефакт (недели 5–6)

- README-first: (1) что это и для кого в 3 строках без слова «OS»; (2) **таблица чисел**: recall/precision/faithfulness до/после, VR precision/VRY на 100 кейсах, $/resolution локально vs API vs $0,99 Fin; (3) схема одной нити; (4) «как запустить за 5 минут»; (5) раздел «Design» с контрактами/ledger/replay — один экран; (6) честный «Limitations».
- 3-минутное демо (по правилам владельца: 2–3 hero shots × 12–15 с, product-метрики первыми, итоговая карточка отдельно).
- Вынести `resolution/contracts/` + JSON Schema + фикстуры в читаемый под-пакет с собственным README (элемент режима C).
- Обновить публичный `RAG_Support_Assistant` (ссылка/ветка) — чтобы найденное рекрутером вело сюда.
- **Гейт:** репозиторий публичный, CI зелёный, демо-ссылка в README, hero-страница (существующий `proof-pack`) ссылается на проект.

### Этап 6 — только при появлении design partner

Возврат к sol §11 (durable HTTP-семантика, SSE-projection, 2 реплики, SBOM/SLSA, restore drills, service accounts) и к Trust Foundation шагам 5–10. До этого — **не делать**.

### Стоп-лист (до конца этапа 5)

G9+, REL-03D «ради полноты», MCP-коннекторы, GraphRAG, смена vector DB без бенчмарка этапа 4, микросервисы/Kafka/OPA, новые каналы (voice/Telegram), новые дашборды, «ещё один параллельный runtime», любой слайс, не меняющий поведение `/api/ask` или число размеченных кейсов.

### Правило приёмки слайса (заменяет текущее)

Слайс принимается, если выполняется хотя бы одно: (а) изменилось наблюдаемое поведение `/api/ask`/UI и есть E2E-тест; (б) выросло число реальных размеченных кейсов; (в) изменилось опубликованное число качества с провенансом. «Locally complete» без (а)/(б)/(в) — не слайс, а подготовка.

---

## 9. Сверка с `audit_sol_23_08_2026.md`

| Тема | Sol | Fable | Комментарий |
|---|---|---|---|
| Split-brain ядра/рантайма (F-01/F-02) | P0 | P0 (мой F-3) | **согласен**; добавляю причинность через F-1 (автопилот избегает решений, требующих внешней авторизации) |
| SSE fail-open (F-03) | P0/P1 | не повторяю | согласен; в режиме B streaming остаётся выключенным, приоритет ниже |
| Release evidence узкое (F-04) | P1 | F-8 | согласен; уточняю: первопричина — неразмеченные 100 кейсов и 10 калибровочных |
| MyPy/coverage scope, README (F-05) | P1 | F-10 | согласен; добавляю, что CI вообще не запускался (нет remote) |
| Auth/JWT/service accounts (F-06) | P1 | не оцениваю | вероятно верно; в режиме B — этап 6 |
| Mistral pricing ×4 (F-07) | P1 | не проверял | принимаю на веру sol; дёшево починить, но не приоритет |
| Chroma/масштаб (F-08) | P1/P2 «измерить» | F-6, P1 «spike pgvector» | **расхожусь в акценте**: для sol это масштаб, для меня — целостность заявления об изоляции |
| Helm/SBOM/SLSA (F-09) | P1 | этап 6 | **не согласен с приоритетом** для соло без заказчика |
| Доки-как-система (F-10) | P2 | F-5, **P1** | **поднимаю приоритет**: это механизм, воспроизводящий F-1 |
| План 90 дней на 2–4 инженера | основной | заменён планом §8 на 6–8 недель соло | **главное расхождение**: sol планирует enterprise-DoD (1 000 attempts/2 replicas/SOC-подобные гейты); я считаю это преждевременным без design partner |
| Рыночная дифференциация «9,0/10» | высоко | **≈4/10** | **не согласен**: исследование показывает table stakes (Lorikeet, Sierra, Intercom Procedures, Rasa) и занятую вертикаль |
| Итоговая оценка | 5,8 / потенциал 8,5 | 5,4 / инженерная база 8 / портфолио 3 → 8,5 | сопоставимо; различие — в том, *что* считать потенциалом |

Итог сверки: инженерные findings sol — принимаю почти полностью; **план и оценку дифференциации — нет**, потому что они рассчитаны на команду и рынок, которых у проекта нет.

---

## 10. Оценка

| Направление | Оценка | Обоснование |
|---|---:|---|
| Качество кода и тестов ядра | 8,5 | `session.py`, RLS-миграции, 198 зелёных за 8 с |
| Актуальность механизма (детерминированный гейт, evidence, replay) | 8,0 | подтверждено arXiv 2607.07405, τ²-bench-методика |
| Рыночная дифференциация концепции | 4,0 | table stakes; вертикаль занята; регуляторика не помогает |
| Runtime-интеграция ядра | 3,0 | 0 production-импортов |
| Данные и evidence на реальных кейсах | 3,0 | 17 синтетических; 100 реальных не размечены; 10 калибровочных |
| Качество RAG (наследованный слой) | 6,0 | recall 0,98, но faithfulness/precision ниже floors; плато |
| Операционная устойчивость проекта | 2,0 | нет remote/бэкапа/CI |
| Процесс и поддерживаемость | 3,5 | 43 md в корне, 12 тыс. строк state-лога, 3 потока |
| **Как поставляемая система** | **5,4** | |
| **Как инженерная база** | **8,0** | |
| **Как портфельный актив сейчас / после §8** | **3,0 / 8,5** | |

---

## 11. Приложение

### 11.1 Выполненные проверки

| Проверка | Команда/метод | Результат |
|---|---|---|
| Git | `git log`, `git remote -v`, `git log bd07179..HEAD` | 907 коммитов; remote пуст; 32 коммита с форка; 0 в `api agent static templates main.py`; +36 768/−48 строк, 139 файлов; даты 21/22/23.08 = 9/14/9 |
| Импорты ядра | `grep -rlE` по production-пакетам | 0 файлов; 20 в tests/scripts/evaluation |
| Тест-гейт ядра | `python -m pytest <17 файлов> -q -p no:schemathesis --basetemp=.tmp/pytest-audit` (Python 3.13.7) | **198 passed, 1 warning, 7.94 s** |
| CI scope | `grep -n mypy .github/workflows/ci.yml` | строки 129–130: ядро не в scope |
| Корпуса | `wc -l evaluation/*.jsonl …` | 76 / 100 / 135 / 10; синтетика 17 |
| Корень | `ls *.md` | 43 файла, 29 капсул |
| Логи состояния | `wc -l` | AGENT_STATE 12 327; SESSION_HANDOFF 2 969 |
| Пины | `grep -E '^(langgraph|…)==' requirements.lock` | langgraph 1.2.9, langchain 1.3.13, chromadb 1.5.9, fastapi 0.139.2, sentence-transformers 5.4.1, sqlalchemy 2.0.49, pydantic 2.13.3 |
| Код | чтение `services/session.py` полностью; `resolution/application/shipment_status.py:258, 617-663` | см. §6 |
| Стратегия | чтение `D:\New_steps\rag.md` полностью (1 060 строк) | Фаза 0/NO-GO: строки 714–728, 956, 972–981 |

### 11.2 Источники исследований

Рынок (opus-агент, 2026-08-23): [Intercom Fin pricing 2026](https://www.gleap.io/blog/intercom-fin-ai-pricing-2026) · [Zendesk automated resolution pricing](https://premiumplus.io/blog/understanding-zendesks-new-automated-resolution-pricing-model-what-you-need-to-know) · [Decagon pricing](https://www.cloudtalk.io/blog/decagon-ai-pricing/) · [Sierra outcome pricing](https://sierra.ai/blog/outcome-based-pricing-for-ai-agents) · [Lorikeet: resolution-rate benchmarks 2026](https://www.lorikeetcx.ai/articles/resolution-rate-ai-customer-support-benchmarks-2026) · [Lorikeet: audit trails for regulated](https://www.lorikeetcx.ai/articles/ai-agent-audit-trails-regulated-guide) · [Sierra constellation/supervisor](https://sierra.ai/blog/constellation-of-models) · [Decagon AOP](https://decagon.ai/product/aop) · [Intercom Procedures FAQ](https://www.intercom.com/help/en/articles/13617008-fin-procedures-faqs) · [Zendesk acquires Forethought (TechCrunch, 2026-03-11)](https://techcrunch.com/2026/03/11/zendesk-acquires-agentic-customer-service-startup-forethought/) · [EU AI Act enforceability, Jul 2026](https://www.dataprotectionreport.com/2026/07/the-eu-ai-act-when-does-it-become-enforceable-now/) · [Digital Omnibus: high-risk deadlines postponed](https://www.gibsondunn.com/eu-ai-act-omnibus-agreement-postponed-high-risk-deadlines-and-other-key-changes/) · [Article 50](https://artificialintelligenceact.eu/article/50/) · [OSS agent frameworks comparison](https://jimmysong.io/blog/open-source-ai-agent-workflow-comparison/) · [Onyx seed](https://onyx.app/blog/seed-round) · [IATA ONE Record fact sheet](https://www.iata.org/en/iata-repository/pressroom/fact-sheets/fact-sheet-one-record/) · [SOC 2 for seed startups 2026](https://hub.causo.ai/guides/soc2-for-seed-startups-enterprise-deals-2026) · [Vector DB comparison 2026 (4xxi)](https://4xxi.com/articles/vector-database-comparison/) · [DE hiring signals 2026](https://recruiter.daily.dev/resources/hire-data-engineers-analytics-talent/).

Технологии (мои проверки, 2026-08-23): [arXiv 2607.07405 — deterministic gates, τ²-bench (проверено мной)](https://arxiv.org/abs/2607.07405) · [Qwen3 lineup guide 2026](https://baeseokjae.github.io/posts/qwen-3-full-lineup-guide-2026/) · [Qwen3 blog](https://qwenlm.github.io/blog/qwen3/) · [Qwen3.5 local (Unsloth)](https://unsloth.ai/docs/models/qwen3.5) · [Embedding models 2026 (StackAI)](https://www.stackai.com/insights/best-embedding-models-for-rag-in-2026-a-comparison-guide) · [Reranker benchmark (AIMultiple)](https://aimultiple.com/rerankers) · [RAG eval tools 2026 (Maxim)](https://www.getmaxim.ai/articles/top-5-tools-to-evaluate-rag-performance-in-2026/) · [Hallucination detection tools 2026 (Braintrust)](https://www.braintrust.dev/articles/best-hallucination-detection-tools-2026) · [τ²-bench (Sierra)](https://github.com/sierra-research/tau2-bench) · [τ-Knowledge](https://arxiv.org/pdf/2603.04370) · [LLM API pricing 2026](https://intuitionlabs.ai/articles/llm-api-pricing-comparison-2025) · [Haiku 4.5 vs GPT-5 mini](https://www.getapipulse.com/blog-gpt5-mini-vs-claude-haiku.html) · [Chroma vs Qdrant vs pgvector 2026 (dev.to)](https://dev.to/ayinedjimi-consultants/chromadb-vs-qdrant-vs-weaviate-vs-pgvector-vector-database-shootout-2026-14n7) · [LangGraph vs OpenAI Agents SDK vs PydanticAI 2026](https://open-techstack.com/blog/langgraph-vs-openai-agents-sdk-vs-pydanticai-2026/).

Числа из вторичных источников (цены, звёзды, доли) приведены как ориентиры на дату аудита и не перепроверялись мной по первоисточникам, кроме отмеченных.
