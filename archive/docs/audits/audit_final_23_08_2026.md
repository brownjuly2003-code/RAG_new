# Финальный аудит RAG_new — 23.08.2026 (синтез Fable + Sol)

**Статус документа:** объединяет `audit_fable_23_08_2026.md` (стратегический: актуальность, рынок, режим работы) и `audit_sol_23_08_2026.md` (инженерный: runtime-пути, безопасность, CI, зависимости). Все спорные и принятые «на веру» пункты перепроверены по коду и внешним источникам 24.08.2026. Этот файл — единая точка входа; исходные аудиты остаются как приложения.
**Репозиторий:** `D:\RAG_new`, ветка `master`, HEAD `26866e9` — не менялся с момента обоих аудитов; untracked только аудит-файлы.
**Git remote:** отсутствует. CI для RAG_new не запускался ни разу.
**План действий:** `plan_23_08_2026.md` (отдельный файл, вход для следующих сессий).

---

## 1. Вердикт

RAG_new — две вселенные в одном репозитории. Первая — зрелый наследованный RAG-runtime (FastAPI + LangGraph + Chroma) с честной eval-культурой (7× NO-SHIP по данным). Вторая — новое детерминированное ядро «Verifiable Resolution OS» (`resolution/`, `knowledge/`, `actions/`, `services/session.py`, миграции 024–031): ~8,7 тыс. строк высокого качества, 198–263 зелёных фокусных теста — и **ноль импортов из production-кода**. Пользователь `/api/ask` получает ровно тот же продукт, что 18 августа (точка форка).

Оба аудита сходятся в главном: **сильнейшая часть репозитория не создаёт ценности, потому что не подключена к публичному пути** (split-brain), а release-машинерия слайсов G1–G8 построена на синтетическом корпусе из 17 сценариев (VR precision 1/2, VRY 1/17 — «constructed evidence, not measured performance»). Fable добавляет причинность: это инверсия критического пути — Фаза 0 брифа (domain owner, разметка 100 реальных кейсов, human baseline) пропущена, и автопилотный формат работы систематически выбирает локально доказуемые слайсы вместо слайсов, требующих внешних решений.

