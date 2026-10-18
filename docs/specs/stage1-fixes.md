# Stage 1: the chat path made ready for any corpus — audit, fixes, new indexes

Status 2026-10-18: **audit and live check before the fixes run, fixes committed, the new
generation building, the check after the fixes registered.** [`PLAN.md`](../../PLAN.md) §5,
stage 1, is the authority; this spec records how the audit is repeated, what it found, the
outcome of each finding, the Mac forecast and the stop rule. The outcome table is the stage's acceptance
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
4. **Index path.** The new generation is built by the measurement path
   (`scripts/corpus_chunks.py` or the `chunks` step of `scripts/external_base.py`, then the
   embedding and index scripts); production updates an index through the upload path
   (`api.app._rebuild_vector_store_from_docs` → `build_vector_store_with_publication`).
   `tests/test_publication_chunk_parity.py` holds that both cut one corpus into the same chunks,
   text and metadata, and that a restarted API reads the same back from the published
   collection; with the API's headers switched off it fails (2026-10-18).

## Findings and outcomes

**Fix** — fixed universally (no hand-made dictionary) with a unit test; **limit** — recorded
with its reason; **stage N** — belongs to a later stage of `PLAN.md`; **not text** — neither the
model nor the customer reads it (log lines, id and hash patterns, headers of HTTP).

