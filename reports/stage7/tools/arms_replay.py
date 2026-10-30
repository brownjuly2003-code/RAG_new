"""Stage 7, step 1: the retrieval arms H, S and P on stage 2's lists, read at M3; no answer.

docs/specs/stage7-step1-arms-m3.md (registered before the run); PLAN.md stage 7, step 1. Reads, on
the Mac, stage 2's retrieval records of stand 5e308fe and the bases' chunk archives, the
committed export of the same runs, and V4's saved stream prompts of stand 4f48fed with their
committed rows; no model is called:

  python -m reports.stage7.tools.arms_replay replay [--runs DIR] [--data-root DIR]
      [--v4-runs DIR] [--out DIR] [--private DIR]
  python reports/stage7/tools/arms_replay.py judged --plan DIR [--record DIR] [--runs DIR]

The defaults are the Mac's folders (RUNS, DATA_ROOT, V4_RUNS, OUT, PRIVATE below); OUT and
PRIVATE stand outside the checkout. Every question of p2-wixqa, p2-conditionalqa,
p2-multihoprag, p2-aircargo and p2-aircargo-gr (415) goes through the product's own retriever
over its base's chunk archive, the recorded lists standing in for the index and the models: the
vector store returns the recorded vector lane, the BM25 index ranks the recorded BM25 lane in
its order, the cross-encoder returns each fused candidate's recorded score and refuses any
other pool. K stays 20, the five stay five, the input window stays V4's; the checkout's own
control must be the same (K 20, a 4,096 window, PyTorch's reranker) or the replay stops.

  H - HybridRetriever.get_relevant_documents_with_path: stage 2's path, today's default;
  S - HybridRetriever.get_graph_documents_with_path over the structural graph of the base's
      chunks, built and projected as vectordb.manager.get_retriever does with graph retrieval
      on and no entity graph: the same five, section coherence, the section expansion;
  P - P1b, rel 0.2 + expansion: of H's five the first scripts.p1_adaptive_k.kept_count("rel",
      0.2) by their cross-encoder scores, then HybridRetriever._expand_parents.

Each arm's documents go through the chat's fitting (api.routers.conversation._fit_stream_prompt,
no history) under the answer prompt V4 at V4's input limit: the prompt the chat would send,
flattened as the provider sends it.

The parity gate, before any arm is read. On every question H must give the record's pool, its
five with their scores, its expansion and, under stage 2's prompt V3, its sent documents and
its prompt byte for byte, the one whose hash the export holds; the M3 points read again must be
the export's. On the 300 questions V4 answered (WixQA, ConditionalQA, aircargo) H under V4 must
give V4's saved prompt byte for byte, the file its committed row names by hash. Any failure
writes OUT/parity.jsonl (ids and flags) and exits 3, and no arm is read.

M3 at «sent» (reports/stage2/tools/retrieval_summary.coverage), «expanded» beside: on the
external bases by each base's gold, H against each arm by exact McNemar on the primary metric.
Gate G1 is PLAN's: an arm goes on to answers only on an M3 gain at the two deciding bases
pooled that is detected and larger than the MDE, c - b > 2.8 sqrt(b + c), with no detected loss
and no NOT_EVIDENCE at any stop reading. On aircargo, and only for the arms that so qualify on
the external bases, the one context-judge plan (scripts/context_judge.build_plan) of H's
prompts and of each such arm's prompts that differ, written under PRIVATE after the record
passes its checks and not judged here; `judged` reads the plan's verdicts on the laptop and
completes G1, aircargo's readings stopping an arm and qualifying none. No such arm: G1 decides
at the replay.

Writes OUT/record.json and OUT/rows.jsonl (ids, flags, numbers); stage2_common.without_text
refuses either when a string of it names a document of a base or holds a question. PRIVATE holds
the judge's texts: PRIVATE/runs/ARM-LABEL and PRIVATE/judge/plan.json.
"""

import argparse
import contextlib
import hashlib
import json
import math
import os
import sys
import tempfile
from collections import Counter
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
WS = HERE.parents[2]
sys.path.insert(0, str(WS / "reports" / "no-rerank" / "tools"))
sys.path.insert(1, str(WS / "reports" / "answer-prompt-v4" / "tools"))
import no_rerank_point as nr  # noqa: E402
import v4_record  # noqa: E402
from retrieval_summary import Excerpted, excerpt_places, position  # noqa: E402
from stage2_common import load_jsonl, sha256, source_names, spread, without_text  # noqa: E402

SPEC = "docs/specs/stage7-step1-arms-m3.md"
CODE_SHA = nr.CODE_SHA
V4_STAND = "4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1"
EXPORT = nr.EXPORT
V4_DIR = WS / "reports" / "answer-prompt-v4" / "4f48fed"
# The inputs, frozen by the spec: the export's manifest, V4's record, each base's chunk archive.
EXPORT_MANIFEST_SHA256 = "f8dbfb9edbdd9af830017c2c583aedcbfc8f8fbedde6c806abb5de94288985e9"
V4_RECORD_SHA256 = "81162268ad1c3af7cbe8f5cc885c7137c29864ed3a9acf5b778f17d28821749e"
ARCHIVES = {
    "wixqa": "2cc24c6f56a394ff189366f70b6ed11b919ba8f545fa592e019c9b193814ba5a",
    "conditionalqa": "e25960d5e4263a0d7f7ea9b02ac217d29be912b078d65bbb4ac0480c677d8755",
    "multihoprag": "db25b882fc9fe6cd6e76101330ffc816a9081813268706a016a263171cf80300",
    "aircargo": "b3e4d3727f3456b66ee398698b6a610f60c0c269de5c81bd814ae4e2c0ebba15",
}
LABELS = {
    "p2-wixqa": "wixqa",
    "p2-conditionalqa": "conditionalqa",
    "p2-multihoprag": "multihoprag",
    "p2-aircargo": "aircargo",
    "p2-aircargo-gr": "aircargo",
}
V4_KEYS = {"p2-wixqa": "wixqa", "p2-conditionalqa": "conditionalqa", "p2-aircargo": "aircargo"}
EXTERNAL = tuple(nr.METRICS)
# PLAN.md stage 7: aircargo, ConditionalQA and WixQA decide; MultiHop-RAG is printed, advisory.
DECIDING = ("conditionalqa", "wixqa")
# PLAN.md stage 7: «М3 выросла» on ConditionalQA and WixQA «вместе»: the one reading that qualifies.
QUALIFIES_AT = "pooled_deciding"
# PLAN.md §4.4's MDE, the K curve's: 1.96 + 0.84 standard errors, detected four times in five.
MDE_Z = Fraction(14, 5)
AIRCARGO = ("p2-aircargo", "p2-aircargo-gr")
ARMS = ("S", "P")
KMAX = 20
TOP = nr.TOP
WINDOW = 4096
LIMIT = 2636
# The path stage 4 accepts, as the checkout's settings give it: H rests on it.
CONTROL = {"retrieval_top_k": KMAX, "ollama_context_window": WINDOW, "reranker_runtime": "torch"}
V4_SAVED = 300
REL = 0.2
MAX_UNREAD = 5
MAX_MISSING = 5
NOT_EVIDENCE = nr.NOT_EVIDENCE
V3_ID, V4_ID = "QA_PROMPT_V3", "QA_PROMPT_V4"
HITS = {"full": ("full",), "full_or_partial": ("full", "partial")}
PATH_KEYS = (
    "kind",
    "candidates",
    "rerank_scores",
    "rerank_batch_effective",
    "retrieved_contexts",
    "retained_contexts",
    "dropped",
)
RENAMED = {"b_reranker_only": "b_h_only", "c_fused_only": "c_arm_only"}
RUNS = Path("/Users/julia/RAG_new_chat_5e308fe/chatlive/runs")
DATA_ROOT = Path("/Users/julia/RAG_new_external_s1")
V4_RUNS = Path("/Users/julia/RAG_new_chat_4f48fed/chatlive/runs")
OUT = Path("/Users/julia/RAG_new_stage7/out")
PRIVATE = Path("/Users/julia/RAG_new_stage7/private")
RECORD = WS / "reports" / "stage7" / "5e308fe"
# Stage 2's context judge: $12.164 for 130 requests; the survey's upper price a request.
COST_PER_REQUEST = (0.094, 0.21)
MEASURE_CODE = (
    *nr.MEASURE_CODE,
    "reports/no-rerank/tools/no_rerank_point.py",
    "reports/answer-prompt-v4/tools/v4_record.py",
    "reports/stage2/tools/judge_export.py",
    "utils/request_deadline.py",
    "agent/context_window.py",
    "agent/prompts.py",
    "agent/prompt_registry.py",
    "api/routers/conversation.py",
    "llm/providers/base.py",
    "llm/role_params.py",
    "config/settings.py",
    "ingestion/structure_graph.py",
    "ingestion/structure_graph_projection.py",
    "ingestion/entity_retrieval.py",
    "ingestion/entity_graph_loading.py",
    "vectordb/table_header.py",
    "vectordb/manager.py",
    "scripts/p1_adaptive_k.py",
    "scripts/context_judge.py",
    "scripts/chat_answer_judge.py",
    "evaluation/isolated_request.py",
)


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Store:
    """The vector store: the recorded vector lane of the question it is set to."""

    def __init__(self):
        self.lane, self.asked = [], []

    def similarity_search(self, query, k=None, **kwargs):
        self.asked.append((query, k, sorted(kwargs)))
        return list(self.lane)


