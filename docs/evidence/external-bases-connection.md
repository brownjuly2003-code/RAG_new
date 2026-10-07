# Connection of the three external bases — plan slices 1.5, 1.5c and 1.5d

ConditionalQA, WixQA and MultiHop-RAG now stand beside our corpus. Their
pinned files were converted to markdown, cut by the product's chunker with its
defaults, embedded by the product's embedder and indexed — each base in a
tenant, a collection and an index directory of its own. This capsule is the
record of that connection: what was taken, what the conversion and the
chunking kept, and what an index cost to build. **It is preparation.** The
connection ran no question through the retrieval path, so no number here
measures quality. The pilot of plan slice 1.6 and the baseline of slice 1.7
record retrieval measurements separately.

Every count below is in
[`connection.json`](../../reports/external/36f1167/connection.json), and
[`tests/test_external_connection_artifact.py`](../../tests/test_external_connection_artifact.py)
holds that file against the registration of the bases and this text against
that file: each row of the tables and each count of the summary is computed
there.

- **Three bases connected, ours untouched.** 7,482 documents in 62,580 chunks,
  in three collections. Our corpus, the index of slice 2.5 and its embeddings
  were hashed before the first step and after the last, and the three digests
  did not change.
- **Chunking lost nothing.** Every visible character of every document is in a
  chunk, and every chunk has its place in its document. All 10,271 evidence
  groups of ConditionalQA lie whole in one chunk; of the 6,084 of
  MultiHop-RAG, 6,078 do and 6 lie across two chunks; none is lost.
- **All gold was placed.** No evidence reference of either base is left
  without a place in its document. 327 of the 10,271 groups of ConditionalQA
  and 29 of the 6,084 of MultiHop-RAG stand in several places of their
  document, and each keeps every place as an alternative.
- **One run on one host.** The seconds are those of one run on one machine
  that other jobs used at the same time. They say what the connection took and
  are not evidence of speed.
- **The labels are the datasets' own.** Nothing here was labelled or checked
  by us. ConditionalQA's evidence was chosen by its annotators. WixQA's
  ExpertWritten questions and gold articles come from Wix's support experts,
  its Simulated ones were distilled from chats by GPT-4o and reviewed by
  experts. MultiHop-RAG's questions, answers and evidence were written by
  GPT-4: the base is `llm_labelled` and decides nothing.

## Terms

- **Base, tenant, collection.** A base is one public dataset: its documents
  and its questions. Connected, it is a tenant with one collection in an index
  directory of its own. This separates the indexed data; the connection run
  did not exercise query routing between tenants.
- **Document.** A page of GOV.UK (ConditionalQA), a document of the Wix
  knowledge base (WixQA) or a news article (MultiHop-RAG), as one markdown
  file written by the registered conversion `external-markdown-v1`.
- **Evidence group, alternative.** An evidence group is one element of a page
  that an annotator chose (ConditionalQA) or one sentence of an article
  (MultiHop-RAG). Its place is a range of the document's visible characters.
  Where the same text stands in several places of the document, each place is
  an *alternative* of the group and none is preferred (rule
  `external-gold/range-coverage-v1` of the
  [spec](../specs/semantic-precision-metrics.md)). WixQA has no groups: its
  gold is whole documents.
- **Visible characters.** The characters of a document that are printable and
  not whitespace, in their order. Chunks are placed by them, so «lost nothing»
  is a count and not an impression.
- **Whole, split, lost.** After chunking, a place is *whole* when one chunk
  covers it, *split* when only several chunks together do, and *lost* when
  they do not. A group is as good as its best alternative.
- **Archive, payload.** The chunks of a base are one gzip archive of a JSON
  payload. The bytes of the archive depend on the compression library of the
  host that wrote it; the bytes of the payload do not. Both digests are given
  below, and an index is tied to the archive of the Mac.
- **Structural graph.** The graph the product builds from the headings of the
  chunks, with no model: documents, sections and chunks, joined by `contains`,
  `next` and `same_section`.

## The bases