| # | Finding (audit key or reading) | Path | Outcome |
|---|---|---|---|
| 1 | `_read_docx` keeps paragraphs only: headings and tables lost | loading | **fix** (`ingestion/markup.py`): body in order; a heading by outline level or heading style, through the styles it is based on; numbered paragraphs to list items; tables to markdown tables, a merged cell once |
| 2 | `_read_html` joins text nodes with spaces: one line | loading | **fix**: h1–h6 to `#`, blocks to paragraphs, nested lists, tables to markdown (a table inside a cell is the cell's text), `pre` to a code block; scripts and styles dropped. WixQA's 6,221 source pages through the loader (`scripts/wixqa_loader_check.py`): every visible character, heading and table row of each, the 340 gold articles too, as the connection's own conversion ([record](../../reports/stage1/875f274/wixqa-loader-check.json)); 29 pages hold nothing beyond their title |
| 3 | `_read_pdf` page text, no headings | loading | **fix** where the PDF has an outline (bookmarks): each title becomes a heading on its page, and a page carries the levels of its section path above its first heading, since every page is chunked alone; a PDF without one stays page text — **limit**: font-size rules differ per document, a guess would be a per-corpus rule |
| 4 | `.txt`, `.json`, `.csv` | loading | **limit**: no markup to keep; `.json`/`.csv` already one document per item |
| 5 | Chunk header «[Контекст: Из документа …, раздел: …]» — writers `add_contextual_headers`, `IngestPipeline.ingest`; parsers `_strip_contextual_header`, `context_window._excerpt`, `doc_grade._is_context_header_only`, `evaluation/external_gold.py`, `scripts/production_baseline.py`, `scripts/ab_context_precision.py`, `scripts/external_base.py` | chat | **fix**: one module (`vectordb/contextual_header.py`) renders `[document › section › …]` and splits it by the chunk's `contextual_header` metadata; no natural-language word; parsers also accept the old prefix, so the old generation stays readable; `ab_context_precision.py` keeps the old form — it reads the pinned pool of the old generation |
| 6 | Header cut at 200 characters from the end nearest the text; document title twice | chat | **fix**: drop outer levels first, the document and the nearest heading stay; the first heading is not repeated when one of it and the file name is a run of the other's words (the longer stays); the page leaves the header and stays in metadata |
| 7 | LLM header prompt of `add_contextual_headers` in Russian | not on the path (`vectordb/manager.py` passes `llm=None`) | **fix** with row 5: English instruction, header in the fragment's language |
| 8 | A continued table chunk has no column-header row (`structural_split`) | chat | **fix**: a continued piece starts with its table's header row and separator row (`vectordb/table_header.py`), recorded as `table_header_prefix`; expansion drops them when it joins the piece back. Count (`scripts/table_continuations.py`, chunks 800/200), continued pieces without a header: aircargo 176 of 5,589 chunks in 132 documents (corpus digest `e69169b4`), ConditionalQA 127 of 13,778 in 60 (`d06190bb`), WixQA 442 of 37,571 in 166 (`e712f1a7`), MultiHop-RAG 0 of 11,231 (`306c227f`) |
| 9 | Parent expansion glues neighbours with their 200-character overlap; the core chunk's header lands mid-text | chat | **fix**: `structural_split` records each piece's seam (`seam_overlap`), expansion joins adjacent pieces of one section over it and counts the budget without the repeat; header first. A collection without the record is joined by a bounded whole-word match. Two adjacent pieces that are both retrieved stay two documents and repeat their seam — the selection is not expansion's to change: **limit** |
| 10 | `qa`, `self_eval`, `conversational_qa` prompts in Russian; `suggested_questions` sets no language; `_format_context_block` labels and the empty-context line in Russian; history labels «Пользователь/Ассистент» | chat | **fix**: the instruction names no language — answer in the question's language even when the context is in another (`qa`, `conversational_qa`), the suggestions in it, and self-evaluation lowers the score of an answer in another; context labels `[N | source=…]`, the empty context `[]`, history roles `user`/`assistant`; prompt ids V2 (Julia, 2026-10-17) |
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
| 23 | External tenants not shown to run BM25 + BGE-M3, rerank and expansion, after a restart too | chat | **fix** (`vectordb/manager.py`): the live check on fresh APIs read the path per tenant — aircargo and ConditionalQA (13,778 chunks) hybrid, 20 vector + 20 BM25 candidates; WixQA (37,571) vector only, BM25 0: the restart restores the BM25 corpus by reading the whole collection in one call, and SQLite refuses a call binding more than 32,766 variables. The restore now reads pages of 5,000 |
| 24 | Markdown YAML front matter (`---` … `---`) stays text of a document's first chunk: all 201 aircargo files, none of the external bases | loading | **limit**: the author's own lines (title, category, type) — retrieval reads their words; making them metadata or the header's name is a change to measure, not a known defect |
| 25 | An index directory without a database (`VECTORDB_CHROMA_DIR` at `<base>/index`, not `<base>/index/chroma`) opens as a new empty one: the tenant's every answer says the context lacks it, the log warns «unstamped index» (live check, 2026-10-18) | deployment | **limit**: a new tenant starts empty the same way; the stage-1 stand refuses a directory without `chroma.sqlite3` and reads a copy of each index, so no run writes into a generation |

**Live check before the fixes** (stand `99cd15f`, the first-generation indexes, 2026-10-18;
record [`reports/stage1/99cd15f/before.json`](../../reports/stage1/99cd15f/before.json): counts,
ids and the API's log lines, no text of an external base). One question per tenant, each on a
fresh API: aircargo, ConditionalQA and MultiHop-RAG took the hybrid path (20 vector + 20 BM25
candidates, rerank ok, 5 documents); WixQA took the vector lane alone (row 23). The answers to
the English questions of ConditionalQA and MultiHop-RAG came in Russian, WixQA's in English;
every answer prompt labelled its documents «[Документ N» and carried «[Контекст:» headers
(rows 5 and 10).

**The check after the fixes** (registered 2026-10-18, before its run): the same four questions
by `audit.sh after` on a stand whose product code is that of `e5e135a`, which cut the new
chunks; the indexes of the new generation (`/Users/julia/RAG_new_external_s1/`), a fresh API
each; record `reports/stage1/<stand commit>/after.json` by `audit_summary.py`. It passes when
the record shows, for every tenant: in `paths`, 20 vector and 20 BM25 candidates, rerank `ok`,
5 documents kept (`kind` alone does not tell: the vector-only run before also says `hybrid`);
in `bm25_restore_log`, the tenant's `Restored N chunks` line and no `Chunk restore failed` or
`WITHOUT BM25`; in `answer_letters`, more letters of the question's script than of the other
(Latin for the three external bases, Cyrillic for aircargo); in `prompts`, `labels_dokument`
and `header_kontekst` 0, `labels_source` and `header_first_line` at least 1 — window fitting
may drop documents or cut one to an excerpt without its header line, so not every one. A
question the client's cap stopped (1,020 s, named in `client_error`) or a run that failed
(`launch.status`) is `NOT_EVIDENCE` for its tenant.

## Mac forecast and stop rule

| Work | Forecast | Stops at |
|---|---|---|
| Live check before the fixes: stand + 4 questions | 40 min (≈ 400 s a question) | 1,020 s a question (3 × 340 s, the cap `audit.sh` gives the client); 2 h in all |
| Unit suite per push candidate | 9 min | 30 min |
| New index generation: aircargo; three external bases | 1 h; 10 h (9.8 h at connection) | 3 h; 30 h |
| E2E live check after the fixes on the new indexes | 40 min | as the first: 1,020 s a question; 2 h in all |

Each live run starts on an idle Mac (no `llama-server`, a 5-minute load below 2) and writes its
record under `reports/stage1/<commit>/` with the corpus SHA, the code SHA and the config. A run
stopped by the rule is `NOT_EVIDENCE` with its log. New indexes go to new directories; the old
ones are never rebuilt in place.

## Tools for stage 2 (step 5 of the stage)

All written (2026-10-18). The scripts each have a unit test; the stand's tools, like those of
the earlier chat records, are pinned with the live records by their artefact test when the
stage closes:

- **the chat-answer runner for any tenant** — the stand `reports/stage1/tools/`
  (`live_supervisor.py` takes `TENANT`, `CHROMA` and `CASES_FILE`, refuses an index directory
  without `chroma.sqlite3`; `live_api.py` records each retrieval's path and every rerank score);
  `audit.sh` runs the one-question check, `audit_summary.py` writes its committable record;
- **the judge's adapter** — `scripts/chat_answer_judge.py`: each answer graded against the
  documents its own answer prompt held, one English prompt for every corpus, the answer due in
  the question's language, the `[N]` marks counted, 15 retests and a quadratic kappa; **M2**
  against reference answers when the cases carry them;
- **the sample** — `evaluation/external_parts.json`, selections `stage2` (registered before any
  request): ConditionalQA 40 documents × 2 primary questions plus the first 20 not-answerable
  ones, WixQA the first 100 tuning questions (77 clusters), MultiHop-RAG the first 100 advisory
  ones (15 clusters, one of 49);
- **the signal tool** — `scripts/chat_signals.py`: S1–S7 of the
  [handover plan](handover-signal.md) through the widget's own nodes;
- **the new generation's build** — `scripts/corpus_chunks.py` (aircargo's chunks from its
  manifest) and `reports/stage1/tools/s1_supervisor.py` (four corpora into
  `/Users/julia/RAG_new_external_s1/`, started 2026-10-18 at `e5e135a`).