class Lane:
    """The BM25 index: scores that rank the recorded BM25 lane in its order, and no other chunk."""

    def __init__(self, size):
        self.size, self.scores, self.calls = size, [0.0] * size, 0

    def set(self, members):
        self.scores = [0.0] * self.size
        for rank, member in enumerate(members):
            self.scores[member] = float(len(members) - rank)
        self.calls = 0

    def get_scores(self, tokens):
        self.calls += 1
        return self.scores


class Recorded:
    """The cross-encoder: each fused candidate's recorded score; another pool is refused."""

    def __init__(self):
        self.pairs, self.scores, self.calls, self.refused = [], [], 0, False

    def expect(self, question, texts, scores):
        self.pairs = [(question, text) for text in texts]
        self.scores, self.calls, self.refused = list(scores), 0, False

    def predict(self, pairs, batch_size=None):
        self.calls += 1
        if [tuple(pair) for pair in pairs] != self.pairs:
            # The product catches it into its fallback status; the replay reads it as a break.
            self.refused = True
            raise ValueError("the pool is not the recorded one")
        return list(self.scores)


@contextlib.contextmanager
def overlap_of(value):
    """Both expansions read the chunk overlap from get_settings() when they are called."""
    import config.settings as config

    real = config.get_settings
    setattr(config, "get_settings", lambda: SimpleNamespace(chunk_overlap=value))
    try:
        yield
    finally:
        config.get_settings = real


def structural_projection(docs, tenant):
    """The structural graph of a base's chunks, as vectordb.manager.get_retriever builds and
    projects it with graph retrieval on and no database: no entity graph."""
    from ingestion.entity_graph_loading import ENTITY_GRAPH_NO_DATABASE
    from ingestion.structure_graph import build_structural_graph
    from ingestion.structure_graph_projection import (
        project_structure_graph,
        structure_graph_digest,
    )

    graph = build_structural_graph(docs, tenant_id=tenant)
    projection = project_structure_graph(graph)
    projection.graph["entity_graph_status"] = ENTITY_GRAPH_NO_DATABASE
    try:
        projection.graph["digest"] = structure_graph_digest(graph)
    except Exception:
        # The factory's own rule: provenance must not break retrieval.
        projection.graph["digest"] = None
        projection.graph["entity_graph_status"] = "invalid"
    return projection


class Replay:
    """A base's chunks behind the product's retrievers, the recorded lists standing in for the
    index and the models: H and P read the hybrid retriever, S the one with the graph."""

    def __init__(self, chunks, settings, tenant, batch):
        from vectordb._base_manager import Document

        # The index stamps each chunk's archive position as its chunk_index.
        self.docs = [
            Document(page_content=c["page_content"], metadata={**c["metadata"], "chunk_index": i})
            for i, c in enumerate(chunks)
        ]
        self.chunks, self.settings, self.tenant, self.batch = chunks, settings, tenant, batch
        self.store, self.lane, self.reranker = Store(), Lane(len(self.docs)), Recorded()
        self.hybrid = self.retriever(None)
        self.structural, self.graph = None, None

    def retriever(self, projection):
        from vectordb._base_manager import HybridRetriever

        key_chars = self.settings["rrf_doc_key_chars"]
        made = HybridRetriever(
            vector_store=self.store,
            chunks=self.docs,
            retrieval_k=self.settings["retrieval_top_k"],
            rerank_k=self.settings["rerank_top_k"],
            rrf_k=self.settings["rrf_k"],
            # The settings snapshot masks a name holding "key"; every chunk has a source and an
            # index, so the fusion keys it by them and never reads the prefix length.
            doc_key_chars=key_chars if type(key_chars) is int else 200,
            reranker=self.reranker,
            use_bm25=False,
            parent_expansion=True,
            parent_expansion_window=self.settings["parent_expansion_window"],
            parent_expansion_max_chars=self.settings["parent_expansion_max_chars"],
            graph_projection=projection,
            rerank_batch=self.batch,
        )
        made._bm25 = self.lane
        return made

    def build_graph(self):
        """S's retriever; when the chunks build no graph, or no retriever over it, S is not read
        on the base."""
        try:
            projection = structural_projection(self.docs, self.tenant)
            self.structural = self.retriever(projection)
        except Exception as error:
            self.graph = {"error": type(error).__name__}
            return
        self.graph = {
            "digest": projection.graph.get("digest"),
            "entity_graph_status": projection.graph.get("entity_graph_status"),
            "nodes": projection.number_of_nodes(),
            "sections": len(self.structural._graph_section_chunks),
        }

    def stage(self, record):
        """The stand-ins set to one record's lists; the question the record asked."""
        pool = record["pool"] or []
        lanes = record["lanes"] or {"vector": [p[:2] for p in pool], "bm25": []}
        if not all(finite(p[2]) for p in pool):
            raise ValueError("a candidate has no recorded finite score")
        self.store.lane = [self.docs[position(x, self.chunks)] for x in lanes["vector"]]
        self.store.asked = []
        self.lane.set([position(x, self.chunks) for x in lanes["bm25"]])
        members = [position(p, self.chunks) for p in pool]
        self.reranker.expect(
            record["question"], [self.docs[m].page_content for m in members], [p[2] for p in pool]
        )
        return record["question"]

    def clean(self, question):
        """Whether the last search asked each stand-in once, for the question, and the pool held."""
        return (
            self.store.asked == [(question, self.settings["retrieval_top_k"], [])]
            and self.lane.calls == 1
            and self.reranker.calls == 1
            and not self.reranker.refused
        )

    def h(self, record):
        question = self.stage(record)
        with overlap_of(self.settings["chunk_overlap"]):
            docs, path = self.hybrid.get_relevant_documents_with_path(question)
        return docs, path, self.clean(question)

    def s(self, record):
        question = self.stage(record)
        with overlap_of(self.settings["chunk_overlap"]):
            docs, path = self.structural.get_graph_documents_with_path(question)
        return docs, path, self.clean(question)

    def p(self, h_docs, scores):
        """P1b's documents: H's first kept_count seeds, expanded; and that count."""
        k = kept(scores)
        if k == len(h_docs):
            return h_docs, k
        seeds = [self.docs[d.metadata["chunk_index"]] for d in h_docs[:k]]
        with overlap_of(self.settings["chunk_overlap"]):
            return self.hybrid._expand_parents(seeds), k