| Base | Documents | Documents with gold | Questions | Chunks | Collection | Revision |
|---|---|---|---|---|---|---|
| ConditionalQA | 652 | 495 | 2,623 | 13,778 | `rag_docs_ext_conditionalqa` | `77bd2959` |
| WixQA | 6,221 | 340 | 400 | 37,571 | `rag_docs_ext_wixqa` | `d662dc42` |
| MultiHop-RAG | 609 | 609 | 2,556 | 11,231 | `rag_docs_ext_multihoprag` | `71ac0d0b` |

- **ConditionalQA** — Sun, Cohen, Salakhutdinov, *ConditionalQA: A Complex
  Reading Comprehension Dataset with Conditional Answers*, ACL 2022
  ([repository](https://github.com/haitian-sun/ConditionalQA)). From `v1_0/`:
  all 652 pages and the questions of `train` and `dev`, 2,338 and 285; the
  questions of `test` are not among the registered files. 2,518 of the 2,623
  questions are answerable, and 495 pages carry a question.
- **WixQA** — Cohen et al. (Wix.com AI Research), *WixQA: A Multi-Dataset
  Benchmark for Enterprise Retrieval-Augmented Generation*, 2025
  ([dataset](https://huggingface.co/datasets/Wix/WixQA)). The knowledge base
  of 6,221 documents — 4,109 articles, 2,049 feature requests and 63 known
  issues, all of them indexed, as the plan has it — and 400 questions: 200
  ExpertWritten and 200 Simulated. 340 documents are the gold of some
  question.
- **MultiHop-RAG** — Tang, Yang, *MultiHop-RAG: Benchmarking
  Retrieval-Augmented Generation for Multi-Hop Queries*, 2024
  ([dataset](https://huggingface.co/datasets/yixuantt/MultiHopRAG)). 609 news
  articles and 2,556 questions: 816 inference, 856 comparison, 583 temporal
  and 301 null. A null question has no gold; every other names two to four
  articles.

The revision and the SHA-256 of every file taken are in
[`evaluation/external_bases.json`](../../evaluation/external_bases.json), with
the digests of each converted corpus and question set. How the questions are
cut into parts, and which parts are locked, is the registration of plan slice
1.6 and not this capsule.

## Conversion and gold

| Base | Evidence groups | Alternatives | Groups in several places | References not placed | Whole | Split | Lost | Alternatives whole / split / lost |
|---|---|---|---|---|---|---|---|---|
| ConditionalQA | 10,271 | 10,712 | 327 | 0 | 10,271 | 0 | 0 | 10,712 / 0 / 0 |
| MultiHop-RAG | 6,084 | 6,113 | 29 | 0 | 6,078 | 6 | 0 | 6,107 / 6 / 0 |

The last four columns are the state after chunking (next section).

- **ConditionalQA.** A page is a list of HTML elements — headings, paragraphs,
  list items and table rows — and the evidence of a question names elements by
  their text. The conversion writes each element as a block of markdown and
  gives every evidence reference its place. 10,284 references make 10,271
  groups: 13 repeat an element inside one question. 327 groups stand in
  several places of their page (236 different strings); the plan had estimated
  339. Questions whose evidence lies in two or more sections of one page — the
  stratum the plan names by default for its first mechanism — number 1,222 by
  the registered reading of a section; the plan had 1,259 from its research.
  One answerable question carries no evidence.
- **WixQA.** The HTML of a document is written as markdown with its headings
  in their order: 26,142 headings stand in the HTML and 26,142 are written,
  and in every one of the 6,221 documents the headings are the same in the
  same order. The plan asks for these counts against the pinned HTML in place
  of a threshold. The visible text of every document also equals the plain
  text that the dataset gives beside the HTML.
- **MultiHop-RAG.** The source, the date and the title of an article are its
  first heading, so the header of every chunk of the article carries them as
  far as the limit of a header allows (the plan asks for them in the text of a
  chunk). Each evidence sentence is placed in the article that its question
  names.

## Chunking

The product's chunker with the registered settings, which are its defaults:
structural splitting, 800 characters a chunk with an overlap of 200, and a
contextual header before each chunk.

| Base | Chunk characters, median / 95th percentile / largest | Chunks a document, median / 95th percentile / largest | Chunks longer than 800 | Heading paths cut | Visible characters in no chunk | Chunks without a place |
|---|---|---|---|---|---|---|
| ConditionalQA | 503 / 899 / 1,013 | 17 / 51 / 118 | 1,797 | 1,174 | 0 | 0 |
| WixQA | 543 / 954 / 1,013 | 3 / 19 / 104 | 7,766 | 6,497 | 0 | 0 |
| MultiHop-RAG | 850 / 996 / 1,012 | 14 / 40 / 131 | 6,835 | 3,839 | 0 | 0 |

The lengths are those of a chunk as it is embedded, with its header. The
header adds up to 213 characters to the 800 that the chunker allows the text,
and the largest chunk is 1,013. A header is cut at 200 characters and keeps
its beginning, so a heading path that does not fit loses its deepest headings
first; the fewest characters of a path that a cut header kept are 114, 105 and
105.

## Embeddings and indexes

The embedder is the product's — `BAAI/bge-m3` at revision
`5617a9f61b028005a4858fdac845db406aefb181`, 1024 dimensions — on the CPU of
the Mac (i5-7500, 4 cores, 8 GiB): the model and the environment of the index
of our corpus (slice 2.5). Each index is a Chroma collection (chromadb 1.5.9)
in a directory of its own, built from the checkpoint of its base; its receipt
names the archive, the checkpoint, the embedder and the code.

| Base | Chunks | Embedding, s | Seconds a chunk | Seconds a document | Attempts | Looks with foreign load | Peak memory of the embedder, GiB | Index, s |
|---|---|---|---|---|---|---|---|---|
| ConditionalQA | 13,778 | 6,977 | 0.51 | 10.7 | 1 | 8 of 116 | 2.7 | 24 |
| WixQA | 37,571 | 19,934 | 0.53 | 3.2 | 1 | 24 of 331 | 2.8 | 61 |
| MultiHop-RAG | 11,231 | 8,227 | 0.73 | 13.5 | 1 | 19 of 137 | 2.5 | 20 |

Once a minute the supervisor of the run looked at the host. «Looks with
foreign load» counts the looks in which a process other than the step's own
held a quarter of a core or more. The steps before the embeddings — download,
conversion, chunking and the check of what the chunks kept — took 16 to 42
seconds a base. The embeddings and the indexes of the three bases took 9.8
hours of the host.

## Our corpus did not change

The supervisor hashed three paths of the Mac before its first step and after
its last: the directory of our corpus, the index of slice 2.5 and the
checkpoint of its embeddings. A digest is the SHA-256 of the list of the
path's files, each with its own SHA-256. Before and after are equal.

| Path | Files | Digest, before and after |
|---|---|---|
| `/Users/julia/RAG_Support_Assistant/data/uploads/aircargo` | 201 | `007dfbf28f127316e16992d892fb36735c77d887d48a7cb44669bf12dbbdab30` |
| `/Users/julia/RAG_new_t65_embeddings_2851e3811508/.tmp/t65-index-72fbd72` | 8 | `b0afc4698056cc6e2e8a5ebf49bec676bb2947b14fa2123aa7971bce66cf2494` |
| `/Users/julia/RAG_new_t65_embeddings_2851e3811508/.tmp/t65-verified-embeddings.npz` | 1 | `f0ec39c547f39bfcbb0d1f3a6b56ae76be6d98108d60ee9f2083eae0641d685d` |

## Structural graphs

Plan slice 1.5 asks for the graph of a base from the product's builders. The
structural builder (`ingestion/structure_graph.py`, version
`gr1-structural-v1`) reads the chunk archive and needs no model. It took 1.6
to 5.7 seconds a base on the laptop, from the payload that the Mac indexed.

| Base | Documents | Sections | Chunks | `contains` | `next` | `same_section` | Cross-reference edges | Digest |
|---|---|---|---|---|---|---|---|---|
| ConditionalQA | 652 | 12,865 | 13,778 | 26,643 | 13,126 | 913 | 0 | `7e9d1bd93c82` |
| WixQA | 6,221 | 31,796 | 37,571 | 69,367 | 31,350 | 5,775 | 0 | `1c755a39a705` |
| MultiHop-RAG | 609 | 609 | 11,231 | 11,840 | 10,622 | 10,622 | 0 | `14fb2f4e2b3b` |

Every document of a base carries the same single category, so each graph also
has one category node and an edge to it from every document.

The entity graph was not built. The spec's section for slice 1.6 («The graph
of a base») reads the plan's condition by lane. The experiment arm of the
first campaign runs the structural lane, so no mechanism of that campaign
needs an entity graph. The timing of the extractor on 100 documents, which the
plan asks for here, is run when a mechanism registers the entity lane, under a
ceiling of three nights a base.

## What the connection shows of the product on a foreign corpus

These are observations from the counts and the code. None is a measured effect
on retrieval.

- **The contextual header is Russian on every corpus.** The header that the
  chunker puts before a chunk is the fixed phrase «[Контекст: Из документа
  *file*, раздел: *heading path*]», and it is embedded with the English text
  of the chunk.
- **Heading paths are cut often.** 1,174 chunks of ConditionalQA (8.5%), 6,497
  of WixQA (17.3%) and 3,839 of MultiHop-RAG (34.2%) have a header cut at its
  limit, and what is cut away is the heading nearest to the text. Part of this
  is the conversion's doing and not the corpus's: the file name of a document
  is the slug of its title, so a title stands in a header twice — as the file
  name and as the first heading.
- **A section is not the same thing on the three bases.** ConditionalQA has
  12,865 sections for 13,778 chunks: a section is mostly one chunk, and only
  913 `same_section` edges exist. WixQA has 31,796 sections for 37,571 chunks.
  In MultiHop-RAG an article is one section, so `same_section` joins every two
  neighbouring chunks of an article, 10,622 times. The spec of a graph
  mechanism (plan row 3.1) has to say what its relation means on each base.
- **No cross-reference is found.** Of the builder's four patterns of a
  reference three follow the wording of our Russian documents («см.», «пункт»,
  «раздел», «приказ №») and the fourth is a file name. No edge of that kind
  exists on any of the three bases. What the builder counts as references it
  could not resolve is the file name in each chunk's own header, one a chunk,
  and 43 more on WixQA.
- **The entity extractor's prompt is Russian** ([policy of plan slice
  3.0](../specs/graph-enablement-policy.md)), which matters when a mechanism
  registers the entity lane.

## Licences and what leaves the hosts

- ConditionalQA: BSD-2-Clause (file `LISCENSE` of the repository). Its README
  adds: «This dataset should ONLY be used for NLP research purpose. Answers
  are NOT verified by legal professionals and should NOT be used for any legal
  purposes.» The page texts are GOV.UK's, under the Open Government Licence
  v3.0. The base is read for retrieval research only.
- WixQA: MIT (dataset card); the knowledge base is a snapshot of 2024-12-02.
- MultiHop-RAG: ODC-BY 1.0 (dataset card); the news texts remain their
  publishers'.

The registration gives one rule for the three bases: «Outside the hosts go
aggregates, attribution and provenance only: no question, evidence string,
document, chunk or embedding of an external base is committed or published.»
The converted corpora, the questions, the chunk archives, the embeddings and
the indexes are on the Mac; the laptop holds the first three, converted there
from the same pinned files. The repository holds counts, digests and the ids
of questions.

## What was not done

- No question was run through the retrieval path, so nothing here says how
  well the product retrieves on these bases.
- No entity graph and no timing of the extractor (above).
- No answer was generated and nothing was judged. The plan reads retrieval
  metrics only on the external bases (decision D7); generation on them is
  frozen.
- The seconds were taken once, on a host that was not idle.
- No label of a base was checked.

## How it was run

On the Mac, from a snapshot of the commit named below, for each base:

1. `python -m scripts.external_base <step> --base <base>` with the steps
   `fetch`, `convert`, `chunks` and `preserve`. The pinned files are
   downloaded and held against the registration, converted, cut into chunks,
   and the chunks are held against the documents and the gold. A conversion
   that differs from the registered digests stops the step.
2. `python -m scripts.production_embeddings` over the chunk archive, with a
   checkpoint every 64 texts, so a stopped run goes on from where it was.
3. `python -m scripts.production_index` from the archive and the checkpoint
   into a new directory, with the embedder manifest that was pinned for the
   index of our corpus.

Steps 2 and 3 ran under a supervisor that waited until no other run of ours
held the Mac, took the bases in turn and hashed the guarded paths.

## Provenance

- Artifact:
  [`connection.json`](../../reports/external/36f1167/connection.json), SHA-256
  `6d6a3ce18ec71e0d97f195a05c67a62ab3dcc7640044d448708dd5eba6cf5225`.
- Registration of the bases, `evaluation/external_bases.json`: SHA-256
  `cf80efc2e0194028c9469a0008a01f0e105bcf3669de71bcfa19947f3a6be167`.
- Code of the conversion, the chunks, the embeddings and the indexes: commit
  `36f1167b9629e3ebcc367bff59c15b7365e0b1b6`. The supervisor on the Mac
  started on 2026-10-05 16:45, waited for the runs of other slices to end,
  worked from 2026-10-06 03:34 to 2026-10-06 13:21 (UTC) and reported 0 failed
  looks at the host.
- Embedder manifest, the same in the three receipts: model `BAAI/bge-m3`,
  revision `5617a9f61b028005a4858fdac845db406aefb181` (`hf_snapshot`), 1024
  dimensions, normalised, no prompt for documents or for queries, backend
  `local`.

| Base | What | SHA-256 |
|---|---|---|
| ConditionalQA | converted corpus | `e22275510a4c4516528a6e9fad0ce437d142697bb4d836f6b510434ae73eb676` |
| ConditionalQA | questions | `8467991cdb095fe1e2204d8eca90679da56f0bac53e3c81686d488cca59eb6b7` |
| ConditionalQA | chunk archive, as the Mac wrote it | `4f9a440de4b9879b0b4a354e4cb1b94c6c03aaa870b78ae6a43d6f799bc14ea1` |
| ConditionalQA | chunk payload | `9685bfd2894f3fae55676a3bc4abc30517c6b14668ddb44dda3dff7453571e33` |
| ConditionalQA | embeddings | `13b7997f31b599fe5bbf866e3a7aef6c0bc38ddafd30c7eaf99bb185cf956e9a` |
| ConditionalQA | structural graph | `7e9d1bd93c8204e44065513df51f172c13e8d4b47c411c44d469f888d463e3d3` |
| WixQA | converted corpus | `08390ae999e25355af4e59f4d14355071b1bd6ad89ed54f0c2d0f330a3ae70a0` |
| WixQA | questions | `d18255995e045c791849db44fb940182f9573056ff3eb11578acb8bf69c20412` |
| WixQA | chunk archive, as the Mac wrote it | `70dd0bd0c52f26281f6d2d5681e193f3d48fb675cac64f78a0889b9d70e2505f` |
| WixQA | chunk payload | `f3134d648fdbfec10e9dcfe9a210814cae7dffcc8e672934a8046c24471e81e7` |
| WixQA | embeddings | `bf3b706234bdfd05ed324a31aecc37d58d64980eb63d57838a6a821bbb7b2001` |
| WixQA | structural graph | `1c755a39a7052a241cd58f39b30c478c3684ff6f698782d4b3553688d044b31e` |
| MultiHop-RAG | converted corpus | `7e1c34980d35889f01dedc5dc21f9a5f2fe28e796be7c0004d44f38b13daa27b` |
| MultiHop-RAG | questions | `cf5f6462b30cac0d6f1b59cff722106001140baee01f003567fb34001c109fac` |
| MultiHop-RAG | chunk archive, as the Mac wrote it | `21c9269557d803ca635bf40a34efc1db818a8006b8f54cfd6e614c00707704db` |
| MultiHop-RAG | chunk payload | `c32820e88d7bbd26298f72effebb591f3ccf92afa995b78e18784640620d5211` |
| MultiHop-RAG | embeddings | `a2ea57d6ed0ea3e23d623f66a652fd5b7dc48bb4954c503662d396a805964135` |
| MultiHop-RAG | structural graph | `14fb2f4e2b3bd5c4ed4c4b9d7fb6cf5467d7e04db1942e65f9b3cd48043a85c4` |
