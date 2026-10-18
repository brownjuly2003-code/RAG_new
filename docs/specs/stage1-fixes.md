# Stage 1: the chat path made ready for any corpus — audit, fixes, new indexes

Status 2026-10-17: **written, audit run, no fix yet.** [`PLAN.md`](../../PLAN.md) §5, stage 1,
is the authority; this spec records how the audit is repeated, what it found, the outcome of
each finding, the Mac forecast and the stop rule. The outcome table is the stage's acceptance
artefact: the stage closes when every row has an outcome, every **fix** row a commit with a unit
test, and the E2E checks below pass on the fixed code with the new indexes (rule (a)).

## The audit, repeatable

1. **Code.** `python -m scripts.universality_audit` walks every Python module of `agent/`,
   `api/`, `config/`, `ingestion/`, `llm/`, `services/` and `vectordb/` and lists string
   literals with Cyrillic letters (docstrings and comments excluded), regular expressions,
   literal word lists, literals naming the aircargo domain, and the reader of each file format
   in `ingestion/loader.py`. A finding is keyed by file, function and kind, so the key outlives
   an edit elsewhere in the file. Run on `99cd15f`: 136 Cyrillic literals, 64 patterns, 1 word
   list, 14 domain names under 84 keys. A key the table below does not cover is a new finding.
2. **Path.** Which of those modules the chat reaches was read from the code: `/api/ask/stream`
   with `streaming_rag_parity` off (the default) retrieves through `HybridRetriever`, fits
   `build_qa_prompt` to the window (`_fit_stream_prompt`, `agent/context_window.py`), streams
   the answer, then `build_self_eval_prompt` and `build_suggested_questions_prompt`. The agent
   graph of `agent/graph.py` is the widget's path (`/api/ask`) and the parity mode's.
3. **Live.** One question per tenant through `/api/ask/stream` on a stand, its trace read —
   before the fixes (what the path does now) and after them on the new indexes (the E2E of
   rule (a)). Questions: the first of `evaluation/curated_cases_aircargo.jsonl` and the first of
   each external base's open part (`evaluation/external_parts.json`).

## Findings and outcomes

**Fix** — fixed universally (no hand-made dictionary) with a unit test; **limit** — recorded
with its reason; **stage N** — belongs to a later stage of `PLAN.md`; **not text** — neither the
model nor the customer reads it (log lines, id and hash patterns, headers of HTTP).