def kept(scores):
    """How many of the five P1b keeps: the rule's family "rel" at 0.2 on the probabilities."""
    from scripts.p1_adaptive_k import kept_count

    return kept_count("rel", REL, list(scores), list(scores))


class Builder:
    """The chat's prompt of a question and documents under V3 or V4, flattened as the provider
    sends it, at V4's input limit; and the documents it holds."""

    def __init__(self):
        import agent.prompts as prompts
        from agent.context_window import prompt_input_limit
        from api.routers.conversation import _fit_stream_prompt
        from llm.providers.base import estimate_window_tokens, flatten_messages
        from scripts.chat_answer_judge import PROMPT_IDS

        self.prompts, self.fit = prompts, _fit_stream_prompt
        self.flatten, self.estimate = flatten_messages, estimate_window_tokens
        self.owner = SimpleNamespace(context_window=WINDOW)
        self.texts = {"v3": v4_record.V3_TEMPLATE, "v4": v4_record.V4_TEMPLATE}
        self.marks = {"v3": PROMPT_IDS[V3_ID], "v4": PROMPT_IDS[V4_ID]}
        registry = prompts.PROMPT_REGISTRY["qa"]
        if registry["text"] != self.texts["v4"] or registry.get("prompt_id") != V4_ID:
            raise SystemExit("the checkout's qa prompt is not V4")
        for version, other in (("v3", "v4"), ("v4", "v3")):
            if (
                self.marks[version] not in self.texts[version]
                or self.marks[version] in (self.texts[other])
            ):
                raise SystemExit("V3's and V4's citation sentences do not tell them apart")
        if prompt_input_limit(self.owner, "generate") != LIMIT:
            raise SystemExit(f"the model's input limit is not V4's {LIMIT} tokens")
        self.cache = {}

    def __call__(self, version, question, docs):
        plain = [{"page_content": d.page_content, "metadata": d.metadata or {}} for d in docs]
        plain = plain[:TOP]
        key = (
            version,
            question,
            json.dumps([[p["page_content"], p["metadata"]] for p in plain], default=str),
        )
        if key not in self.cache:
            registry = self.prompts.PROMPT_REGISTRY["qa"]
            registry["text"] = self.texts[version]
            try:
                prompt, fitted = self.fit(self.owner, question, plain, [])
            finally:
                registry["text"] = self.texts["v4"]
            if self.marks[version] not in prompt:
                raise SystemExit("the chat built its prompt from another text than the one given")
            sent = [
                {
                    "source": d["metadata"].get("source"),
                    "chunk_index": d["metadata"].get("chunk_index"),
                    "text": d["page_content"],
                    "cut": d["page_content"] != plain[i]["page_content"],
                }
                for i, d in enumerate(fitted)
            ]
            self.cache[key] = (self.flatten([{"role": "user", "content": prompt}]), sent)
        flat, sent = self.cache[key]
        # Copies: what a caller does to them must not reach the next call's documents.
        return flat, [dict(s) for s in sent]


def meta_of(chunks, at):
    return {**chunks[at]["metadata"], "chunk_index": at}


def run_members(text, seed, chunks, overlap):
    """The chunks a section-expanded document was joined from: one run of its document's
    chunks around the seed, joined as the section expansion joins them (vectordb.parent_join).

    No run gives exactly the text: ValueError, the text is not a section run of its seed.
    """
    from evaluation import external_gold as gold
    from vectordb import contextual_header, parent_join

    own = chunks[seed]["page_content"]
    if text == own:
        return [seed]
    source = chunks[seed]["metadata"].get("source")
    header, own_body = contextual_header.split(own, meta_of(chunks, seed))

    def piece(at):
        meta = meta_of(chunks, at)
        body = own_body if at == seed else gold.strip_header(chunks[at]["page_content"], meta)
        return at, body.strip(), meta

    def same(at):
        return 0 <= at < len(chunks) and chunks[at]["metadata"].get("source") == source

    start = seed
    while same(start):
        lead = parent_join.join(header, [piece(at) for at in range(start, seed + 1)], overlap)
        if len(lead) > len(text):
            break
        end = seed
        while same(end):
            joined = parent_join.join(header, [piece(at) for at in range(start, end + 1)], overlap)
            if joined == text:
                return list(range(start, end + 1))
            if len(joined) > len(text):
                break
            end += 1
        start -= 1
    raise ValueError(f"the text is not a section run of chunk {seed}")


def members_of(arm, docs, chunks, settings):
    """The chunks each document was joined from: H's and P's by external_gold's reading of a
    parent expansion, S's by run_members."""
    from evaluation import external_gold as gold

    out = []
    for doc in docs:
        seed = doc.metadata.get("chunk_index")
        if type(seed) is not int or not 0 <= seed < len(chunks):
            raise ValueError("a document names no chunk of the archive")
        if arm == "S":
            out.append(run_members(doc.page_content, seed, chunks, settings["chunk_overlap"]))
        else:
            out.append(
                gold.expansion_members(
                    doc.page_content,
                    seed,
                    chunks,
                    settings["parent_expansion_window"],
                    settings["chunk_overlap"],
                )
            )
    return out


def sent_point(base, case, sent, members, gold_of):
    """M3 of the documents the fitting sent, as retrieval_summary.coverage reads «sent»: a whole
    document holds the chunks it was joined from; one cut to an excerpt holds the places of its
    paragraphs found among them (WixQA: its article, when the excerpt shows a character)."""
    from evaluation import external_gold as gold
    from scripts.external_pilot import read_gold

    places, sources, chunks = gold_of["places"], gold_of["sources"], gold_of["chunks"]
    held, extra, missed = [], [], 0
    # The fitting keeps leading documents: what it sent is a prefix of the documents.
    for doc, joined in zip(sent, members, strict=False):
        if not doc["cut"]:
            held += joined
        elif sources is None:
            if gold.visible(doc["text"])[0]:
                held.append(doc["chunk_index"])
        else:
            found, lost = excerpt_places(
                doc["text"], joined, doc["chunk_index"], places, sources, chunks
            )
            extra += found
            missed += lost
    return read_gold(base, case, held, Excerpted(places, extra)), missed