Второй по важности факт: **вся работа существует в единственной копии на `D:\` без remote, бэкапа и CI** — 32 коммита, +36,8 тыс. строк. Дешевейшее действие с максимальным leverage — push в private remote (30 минут).

**Итоговые оценки (синтез):** как поставляемая система — **5,5/10** (sol 5,8 / fable 5,4; разница только в весе штрафа за отсутствие remote/CI); как инженерная база — **8,0–8,5/10**; как портфельный актив — **3/10 сейчас → 8,5/10** после исполнения плана.

**Рекомендация:** режим B — «доказательство инженерной зрелости» (6–8 недель соло + агенты): push/freeze → одна сквозная нить shipment-status в `/api/ask` → 100 реальных размеченных кейсов → бенчмарк генератора → spike pgvector → README-first публикация. Enterprise-трек sol §11 (durable HTTP-семантика, 2 реплики, SBOM/SLSA, service accounts) — только при появлении design partner. Детали — `plan_23_08_2026.md`.

---

## 2. Верификация 24.08.2026 — что перепроверено

Каждый ключевой факт обоих аудитов сверен с кодом на HEAD `26866e9`; внешний факт (цены Mistral) — с официальной страницей.

| # | Утверждение | Проверка 24.08 | Вердикт |
|---|---|---|---|
| V-1 | 0 импортов `resolution`/`knowledge`/`actions`/`services.session` из production (`api`, `agent`, `main.py`, `services`, `ingestion`, `llm`, `vectordb`, `channels`, `integrations`) | `grep -rlE` → пусто | ✅ подтверждено |
| V-2 | `run_legacy_ask_shadow` существует, но не вызывается из production | `resolution/application/shipment_status.py:617`; grep по `api agent services main.py` → пусто | ✅ подтверждено |
| V-3 | SSE fail-open: fallback `quality_score=50`, `quality_source=llm`, `route=auto`; токены уходят до терминальных проверок | `api/routers/conversation.py` (~1535: `result.get("quality_score") or 50`, `route ... or "auto"`; ~1245: `yield "data:"` token до route-вычисления ~1367) | ✅ подтверждено |
| V-4 | Streaming по умолчанию выключен (дефект не активен в sync-only) | `config/settings.py:656,663`: `STREAMING_ENABLED=false`, `STREAMING_RAG_PARITY=false` | ✅ подтверждено |
| V-5 | MyPy CI-scope не включает `resolution`, `actions`, `knowledge`, `services`, `cache`, `integrations` | `.github/workflows/ci.yml:129-130` | ✅ подтверждено |
| V-6 | Coverage source включает `resolution`, но не `actions`/`knowledge`/`services`/`cache`/`integrations` | `pyproject.toml`, `[tool.coverage.run] source` | ✅ подтверждено |
| V-7 | README-заявление «All production packages are mypy --strict clean (CI-enforced)» ложно (scope + CI ни разу не запускался) | `README.md:94`; remote отсутствует | ✅ подтверждено, ложно дважды |
| V-8 | Точечные type-ошибки из sol F-05 существуют | `actions/ticket.py` (`**kwargs: object` → `create_escalation(**kwargs)`), `cache/redis_cache.py:95` (`def _get_redis():` без аннотации) | ✅ образцы найдены |
| V-9 | **Mistral pricing неверен** (fable принимал на веру) | `config/providers.yml:80-95` vs официальная страница pricing (fetch 24.08): 3b 0,04/0,04 → факт 0,10/0,10 (недоучёт ×2,5); 8b 0,10/0,10 → 0,15/0,15 (×1,5); small input 0,20 → 0,15; **large 2,00/6,00 → 0,50/1,50 (завышен ×4)** | ✅ **подтверждено независимо** |
| V-10 | API-key даёт `{"sub": "api-key-user", "role": "admin", "tenant": "default"}` | `auth/dependencies.py:64` | ✅ подтверждено |
| V-11 | JWT без `iss`/`aud`/`iat`/`jti`, без rotation/revocation | `auth/jwt_handler.py:25-46`: только `sub, role, tenant, exp, type` | ✅ подтверждено |
| V-12 | Cookie-bridge пропускает unsafe-запрос без `Origin` (fail-open) | `api/app.py` (~2045): `if not origin: return True` | ✅ подтверждено (риск смягчён SameSite) |
| V-13 | `ragas_eval.py` подставляет `expected_answer` при отсутствии фактических ответов | `evaluation/ragas_eval.py:432-435` (`elif tc.expected_answer: answer = tc.expected_answer`) | ✅ подтверждено |
| V-14 | `eval_gate.py` печатает `EVAL GATE: PASSED (graceful skip)` | `scripts/eval_gate.py:274-278` | ✅ подтверждено |
| V-15 | Helm: 1 replica by design (задокументировано), backup encryption выключен | `deploy/helm/values.yaml:1-6,104-106` | ✅ подтверждено |
| V-16 | Размеры state-доков: fable считал строки, sol — байты; оба верны | `AGENT_STATE.md` 12 327 строк / 678 KB; `docs/SESSION_HANDOFF.md` 2 969 строк / 221,5 KB | ✅ оба верны |
| V-17 | Генератор по умолчанию — `qwen2.5:7b` (сентябрь 2024) | `config/settings.py:298` | ✅ подтверждено |
| V-18 | Корпуса: синтетика ядра ровно **17 сценариев**; реальные 100 air-cargo без journey-разметки; калибровка 10 | `evaluation/resolution/corpora/v0.1/shipment-status.json` → `scenarios: 17`; `curated_cases_aircargo.jsonl` 100; `phase0_labels.jsonl` 135; `calibration/labelled_routes.jsonl` 10 | ✅ подтверждено |
| V-19 | Расхождение чисел тестов 158 / 198 / 263 | BACKLOG (158) — узкий гейт; fable (198) — 17 файлов; sol (263) — более широкий фокусный набор. Разные scope, противоречия нет | ✅ снято |

Не перепроверялись (нет расхождений между аудитами, дорого повторять): полный suite 1 878 тестов, live-LLM, миграции на реальном Postgres, LOC-подсчёты (146 157 total / 52 251 production — методика sol воспроизводима).

---

## 3. Разрешение расхождений Fable ↔ Sol

| Тема | Sol | Fable | Финальное решение |
|---|---|---|---|
| **Рыночная дифференциация** | 9,0/10 | ≈4/10 | **Разделить понятия.** Механизм (детерминированный гейт, evidence, replay) — актуальный инженерный стандарт 2026, подтверждён наукой (arXiv 2607.07405, τ²-bench) — **8/10**. Рыночный moat — **4/10**: тот же питч продают Lorikeet, Sierra, Decagon AOP, Intercom Procedures, Rasa CALM; логистика занята (Expedock, Vooma, Zowie/InPost). Sol сам оговаривал «гипотезу нужно подтвердить buyer research» — research fable это и сделал, результат отрицательный для соло-коммерциализации. Позиционирование: «грамотная реализация best practice», не «открытие» |
| **План** | 90 дней, 2–4 инженера (+16–20 недель при одном) | 6–8 недель соло, режим B | **База — режим B** (fable §8): реальная capacity = 1 человек + агенты, без domain owner/security/ops, железо без GPU. Sol §11 (durable HTTP 428/412, 1000 contended attempts, 2 реплики, SBOM/SLSA, service accounts) — **условный трек при design partner**, не выбрасывается |
| Helm/SBOM/SLSA (sol F-09) | P1 | этап 6 | **P2/условный трек.** Enterprise-DoD без enterprise-заказчика преждевременен |
| Доки-как-система | P2 (sol F-10) | P1 (fable F-5) | **P1.** Это не гигиена, а механизм, воспроизводящий инверсию пути: дорогой онбординг (43 md в корне + 12 тыс. строк state по правилу «читать все md») смещает автопилот к мелким локальным слайсам |
| Chroma (sol F-08 «масштаб» vs fable F-6 «граница доверия») | P1/P2 измерить | P1 spike pgvector | **Объединено:** один spike pgvector+FTS/RRF с двойной мотивацией — единая RLS-граница (главный аргумент: заявление «verifiable isolation» при retrieval вне RLS) + снятие однопроцессного потолка кэшей. Решение только по числам, оформить ADR |
| Auth/tenancy (sol F-06) | P1 | «этап 6» | **P1 при любом внешнем/multi-tenant запуске; P2 в режиме B** (локальное демо + фикстуры). Дешёвые фиксы (fail-closed Origin) можно взять раньше |
| Mistral pricing (sol F-07) | P1 | «на веру» | **Подтверждено web-проверкой 24.08 (V-9). P1, чинится за час** — цены участвуют в traces/Prometheus/daily paid-cost guard, т.е. это не косметика |
| Итоговая оценка | 5,8 | 5,4 | **5,5.** Вся разница — вес штрафа за отсутствие remote/CI/бэкапа; по фактам расхождений нет |

---

## 4. Единый список findings

Приоритеты: **P0** — блокирует любую ценность (продуктовую или карьерную); **P1** — закрыть до публикации/пилота; **P2** — планировать. Все findings сверены с кодом (§2).

### P0

- **FIN-01 — Split-brain: ядро не владеет публичным запросом** (sol F-01/F-02 + fable F-3; V-1, V-2). 0 production-импортов; `run_legacy_ask_shadow` не зарегистрирован; `SessionService` (`services/session.py:226`) не вызывается из `/api/ask`; вместо него `_persist_ask_messages` best-effort + глобальный 60-сек cooldown на все tenants при DB-ошибке (`api/routers/conversation.py:217`). Причинность (fable): wiring требует решений, которые автопилот не может принять «локально доказуемо». Лечится изменением правила приёмки слайса, не «ещё одним слайсом».
- **FIN-02 — Инверсия критического пути: release-машинерия на синтетике** (fable F-1; V-18). Фаза 0 брифа (`D:\New_steps\rag.md:714-728, 956, 972-981`: domain owner, 100 размеченных кейсов, human baseline, NO-GO без owner) пропущена; вместо неё G1–G8 + REL-03A/B/C на 17 синтетических сценариях; метрики VR 1/2, VRY 1/17 — числа без содержания; все три owner-checkbox в `archive/docs/architecture/migration-plan.md:406-408` пусты. Слайсы G2–G8 производят доказательства о предыдущих слайсах («манифест, пинящий манифест») — самоподдерживающаяся экономика доказательств.
- **FIN-03 — Единственная копия работы, мёртвый CI** (fable F-2; V-7). Remote пуст, 32 коммита только на `D:\`, `.git` 34 MB; ci.yml никогда не выполнялся; README:94,439 заявляет CI-enforcement. Потеря диска = потеря ядра. Fix = 30 минут.
- **FIN-04 — SSE fail-open** (sol F-03; V-3, V-4). P0 при включении streaming; P1 в текущем sync-only профиле (дефолты безопасны). Токены уходят клиенту до терминальных safety/grounding-проверок; fallback `quality=50`/`route=auto`. Правильное лечение — SSE как projection persisted events (условный трек); в режиме B streaming остаётся выключенным.

### P1

- **FIN-05 — Три параллельных незавершённых потока без WIP-лимита** (fable F-4). Trust Foundation на шаге 4.8d3e (5–10 не начаты, live-гейты открыты с 23.07), Resolution на G8, REL-03 на C. Ни один не даёт демо. WIP-лимит = 1 нить.
- **FIN-06 — Процессная нагрузка — главная статья расходов** (fable F-5 + sol F-10; V-16). 43 md в корне (29 капсул), AGENT_STATE 12 327 строк, SESSION_HANDOFF 2 969; документации больше, чем production-кода. Три живых документа (`CURRENT_STATE.md` ≤150 строк, `ROADMAP.md`, `EVIDENCE_INDEX.md`), капсулы → `docs/evidence/`, AGENT_STATE → архив с дайджестом.
- **FIN-07 — Разрыв заявленных и фактических гейтов** (sol F-05 + fable F-10; V-5–V-8). MyPy/coverage scope не включают новые пакеты; README врёт; ≥6 type-ошибок в непокрытых пакетах (нижняя граница). Синхронизировать три множества: production packages ↔ MyPy scope ↔ coverage source; сначала informational job, потом blocking.
- **FIN-08 — Mistral cost accounting фактически неверен** (sol F-07; V-9 — подтверждено web 24.08). Цены в traces/Prometheus/daily guard: 3b ×2,5 недоучёт, large ×4 завышение. Исправить registry, датированный snapshot + contract test, логировать resolved model для `*-latest`.
- **FIN-09 — Несогласованная граница тенантов + однопроцессный потолок retrieval** (fable F-6 + sol F-08). RLS форсирован на новых таблицах (025/029/030/031), а retrieval — Chroma per-tenant коллекции + BM25 в памяти без quota/LRU (`vectordb/manager.py:47,812`); фильтры Chroma — после ANN. Spike pgvector+FTS/RRF на 100-кейсовом корпусе → ADR: миграция или явный инвариант «изоляция retrieval — application-level».
- **FIN-10 — Плато качества, неверный следующий рычаг** (fable F-7; V-17). Faithfulness 0,84 (<0,90), precision 0,58 (<0,63) при recall 0,98 и 7× NO-SHIP retrieval-плеч: retrieval выжат. Рычаги: генератор (qwen2.5:7b, сент. 2024 → бенчмарк Qwen3-8B/Qwen3.5-класса), claim-level compilation, независимый дешёвый NLI-чекер (HHEM-2.1/MiniCheck) вторым судьёй.
- **FIN-11 — Release evidence: опасные заглушки в eval-контуре** (sol F-04; V-13, V-14). `ragas_eval.py` может подставить `expected_answer` как ответ; `eval_gate.py` печатает «PASSED (graceful skip)»; `data/evaluation/benchmark_results.json` — старый 12-кейсовый демо-файл. Правило: skipped/self-judged/expected-copy = `NOT_EVIDENCE`, hard-fail в release lane; один versioned evaluation manifest с провенансом.
- **FIN-12 — Auth/tenancy наследованного слоя** (sol F-06; V-10–V-12). API-key → admin/default tenant; JWT без iss/aud/iat/jti/rotation; cookie-bridge fail-open без Origin; legacy `sessions`/`messages` без forced RLS. **P1 при любом внешнем multi-tenant запуске; в режиме B — P2**, кроме дешёвого fail-closed Origin.

### P2

- **FIN-13 — Данные — первопричина** (fable F-8; V-18). 100 реальных кейсов не размечены по journey/outcome/root-cause; калибровка — 10 строк; синтетика (17) не связана с реальностью. Самая дешёвая работа с максимальной отдачей после push: разметка = 1 день владельца + агента. (P2 как finding, но **вершина плана** — фаза B.)
- **FIN-14 — Планы не откалиброваны под capacity** (fable F-9). Все существующие планы предполагают команду/владельцев, которых нет. Закрывается `plan_23_08_2026.md`.
- **FIN-15 — Deployment blueprint ≠ production** (sol F-09; V-15). 1 replica (осознанно, задокументировано), backup encryption off, нет NetworkPolicy/PDB/SBOM/подписей/digest-pin. Условный трек (design partner).
- **FIN-16 — God-modules** (sol F-11). `agent/graph.py` 4 133, `api/app.py` 2 069, `conversation.py` 1 671, `db/models.py` 1 449. Рефакторинг — только после runtime-конвергенции, через characterization tests, извлечение по ownership.

---

## 5. Что сделано действительно хорошо (консенсус обоих аудитов)

- **Код ядра.** `services/session.py`: advisory-lock, `FOR UPDATE`, DB-clock authority, epoch-fencing, идемпотентный replay по digest, transaction-local tenant GUC. Interview-ready.
- **Честность утверждений.** «Locally complete» нигде не выдаётся за release; синтетика везде помечена; `deployment_authorized=false`. Редкость.
- **Eval-культура.** 7× NO-SHIP по данным (precision покупалась потерей recall — отказались), judge-репорты, human calibration, pass^k/state-grading — методика τ²-bench уровня 2026.
- **Ingestion/index lifecycle:** staging → publish → rollback → manifest → retention.
- **Инженерные гейты:** hashed locks, Ruff clean, pip-audit clean, coverage 72%, документированные исключения.
- **ADR-дисциплина** (0001–0006) с честным «не делать заранее» (GraphRAG, OPA, микросервисы, MCP).
- **Закрытые старые претензии** (не копировать из аудитов апреля–июля): ASGI body limit, OIDC issuer/subject binding, bounded Redis fallback, durable escalation, index publish/rollback.

---

## 6. Сводные оценки

| Направление | Sol | Fable | Финал |
|---|---:|---:|---:|
| Механизм/идея как инженерный стандарт | 9,0 | 8,0 | **8,0** |
| Рыночная дифференциация (moat) | — | 4,0 | **4,0** |
| Целевая архитектура | 8,5 | — | **8,5** |
| Качество кода и тестов ядра | — | 8,5 | **8,5** |
| Фактическая runtime-интеграция | 4,0 | 3,0 | **3,5** |
| Retrieval/generation quality | 6,0 | 6,0 | **6,0** |
| Resolution evidence / данные на реальных кейсах | 4,0 | 3,0 | **3,5** |
| Security/tenancy | 6,0 | — | **6,0** |
| Tests/CI/governance | 7,0 | — | **6,0** (CI ни разу не запускался) |
| Операционная устойчивость проекта (remote/бэкап/CI) | — | 2,0 | **2,0** |
| Maintainability / процесс | 4,0 | 3,5 | **4,0** |
| **Как поставляемая система** | **5,8** | **5,4** | **5,5** |
| **Как инженерная база / потенциал** | **8,5** | **8,0** | **8,0–8,5** |
| **Как портфельный актив: сейчас → после плана** | — | **3,0 → 8,5** | **3,0 → 8,5** |

---

## 7. Рекомендация

Режим **B — «доказательство инженерной зрелости»** (обоснование выбора: fable §7; продуктовый клин и целевой runtime при появлении партнёра: sol §10–11). Пять критериев «сильного» проекта:

1. Сквозная нить: `docker compose up` → вопрос о статусе отправления → ответ + evidence bundle + replay receipt; один E2E-тест это доказывает.
2. Честные числа на 100 реальных размеченных кейсах (VR precision / VRY / pass^3) рядом с legacy-baseline.
3. Качество выше собственных floors (faithfulness ≥ 0,90, precision ≥ 0,63) или задокументированный NO-SHIP.
4. Единая trust boundary (pgvector+RLS) или явный ADR-инвариант.
5. Видимость: публичный репозиторий, зелёный CI, README-first с числами и $/resolution, 3-минутное демо.

Пошаговый план с гейтами-командами и вопросами к владельцу — **`plan_23_08_2026.md`**.

Стоп-лист до конца плана: G9+, REL-03D «ради полноты», MCP-коннекторы, GraphRAG, смена vector DB без бенчмарка, микросервисы/Kafka/OPA, новые каналы/дашборды, любой слайс, не меняющий поведение `/api/ask` или число размеченных кейсов.