| # | Finding (audit key or reading) | Path | Outcome |
|---|---|---|---|
| 1 | `_read_docx` keeps paragraphs only: headings and tables lost | loading | **fix**: body in order, heading styles to `#`, tables to markdown tables |
| 2 | `_read_html` joins text nodes with spaces: one line | loading | **fix**: h1–h6 to `#`, blocks to paragraphs, lists, tables to markdown |
| 3 | `_read_pdf` page text, no headings | loading | **fix** where the PDF has an outline (bookmarks); a PDF without one stays page text — **limit**: font-size rules differ per document, a guess would be a per-corpus rule |
| 4 | `.txt`, `.json`, `.csv` | loading | **limit**: no markup to keep; `.json`/`.csv` already one document per item |
| 5 | Chunk header «[Контекст: Из документа …, раздел: …]» — writers `add_contextual_headers`, `IngestPipeline.ingest`; parsers `_strip_contextual_header`, `context_window._excerpt`, `doc_grade._is_context_header_only`, `evaluation/external_gold.py`, `scripts/production_baseline.py`, `scripts/ab_context_precision.py`, `scripts/external_base.py` | chat | **fix**: one module (`vectordb/contextual_header.py`) renders `[document › section › …]` and splits it by the chunk's `contextual_header` metadata; no natural-language word; parsers also accept the old prefix, so the old generation stays readable; `ab_context_precision.py` keeps the old form — it reads the pinned pool of the old generation |
| 6 | Header cut at 200 characters from the end nearest the text; document title twice | chat | **fix**: drop outer levels first, the document and the nearest heading stay; the first heading is not repeated when one of it and the file name is a run of the other's words (the longer stays); the page leaves the header and stays in metadata |
| 7 | LLM header prompt of `add_contextual_headers` in Russian | not on the path (`vectordb/manager.py` passes `llm=None`) | **fix** with row 5: English instruction, header in the fragment's language |
| 8 | A continued table chunk has no column-header row (`structural_split`) | chat | **fix**: a continued piece starts with its table's header row and separator row (`vectordb/table_header.py`), recorded as `table_header_prefix`; expansion drops them when it joins the piece back. Count (`scripts/table_continuations.py`, chunks 800/200), continued pieces without a header: aircargo 176 of 5,589 chunks in 132 documents (corpus digest `e69169b4`), ConditionalQA 127 of 13,778 in 60 (`d06190bb`), WixQA 442 of 37,571 in 166 (`e712f1a7`), MultiHop-RAG 0 of 11,231 (`306c227f`) |
| 9 | Parent expansion glues neighbours with their 200-character overlap; the core chunk's header lands mid-text | chat | **fix**: `structural_split` records each piece's seam (`seam_overlap`), expansion joins adjacent pieces of one section over it and counts the budget without the repeat; header first. A collection without the record is joined by a bounded whole-word match. Two adjacent pieces that are both retrieved stay two documents and repeat their seam — the selection is not expansion's to change: **limit** |
| 10 | `qa`, `self_eval`, `conversational_qa` prompts in Russian; `suggested_questions` sets no language; `_format_context_block` labels and the empty-context line in Russian; history labels «Пользователь/Ассистент» | chat | **fix**: language-neutral instruction to answer in the question's language (Julia, 2026-10-17); labels without words |
| 11 | BM25 tokens `[^\W_]+`, `\w+` in `context_window`, `grounding` | chat | **limit**: languages written without spaces (Chinese, Japanese, Thai) get one token per run of letters; none of the four corpora is one |
| 12 | Fixed customer messages in `ask_stream` («Сессия не инициализирована.», «Ошибка обработки запроса.», «Не удалось получить ответ.») | chat, error branches only | **limit**: the interface's language, as the whole web UI (`static/`, `templates/`); interface texts are stage 6 |
| 13 | Widget graph: fixed messages, `_is_knowledge_gap` Russian refusal phrases, ticket texts, `response_safety` refusal | widget | **stage 3**: the widget's handover is decided there; the refusal phrases are a hand-made list to replace |
| 14 | `_build_agentic_search_query` rewrites «достав…/москв…» to fixed aircargo queries | widget agentic mode | **stage 3**: a hand-made domain rule; removed when the widget is touched |
| 15 | `agent/tools.py` order-status stub («Заказ #42»), `_extract_order_id` | widget tools | **stage 3** with row 13 |
| 16 | `shipment-status` journey (`conversation.py`, `feedback.py`, `settings.py`) | widget, phase A | **limit**: the resolution kernel's one journey, on only by its environment list; phase B (`PLAN.md` §6) |
| 17 | `services/escalation.py` ticket messages in Russian | handover | **stage 3** |
| 18 | `api/routers/agent.py::_term_set` Russian suffix stripping | operator console | **limit**: operator tool for similar tickets, not the customer path; listed for any operator work |
| 19 | `MultiQueryRetriever` prompt in Russian | off by default | **stage 7** with the retrieval mechanisms |
| 20 | `structure_graph` Russian reference patterns, `entity_extraction` prompt, `entity_normalization` aircargo synonyms, `factcard_extractor` prompt | graph lane, fact cards, off | **stage 7** (`PLAN.md` stage 1 names them for it) |
| 21 | `config/settings.py` validation log lines, `agentic_measure` | operator | **not text** |
| 22 | id, hash, SHA, date and URL-credential patterns; CORS header list; GraceKelly time pattern | — | **not text** |
| 23 | External tenants not shown to run BM25 + BGE-M3, rerank and expansion, after a restart too | chat | **fix or proof**: the live check above reads the trace's retrieval mode per tenant |

## Mac forecast and stop rule

| Work | Forecast | Stops at |
|---|---|---|
| Live check before the fixes: stand + 4 questions | 40 min (≈ 400 s a question) | 1,200 s a question; 2 h in all |
| Unit suite per push candidate | 9 min | 30 min |
| New index generation: aircargo; three external bases | 1 h; 10 h (9.8 h at connection) | 3 h; 30 h |
| E2E live check after the fixes on the new indexes | 40 min | as the first |

Each live run starts on an idle Mac (no `llama-server`, a 5-minute load below 2) and writes its
record under `reports/stage1/<commit>/` with the corpus SHA, the code SHA and the config. A run
stopped by the rule is `NOT_EVIDENCE` with its log. New indexes go to new directories; the old
ones are never rebuilt in place.

## Tools for stage 2 (step 5 of the stage)

A chat-answer runner for any tenant; the judge's adapter for chat answers (each answer brings
its documents) with an English prompt, its own stability check and the `[N]` citation check;
M2 against reference answers; the sample of ≈ 100 questions per external base from the open
parts, by cluster, committed before the first request; the signal tool (signal stage 1.0 of
the [handover plan](handover-signal.md)).