def points(base, case, sent, members, gold_of):
    """The arm's M3 at «expanded» and «sent»; ValueError when a point cannot be read."""
    from scripts.external_pilot import read_gold

    joined = [m for each in members for m in each]
    expanded = read_gold(base, case, joined, gold_of["places"])
    at_sent, missed = sent_point(base, case, sent, members, gold_of)
    return {"expanded": expanded, "sent": at_sent}, missed


def described(docs):
    return [
        {
            "source": d.metadata.get("source"),
            "chunk_index": d.metadata.get("chunk_index"),
            "text": d.page_content,
        }
        for d in docs
    ]


def h_breaks(record, docs, path, clean, chunks):
    """What H's replay gives other than the record: the stand-ins, the path, the five, the
    expansion; an empty list is parity."""
    breaks = [] if clean else ["stand_ins"]
    if path.get("rerank_status") != "ok":
        breaks.append("rerank_status")
    # The record holds the path as JSON: tuples came back as lists.
    path = json.loads(json.dumps(path))
    breaks += [key for key in PATH_KEYS if path.get(key) != record["path"].get(key)]
    five = [position(r, chunks) for r in record["ranked"]]
    if [d.metadata.get("chunk_index") for d in docs] != five or path.get("rerank_scores") != [
        r[2] for r in record["ranked"]
    ]:
        breaks.append("ranked")
    if described(docs) != record["expanded"]:
        breaks.append("expanded")
    return breaks


def v4_rows(label):
    """V4's committed rows of a key, held to V4's record: {case_id: row}."""
    name = f"reports/answer-prompt-v4/4f48fed/v4-{V4_KEYS[label]}.cases.jsonl"
    if sha256(V4_DIR / "v4-record.json") != V4_RECORD_SHA256:
        raise SystemExit("v4-record.json is not the record the spec froze")
    record = json.loads((V4_DIR / "v4-record.json").read_text(encoding="utf-8"))
    if record.get("stand") != V4_STAND or record.get("stage2") != CODE_SHA:
        raise SystemExit("V4's record is not of the stands this replay reads")
    if sha256(WS / name) != record["inputs"].get(name):
        raise SystemExit(f"{name} is not the file V4's record read")
    rows = {}
    for row in load_jsonl(WS / name):
        if row["case_id"] in rows or row.get("answered") is not True or len(row["prompts"]) != 1:
            raise SystemExit(f"{row['case_id']}: not one answered V4 case with one stream prompt")
        rows[row["case_id"]] = row
    return rows


def v4_prompt(v4_runs, row):
    """V4's saved stream prompt of a case: the file its row names, by its hash; else None."""
    path = Path(v4_runs) / row["run"] / "prompts" / row["prompts"][0]["file"]
    try:
        # Bytes, not read_text: its newline translation would hand the gate other white space.
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    if "\r" in text or digest(text) != row["prompts"][0]["sha256"]:
        return None
    return text


def control():
    """The checkout's control, as get_settings() builds it with no experiment selected, without
    its directories: another K, window or reranker runtime changes H, and the replay then needs a
    registered amendment."""
    import config.settings as config

    if (os.getenv("EXPERIMENT_ID", "") or "").strip():
        raise SystemExit("the checkout's control is an experiment's: EXPERIMENT_ID is set")
    built = config.Settings()
    config._apply_deployed_settings(built)
    got = {key: getattr(built, key) for key in CONTROL}
    if got != CONTROL:
        raise SystemExit(f"the checkout's control is {got}, not the spec's {CONTROL}")
    return got


def export_manifest():
    if sha256(EXPORT / "manifest.json") != EXPORT_MANIFEST_SHA256:
        raise SystemExit("the export's manifest is not the one the spec froze")
    manifest = json.loads((EXPORT / "manifest.json").read_text(encoding="utf-8"))
    if manifest["code_sha"] != CODE_SHA:
        raise SystemExit("the export is not of the stand the records are")
    return manifest


def run_inputs(label, args, manifest):
    """One run's records, settings and provenance, its base's archive and gold, the export's
    rows and V4's, each held to the others."""
    base = LABELS[label]
    run = args.runs / label
    launch = json.loads((run / "launch.json").read_text(encoding="utf-8"))
    if launch.get("status") != "complete" or launch.get("code_sha") != CODE_SHA:
        raise SystemExit(f"{label}: not a complete run of {CODE_SHA}: NOT_EVIDENCE")
    effective = json.loads((run / "effective_settings.json").read_text(encoding="utf-8"))
    settings = effective["all"]
    path = {
        "rerank_top_k": TOP,
        "retrieval_top_k": KMAX,
        "parent_expansion": True,
        "hybrid_search": True,
        "retrieval_strategy": "hybrid",
    }
    if any(settings.get(key) != value for key, value in path.items()):
        raise SystemExit(f"{label}: not stage 2's hybrid path at K {KMAX} and the five")
    if sha256(EXPORT / f"{label}.json") != manifest["files"][f"{label}.json"]:
        raise SystemExit(f"{label}.json is not the file the export's manifest names")
    exported = json.loads((EXPORT / f"{label}.json").read_text(encoding="utf-8"))["provenance"]
    archive, names = source_names(args.data_root, base)
    chunks = archive["chunks"]
    receipt = json.loads(
        (args.data_root / base / "index" / "index-receipt.json").read_text(encoding="utf-8")
    )
    archive_sha = sha256(args.data_root / base / "chunks.json.gz")
    if not (
        receipt.get("corpus_sha256") == exported.get("archive_sha256") == archive_sha
        and archive_sha == ARCHIVES[base]
    ):
        raise SystemExit(f"{base}: the chunk archive is not the one the index and export read")
    if (exported.get("window") or {}).get("context_window") != WINDOW:
        raise SystemExit(f"{label}: the export's prompts were not fitted to a {WINDOW} window")
    # retrieval_summary.py's hash of the public settings, and of the questions' file.
    public = json.dumps(effective["settings"], sort_keys=True).encode()
    if hashlib.sha256(public).hexdigest() != exported.get("settings_sha256") or sha256(
        Path(launch["cases_file"])
    ) != exported.get("cases_file_sha256"):
        raise SystemExit(f"{label}: the run's settings or questions are not the ones exported")
    records = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted((run / "retrieval").glob("*.json"))
    ]
    committed = nr.export_rows(label, manifest)
    if sorted(r["case_id"] for r in records) != sorted(committed):
        raise SystemExit(f"{label}: the records are not the export's questions")
    batches = {json.dumps(r["path"].get("rerank_batch_effective")) for r in records}
    if len(batches) != 1:
        raise SystemExit(f"{label}: the records ran at more than one rerank batch")
    gold_of, cases = None, {}
    if base in nr.METRICS:
        from evaluation import external_bases as bases
        from evaluation import external_parts as parts
        from scripts import external_base
        from scripts.external_pilot import Places, gold_documents

        converted = bases.registration()
        cases = {
            c["case_id"]: c
            for c in parts.load_cases(args.data_root / base, base, converted)
            if gold_documents(base, c)
        }
        sources = None if base == "wixqa" else external_base._corpus(args.data_root / base)[1]
        places = Places(
            chunks,
            sources,
            converted["chunking"]["chunk_overlap"],
            settings["parent_expansion_window"],
        )
        gold_of = {"places": places, "sources": sources, "chunks": chunks}
        with_points = {c for c, row in committed.items() if "points" in row}
        if with_points != {r["case_id"] for r in records if r["case_id"] in cases}:
            raise SystemExit(f"{label}: the questions with gold are not the export's")
    kept_settings = {
        key: settings[key]
        for key in (
            "retrieval_top_k",
            "rerank_top_k",
            "rrf_k",
            "rrf_doc_key_chars",
            "chunk_overlap",
            "parent_expansion_window",
            "parent_expansion_max_chars",
        )
    }
    provenance = {
        "label": label,
        "base": base,
        "code_sha": launch["code_sha"],
        "tenant": launch.get("tenant"),
        "settings": kept_settings,
        "rerank_batch_effective": json.loads(batches.pop()),
        "archive_sha256": archive_sha,
        "cases_file_sha256": sha256(Path(launch["cases_file"])),
        "launch_sha256": sha256(run / "launch.json"),
        "effective_settings_sha256": sha256(run / "effective_settings.json"),
        "records": len(records),
        "with_gold": len(cases),
    }
    return {
        "label": label,
        "base": base,
        "tenant": launch.get("tenant") or "default",
        "launch": launch,
        "records": records,
        "committed": committed,
        "chunks": chunks,
        "names": names,
        "cases": cases,
        "gold_of": gold_of,
        "settings": kept_settings,
        "batch": provenance["rerank_batch_effective"],
        "provenance": provenance,
        "questions": [r["query"] for r in load_jsonl(Path(launch["cases_file"]))],
        "v4": v4_rows(label) if label in V4_KEYS else {},
        "v4_runs": args.v4_runs,
    }


def h_parity(inputs, record, replay, builder):
    """H on one record: its parity row and what the arms read (H's documents, V4's prompt)."""
    case_id = record["case_id"]
    row = {"label": inputs["label"], "case_id": case_id, "index": record["index"]}
    try:
        docs, path, clean = replay.h(record)
    except ValueError:
        return {**row, "breaks": ["stand_ins"]}, None
    breaks = h_breaks(record, docs, path, clean, inputs["chunks"])
    flat3, sent3 = builder("v3", record["question"], docs)
    exported = inputs["committed"][case_id]["prompt"]["sha256"]
    if flat3 != record["prompt"]["text"]:
        breaks.append("v3_prompt")
    if not digest(flat3) == record["prompt"]["sha256"] == exported:
        breaks.append("v3_sha256")
    if sent3 != record["sent"]:
        breaks.append("v3_sent")
    flat4, sent4 = builder("v4", record["question"], docs)
    v4_row = inputs["v4"].get(case_id)
    row["v4_saved"] = v4_row is not None
    if v4_row is not None:
        saved = v4_prompt(inputs["v4_runs"], v4_row)
        if saved is None:
            breaks.append("v4_saved")
        elif flat4 != saved:
            breaks.append("v4_prompt")
    case = inputs["cases"].get(case_id)
    if case is not None and not breaks:
        # The export's points, read again from what H gave under V3.
        try:
            members = members_of("H", docs, inputs["chunks"], inputs["settings"])
            got, missed = points(inputs["base"], case, sent3, members, inputs["gold_of"])
        except ValueError:
            got, missed = None, None
        committed = inputs["committed"][case_id]
        if got is None or (got["expanded"], got["sent"], missed) != (
            committed["points"]["expanded"],
            committed["points"]["sent"],
            committed["excerpt_pieces_missed"],
        ):
            breaks.append("recount")
    row["breaks"] = breaks
    return row, {"docs": docs, "path": path, "flat": flat4, "sent": sent4}


def arm_entry(arm, docs, flat, sent, inputs, builder, case):
    """One arm on one question: its documents, what it sent, its prompt, its M3 points."""
    entry = {
        "documents": len(docs),
        "chars": sum(len(d.page_content) for d in docs),
        "sent_documents": len(sent),
        "sent_chars": sum(len(s["text"]) for s in sent),
        "sent_est_tokens": sum(builder.estimate(s["text"]) for s in sent),
        "cut": any(s["cut"] for s in sent),
        "prompt": {
            "sha256": digest(flat),
            "chars": len(flat),
            "est_tokens": builder.estimate(flat),
        },
        "chunks": None,
        "sent_chunks": None,
        "unresolved": None,
    }
    try:
        members = members_of(arm, docs, inputs["chunks"], inputs["settings"])
    except ValueError:
        entry["unresolved"] = "members"
        return entry
    entry["chunks"] = sum(len(m) for m in members)
    entry["sent_chunks"] = sum(len(m) for m in members[: len(sent)])
    if case is not None:
        try:
            entry["points"], entry["excerpt_pieces_missed"] = points(
                inputs["base"], case, sent, members, inputs["gold_of"]
            )
        except ValueError:
            entry["unresolved"] = "points"
    return entry


def arms_row(inputs, record, h, replay, builder, texts):
    """H, S and P on one question that passed the gate: the row, and its texts for the judge."""
    case_id = record["case_id"]
    case = inputs["cases"].get(case_id)
    row = {
        "label": inputs["label"],
        "base": inputs["base"],
        "case_id": case_id,
        "index": record["index"],
        "gold": case is not None,
        "stratum": None if case is None else case.get("stratum"),
        "v4_saved": case_id in inputs["v4"],
    }
    flats = {"H": h["flat"]}
    row["H"] = arm_entry("H", h["docs"], h["flat"], h["sent"], inputs, builder, case)
    five = [d.metadata["chunk_index"] for d in h["docs"]]
    if replay.structural is None:
        row["S"] = None
    else:
        docs, path, clean = replay.s(record)
        expected = {**h["path"]["candidates"], "entity": 0}
        if (
            not clean
            or path is None
            or path.get("rerank_status") != "ok"
            or path.get("candidates") != expected
        ):
            raise SystemExit(f"{inputs['label']}/{case_id}: S did not read H's pool: NOT_EVIDENCE")
        seeds = [d.metadata["chunk_index"] for d in docs]
        if not set(seeds) <= set(five):
            raise SystemExit(f"{inputs['label']}/{case_id}: S kept a seed outside H's five")
        flat, sent = builder("v4", record["question"], docs)
        flats["S"] = flat
        row["S"] = {
            **arm_entry("S", docs, flat, sent, inputs, builder, case),
            "seeds": len(seeds),
            "dropped": len(path["dropped"]),
            "order_changed": seeds != [s for s in five if s in seeds],
            "section_expanded": path["expanded_contexts"],
            "changed": flat != h["flat"],
        }
    docs, k = replay.p(h["docs"], h["path"]["rerank_scores"])
    flat, sent = builder("v4", record["question"], docs)
    flats["P"] = flat
    row["P"] = {
        **arm_entry("P", docs, flat, sent, inputs, builder, case),
        "kept": k,
        "changed": flat != h["flat"],
    }
    if inputs["label"] in AIRCARGO:
        texts[(inputs["label"], case_id)] = {"question": record["question"], **flats}
    return row


def read(row, arm):
    """Whether a question is read in the pair of H and an arm: gold, both points resolved."""
    return (
        row["gold"]
        and row.get(arm) is not None
        and row["H"]["unresolved"] is None
        and row[arm]["unresolved"] is None
    )


def pair(rows, arm, point):
    """H against an arm at one point, by each question's primary metric: the no-reranker
    point's pair, b - gold with H only, c - gold with the arm only."""
    view = [
        {"base": r["base"], "points": {"H": r["H"]["points"][point], arm: r[arm]["points"][point]}}
        for r in rows
        if read(r, arm)
    ]
    return {RENAMED.get(key, key): value for key, value in nr.pair(view, "H", arm).items()}


def unread(rows, arm):
    return sum(1 for r in rows if r["gold"] and not read(r, arm))


def readings(rows, arm, not_evidence):
    """The pair at «sent», which is read, and at «expanded», which stands beside."""
    if not_evidence:
        return {"sent": NOT_EVIDENCE, "expanded": NOT_EVIDENCE}
    return {"sent": pair(rows, arm, "sent"), "expanded": pair(rows, arm, "expanded")}


def external(rows, graphs):
    """Each arm against H on each external base, on the two deciding bases pooled and on the
    three pooled; a base where the arm leaves more than MAX_UNREAD questions unread, or where S
    has no graph, is NOT_EVIDENCE, and so is each pool holding it."""
    out = {}
    for arm in ARMS:
        per_base, failed = {}, set()
        for base in EXTERNAL:
            mine = [r for r in rows if r["base"] == base]
            missing = arm == "S" and graphs.get(base, {}).get("error") is not None
            if missing or unread(mine, arm) > MAX_UNREAD:
                failed.add(base)
            per_base[base] = {
                "with_gold": sum(1 for r in mine if r["gold"]),
                "unread": None if missing else unread(mine, arm),
                **readings(mine, arm, base in failed),
            }
        pools = {"deciding": DECIDING, "all_three": EXTERNAL}
        pooled = {
            name: readings(
                [r for r in rows if r["base"] in held], arm, bool(failed.intersection(held))
            )
            for name, held in pools.items()
        }
        out[arm] = {"per_base": per_base, "pooled": pooled}
    return out


def external_stops(got):
    """An arm's stop readings on the external bases: each deciding base, and the two pooled."""
    stops = {base: got["per_base"][base]["sent"] for base in DECIDING}
    stops["pooled_deciding"] = got["pooled"]["deciding"]["sent"]
    return stops


def standing(stops):
    """An arm on its stop readings: a detected loss stops it; else one not evidence leaves it
    NOT_EVIDENCE; else it is open."""
    values = list(stops.values())
    if any(isinstance(v, dict) and v["reading"] == "loss" for v in values):
        return "stopped"
    if NOT_EVIDENCE in values:
        return NOT_EVIDENCE
    return "open"


def gained(stops):
    """Where an arm's stop readings detect an M3 gain over H."""
    return sorted(
        where for where, got in stops.items() if isinstance(got, dict) and got["reading"] == "gain"
    )


def above_mde(b, c):
    """PLAN's «больше MDE» (§4.4): a gain c - b larger than MDE_Z standard errors of the paired
    difference, sqrt(b + c); exact, in fractions. It holds a detection too: the exact McNemar
    p is at most 0.008 at its edge."""
    return c > b and (c - b) ** 2 > MDE_Z**2 * (b + c)


def qualifies(stops):
    """An M3 gain at the two deciding bases pooled, detected and larger than the MDE; a gain at
    one base alone, or aircargo's, qualifies no arm."""
    got = stops[QUALIFIES_AT]
    return (
        isinstance(got, dict)
        and got["reading"] == "gain"
        and above_mde(got["b_h_only"], got["c_arm_only"])
    )


def candidates(stops):
    """The arms answers may open for: no detected loss, every stop reading evidence, the pooled
    gain above the MDE. On the external bases' stops these are the arms the aircargo judge
    reads."""
    return [arm for arm in ARMS if standing(stops[arm]) == "open" and qualifies(stops[arm])]


def decision(stops):
    """Gate G1, PLAN's: answers only for the best arm and only on an M3 gain above the MDE. One
    arm goes on: the one that qualifies alone; of two, the larger gain at the deciding bases
    pooled (c - b), P on a tie. None: «H stays», and stage 7 closes; NOT_EVIDENCE while an arm
    without a loss cannot be read."""
    standings = {arm: standing(stops[arm]) for arm in ARMS}
    gains = {arm: gained(stops[arm]) for arm in ARMS}
    qualifying = candidates(stops)
    if qualifying:

        def margin(arm):
            got = stops[arm][QUALIFIES_AT]
            return got["c_arm_only"] - got["b_h_only"]

        chosen = max(qualifying, key=lambda arm: (margin(arm), arm == "P"))
        reading = f"{chosen} opens answers"
    else:
        chosen = None
        reading = NOT_EVIDENCE if NOT_EVIDENCE in standings.values() else "H stays"
    return {"standings": standings, "gains": gains, "arm": chosen, "reading": reading}


def label_summary(rows, graph):
    """A run's spreads per arm and how many prompts each arm changes."""
    out = {"questions": len(rows), "v4_saved": sum(1 for r in rows if r["v4_saved"])}
    for arm in ("H", *ARMS):
        got = [r[arm] for r in rows if r.get(arm) is not None]
        if not got:
            out[arm] = None
            continue
        out[arm] = {
            "questions": len(got),
            "documents": spread([g["documents"] for g in got]),
            "chunks": spread([g["chunks"] for g in got]),
            "sent_documents": spread([g["sent_documents"] for g in got]),
            "sent_chunks": spread([g["sent_chunks"] for g in got]),
            "sent_est_tokens": spread([g["sent_est_tokens"] for g in got]),
            "prompt_est_tokens": spread([g["prompt"]["est_tokens"] for g in got]),
            "cut": sum(1 for g in got if g["cut"]),
            "unresolved": dict(Counter(str(g["unresolved"]) for g in got)),
        }
        if arm != "H":
            out[arm]["prompt_changed"] = sum(1 for g in got if g["changed"])
            out[arm]["prompt_changed_on_v4"] = sum(
                1 for r in rows if r.get(arm) is not None and r[arm]["changed"] and r["v4_saved"]
            )
    if out["P"] is not None:
        out["P"]["kept"] = dict(sorted(Counter(r["P"]["kept"] for r in rows).items()))
    if out["S"] is not None:
        got = [r["S"] for r in rows if r.get("S") is not None]
        out["S"]["seeds"] = dict(sorted(Counter(g["seeds"] for g in got).items()))
        out["S"]["order_changed"] = sum(1 for g in got if g["order_changed"])
        out["S"]["section_expanded"] = spread([g["section_expanded"] for g in got])
    out["graph"] = graph
    return out


def put_trees(trees):
    """Trees {root: {name: text}}, written once: a tree already there must hold these files and
    texts, and every tree is checked before any is written."""
    missing = []
    for root, files in trees.items():
        root = Path(root)
        wanted = {name: text.encode("utf-8") for name, text in files.items()}
        if not root.exists():
            missing.append((root, wanted))
            continue
        held = {
            p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()
        }
        if held != wanted:
            raise SystemExit(f"{root} holds another plan's files: a plan is frozen once written")
    for root, wanted in missing:
        for name, data in wanted.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)


def put_tree(root, files):
    """Files under root, written once: a tree already there must hold these files and texts."""
    put_trees({root: files})


def judge_runs(rows, open_arms):
    """The aircargo runs the context judge reads: H's prompts, then each open arm's prompts that
    differ from every prompt already planned for the question; {run: [(row, arm)]}."""
    runs = {}
    for label in AIRCARGO:
        mine = [r for r in rows if r["label"] == label]
        planned = {r["case_id"]: {r["H"]["prompt"]["sha256"]} for r in mine}
        runs[f"H-{label}"] = [(r, "H") for r in mine]
        for arm in ARMS:
            if arm not in open_arms:
                continue
            runs[f"{arm}-{label}"] = []
            for r in mine:
                sha = r[arm]["prompt"]["sha256"]
                if sha not in planned[r["case_id"]]:
                    planned[r["case_id"]].add(sha)
                    runs[f"{arm}-{label}"].append((r, arm))
    return {name: taken for name, taken in runs.items() if taken}


def judge_plan(private, runs, texts, launches, estimate):
    """PRIVATE/runs/RUN as live_retrieval.py lays a run out (a retrieval record a question, the
    prompt the chat would send) and PRIVATE/judge/plan.json, context_judge.build_plan's, built in
    a staging folder that goes with it: the trees to write, the plan and its hash. Nothing is
    left under PRIVATE until the caller puts the trees."""
    from scripts import context_judge

    files = {}
    for name, taken in runs.items():
        label = name.split("-", 1)[1]
        launch = {**launches[label], "arm": name.split("-", 1)[0], "label": name}
        files[name] = {"launch.json": json.dumps(launch, ensure_ascii=False, indent=1) + "\n"}
        for row, arm in taken:
            entry = texts[(row["label"], row["case_id"])]
            flat = entry[arm]
            record = {
                "case_id": row["case_id"],
                "index": row["index"],
                "question": entry["question"],
                "prompt": {
                    "sha256": digest(flat),
                    "chars": len(flat),
                    "est_tokens": estimate(flat),
                    "text": flat,
                },
            }
            files[name][f"retrieval/{row['index']:03d}-{row['case_id']}.json"] = (
                json.dumps(record, ensure_ascii=False, indent=1) + "\n"
            )
    private.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=private, prefix=".staging-") as staging:
        for name, held in files.items():
            put_tree(Path(staging) / name, held)
        plan = context_judge.build_plan(
            {name: Path(staging) / name for name in files}, retest=context_judge.RETEST_SIZE
        )
    text = json.dumps(plan, ensure_ascii=False, indent=1) + "\n"
    trees = {private / "runs" / name: held for name, held in files.items()}
    trees[private / "judge"] = {"plan.json": text}
    return trees, plan, digest(text)


def plan_size(plan):
    items = plan["items"]
    asked = sum(1 for item in items if "message" in item)
    retests = sum(1 for item in items if "retest_of" in item)
    return {
        "requests": asked,
        "first_requests": asked - retests,
        "retests": retests,
        "empty_contexts": sum(1 for item in items if item.get("empty_context")),
        "by_run": dict(Counter(item["run"] for item in items if "retest_of" not in item)),
        "cost_usd": [round(asked * price, 2) for price in COST_PER_REQUEST],
    }


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", "utf-8", newline="\n")


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), "utf-8", newline="\n"
    )


def replay(args):
    """The parity gate, then the arms, the external readings and the aircargo judge plan."""
    held_control = control()
    manifest = export_manifest()
    builder = Builder()
    parity, rows, provenance, graphs, labels = [], [], {}, {}, {}
    texts, launches, names, questions = {}, {}, set(), []
    failed, current = False, None
    for label in LABELS:
        inputs = run_inputs(label, args, manifest)
        if not set(inputs["v4"]) <= {r["case_id"] for r in inputs["records"]}:
            raise SystemExit(f"{label}: a question V4 answered is not among the records")
        provenance[label] = inputs["provenance"]
        names |= inputs["names"]
        questions += inputs["questions"]
        launches[label] = {
            "code_sha": nr.git_head(),
            "stand_code_sha": CODE_SHA,
            "tenant": inputs["launch"].get("tenant"),
            "chroma_dir": None,
            "cases_file": inputs["launch"].get("cases_file"),
            "status": "complete",
        }
        key = (inputs["base"], json.dumps(inputs["settings"], sort_keys=True), inputs["batch"])
        if current is None or current[0] != key:
            current = (
                key,
                Replay(inputs["chunks"], inputs["settings"], inputs["tenant"], inputs["batch"]),
            )
        machine = current[1]
        checked = [(r, *h_parity(inputs, r, machine, builder)) for r in inputs["records"]]
        parity += [row for _, row, _ in checked]
        failed = failed or any(row["breaks"] for _, row, _ in checked)
        if failed:
            continue
        if machine.graph is None:
            machine.build_graph()
        graphs[inputs["base"]] = machine.graph
        mine = [arms_row(inputs, r, h, machine, builder, texts) for r, _, h in checked]
        labels[label] = label_summary(mine, machine.graph)
        rows += mine
    gate = {
        "questions": len(parity),
        "passed": sum(1 for row in parity if not row["breaks"]),
        "v4_saved": sum(1 for row in parity if row.get("v4_saved")),
        "v4_byte_equal": sum(
            1
            for row in parity
            if row.get("v4_saved") and not {"v4_saved", "v4_prompt"} & set(row["breaks"])
        ),
        "breaks": dict(Counter(b for row in parity for b in row["breaks"])),
    }
    without_text(parity, names, questions)
    if failed:
        write_rows(args.out / "parity.jsonl", parity)
        print(json.dumps({"parity": gate}, indent=1))
        print("the parity gate failed: no arm is read", file=sys.stderr)
        return 3
    if gate["v4_saved"] != V4_SAVED:
        raise SystemExit(f"{gate['v4_saved']} of V4's questions read, not the {V4_SAVED}")
    reads = external([r for r in rows if r["base"] in EXTERNAL], graphs)
    stops = {arm: external_stops(reads[arm]) for arm in ARMS}
    open_arms = []
    for arm in candidates(stops):
        if any(r.get(arm) is None for r in rows if r["label"] in AIRCARGO):
            # S without a graph of aircargo's chunks: the readings that could stop it cannot be
            # had, so it is not planned.
            stops[arm].update({f"aircargo_{name}": NOT_EVIDENCE for name in HITS})
        else:
            open_arms.append(arm)
    changed = {
        arm: sum(1 for r in rows if r.get(arm) is not None and r[arm]["changed"] and r["v4_saved"])
        for arm in ARMS
    }
    judge, trees = None, {}
    if open_arms:
        trees, plan, plan_sha = judge_plan(
            args.private, judge_runs(rows, open_arms), texts, launches, builder.estimate
        )
        judge = {"arms": open_arms, "plan_sha256": plan_sha, **plan_size(plan)}
    record = {
        "spec": SPEC,
        "stand_code_sha": CODE_SHA,
        "v4_stand_code_sha": V4_STAND,
        "measured_at_head": nr.git_head(),
        "inputs": {
            "runs": str(args.runs),
            "data_root": str(args.data_root),
            "v4_runs": str(args.v4_runs),
            "export": str(EXPORT.relative_to(WS)),
            "export_manifest_sha256": sha256(EXPORT / "manifest.json"),
            "v4_record_sha256": sha256(V4_DIR / "v4-record.json"),
        },
        "tool_sha256": sha256(Path(__file__)),
        "measure_code_sha256": {n: sha256(WS / n) for n in MEASURE_CODE},
        "control": held_control,
        "frozen": {
            "k": KMAX,
            "five": TOP,
            "window": WINDOW,
            "input_limit": LIMIT,
            "p_rule": ["rel", REL],
            "alpha": nr.ALPHA,
            "max_unread": MAX_UNREAD,
            "max_missing": MAX_MISSING,
            "deciding": list(DECIDING),
            "qualifies_at": QUALIFIES_AT,
            "mde_z": float(MDE_Z),
            "v4_saved": V4_SAVED,
        },
        "provenance": provenance,
        "parity": gate,
        "labels": labels,
        "external": reads,
        "stops": stops,
        "changed_on_v4": changed,
        "judge": judge,
        "decision": "pending the aircargo context judge" if open_arms else decision(stops),
    }
    without_text(record, names, questions)
    without_text(rows, names, questions)
    # The plan only beside a record that passed: a refused record leaves no plan.
    put_trees(trees)
    write_json(args.out / "record.json", record)
    write_rows(args.out / "rows.jsonl", rows)
    write_rows(args.out / "parity.jsonl", parity)
    for arm in ARMS:
        for where, got in stops[arm].items():
            if isinstance(got, dict):
                print(
                    f"{arm} {where}: H {got['hits']['H']}, {arm} {got['hits'][arm]} of {got['n']},"
                    f" b {got['b_h_only']}, c {got['c_arm_only']}, p {got['p']}, {got['reading']}"
                )
            else:
                print(f"{arm} {where}: {got}")
    print(json.dumps({"parity": gate, "judge": judge, "decision": record["decision"]}, indent=1))
    return 0


def aircargo_pairs(levels, arm, cases):
    """H against an arm on aircargo, on «full» and on «full or partial», both runs pooled and
    each beside; a question without a counted level on either side is left out."""
    out = {}
    for name, hits in HITS.items():
        out[name] = {}
        for where, held in (("pooled", AIRCARGO), *((label, (label,)) for label in AIRCARGO)):
            both = [
                (levels[("H", c)], levels[(arm, c)])
                for c in cases
                if c[0] in held and levels[("H", c)] is not None and levels[(arm, c)] is not None
            ]
            b = sum(1 for h, a in both if h in hits and a not in hits)
            c = sum(1 for h, a in both if a in hits and h not in hits)
            p = nr.mcnemar(b, c)
            out[name][where] = {
                "n": len(both),
                "hits": {
                    "H": sum(1 for h, _ in both if h in hits),
                    arm: sum(1 for _, a in both if a in hits),
                },
                "b_h_only": b,
                "c_arm_only": c,
                "p": round(p, 6),
                "reading": nr.reading(b, c, p),
            }
    return out


def judged(args):
    """The aircargo half of G1 from the plan's verdicts, and the gate's decision."""
    sys.path.insert(0, str(WS / "reports" / "stage2" / "tools"))
    import judge_export as je

    from scripts import context_judge

    record = json.loads((args.record / "record.json").read_text(encoding="utf-8"))
    rows = load_jsonl(args.record / "rows.jsonl")
    if not record.get("judge"):
        raise SystemExit("the replay planned no judge: its decision is in record.json")
    text = (args.plan / "plan.json").read_bytes().decode("utf-8")
    if digest(text) != record["judge"]["plan_sha256"]:
        raise SystemExit("plan.json is not the plan the replay froze")
    plan = json.loads(text)
    judge = je.judge_of(plan)
    if judge["module"] is not context_judge:
        raise SystemExit("the plan is not the context judge's")
    runs_dir = args.runs or args.plan.parent / "runs"
    names, questions = set(), []
    for name, held in plan["runs"].items():
        launch = json.loads((runs_dir / name / "launch.json").read_text(encoding="utf-8"))
        if any(launch.get(key) != value for key, value in held.items()):
            raise SystemExit(f"{name}: its launch.json is not the run the plan names")
        for context in context_judge.run_contexts(runs_dir / name):
            questions.append(context["question"])
            names.update(source for source, _ in context["documents"])
    verdicts = load_jsonl(args.plan / "verdicts.jsonl")
    _, past = je.counted(verdicts)
    valid = context_judge._vouched(plan, verdicts)
    je.admission(verdicts, valid)
    stability = je.stability(judge, plan, valid)
    by_prompt = {}
    for item in plan["items"]:
        if "retest_of" not in item:
            label = item["run"].split("-", 1)[1]
            level = je.grade(judge, item, valid)
            by_prompt[(label, item["case_id"], item["prompt_sha256"])] = level
    arms = record["judge"]["arms"]
    mine = [r for r in rows if r["label"] in AIRCARGO]
    cases = [(r["label"], r["case_id"]) for r in mine]
    levels = {}
    for r in mine:
        for arm in ("H", *arms):
            key = (r["label"], r["case_id"], r[arm]["prompt"]["sha256"])
            if key not in by_prompt:
                raise SystemExit(f"{r['label']}/{r['case_id']}: {arm}'s prompt is not in the plan")
            levels[(arm, (r["label"], r["case_id"]))] = by_prompt[key]
    stops, aircargo = record["stops"], {}
    for arm in ARMS:
        if arm not in arms:
            continue
        missing = sum(1 for c in cases if levels[("H", c)] is None or levels[(arm, c)] is None)
        got = aircargo_pairs(levels, arm, cases)
        aircargo[arm] = {"missing": missing, **got}
        bad = not stability["passed"] or missing > MAX_MISSING
        for name in HITS:
            stops[arm][f"aircargo_{name}"] = NOT_EVIDENCE if bad else got[name]["pooled"]
    out = {
        "spec": SPEC,
        "plan_sha256": record["judge"]["plan_sha256"],
        "measured_at_head": nr.git_head(),
        "tool_sha256": sha256(Path(__file__)),
        "verdicts_sha256": sha256(args.plan / "verdicts.jsonl"),
        "replies_past_the_limit": past,
        "counted": len(valid),
        "stability": stability,
        "aircargo": aircargo,
        "stops": stops,
        "decision": decision(stops),
    }
    without_text(out, names, questions)
    write_json(args.record / "judged.json", out)
    print(json.dumps({"stops": stops, "decision": out["decision"]}, indent=1))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("replay")
    run.add_argument("--runs", type=Path, default=RUNS)
    run.add_argument("--data-root", type=Path, default=DATA_ROOT)
    run.add_argument("--v4-runs", type=Path, default=V4_RUNS)
    run.add_argument("--out", type=Path, default=OUT)
    run.add_argument("--private", type=Path, default=PRIVATE)
    read_back = commands.add_parser("judged")
    read_back.add_argument("--plan", type=Path, required=True)
    read_back.add_argument("--record", type=Path, default=RECORD)
    read_back.add_argument("--runs", type=Path, default=None)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    return replay(args) if args.command == "replay" else judged(args)


if __name__ == "__main__":
    raise SystemExit(main())
