"""
agent/prompts.py

Prompt templates and builders for the RAG assistant.
"""

from __future__ import annotations

from typing import Any

PROMPT_REGISTRY: dict[str, dict[str, str]] = {
    "qa": {
        "prompt_id": "QA_PROMPT_V4",
        "text": """You are a support assistant.

You are given context from a knowledge base and a user's question.
Your task is to answer strictly from this context.

If the context answers the question only in part, or in general terms that cover
the user's case, give what the context says and briefly name what it does not cover.
Only when nothing in the context answers the question, say that the available
information does not answer it.
When the answer depends on conditions the context gives, state them
instead of a bare yes or no.
Do NOT invent facts, conditions or advice that are not in the provided text.

--------------------
CONTEXT:
{context_block}
--------------------

QUESTION:
{question}

When you rely on a specific fact from the context, put the number of its document
in square brackets right after it: [1] for the first document in the context list,
[2] for the second, and so on. Do not invent citation numbers. If a statement is not
supported by the context, do not add a reference.

Answer in the language of the QUESTION, even when the context is written in another language.
Write a clear, brief and accurate answer for the user:
""",
    },
    "self_eval": {
        "prompt_id": "SELF_EVAL_PROMPT_V3",
        "text": """You are an expert in rating the quality of assistant answers.

You are given:
1) the user's question;
2) the context (fragments of a knowledge base);
3) the assistant's answer to this question.

Rate the quality of the answer on a scale from 1 to 100.

When rating, take into account:
- Answer relevance:
    How far the answer relates to the question at all, whether it answers its substance.

- Answer accuracy:
    How far the facts in the answer match the text of the context.
    Do not reward an answer that invents facts.

- Retrieval quality:
    How well the context the assistant used covers the topic of the
    question without irrelevant noise. If the needed information is not
    in the context, this also lowers the final rating of the answer.

- Answer language:
    The answer must be in the language of the question; an answer in another language lowers the rating.

Your task is to output ONE INTEGER from 1 to 100,
where 1 is a terrible answer, 50 an average one, 100 an excellent one.

OUTPUT ONLY THE NUMBER, WITHOUT WORDS OR COMMENTS.

--------------------
QUESTION:
{question}
--------------------
CONTEXT:
{context_block}
--------------------
ASSISTANT'S ANSWER:
{answer}
--------------------

Output only an integer from 1 to 100:
""",
    },
    "extract_claims": {
        "prompt_id": "EXTRACT_CLAIMS_PROMPT_V1",
        "text": """You are an assistant that breaks a text into atomic factual claims.
A claim is a single, verifiable statement of fact.
Ignore greetings, meta-commentary, and hedges.
Output each claim on its own line, prefixed with '- '.
If there are no factual claims, output 'NONE'.

Text:
{answer}

Claims:""",
    },
    "verify_claim": {
        "prompt_id": "VERIFY_CLAIM_PROMPT_V1",
        "text": """You are a fact-checker. Decide whether the CLAIM is DIRECTLY supported by the CONTEXT.
Answer strictly:
  SUPPORTED: <one-line quote or paraphrase from context>
  UNSUPPORTED
Do not use outside knowledge. If context is silent or ambiguous - UNSUPPORTED.

CONTEXT:
{context}

CLAIM: {claim}

Answer:""",
    },
    "classify_complexity": {
        "prompt_id": "CLASSIFY_COMPLEXITY_PROMPT_V2",
        "text": """Classify the user question and extract structured retrieval metadata.

SIMPLE: factual lookup, single concept, short answer (<5 sentences).
  Examples: 'How to reset password?', 'What is X?', 'Where is the Y button?'

COMPLEX: multi-step reasoning, comparison, analysis, inference,
or synthesis across a small set of documents.
  Examples: 'Compare A and B', 'Explain why X causes Y',
            'Analyze this contract against policy Z'

GLOBAL: corpus-level or multi-hop question that asks about themes,
relationships, or patterns across many documents.
  Examples: 'Which policies relate to contract X?',
            'What topics recur across the HR corpus?'

Question classes describe where the answer lives:
- single_hop: one passage or source is sufficient
- multi_hop: the answer links evidence from multiple sources
- aggregation: the answer compares or combines items from multiple sources
- global: the answer requires corpus-wide themes or patterns

Extract concise named entities exactly as written in the question. Set
needs_multi_hop=true for multi_hop, aggregation, or global. Use the matching
reason_code: SINGLE_SOURCE, MULTI_SOURCE_CHAIN, MULTI_SOURCE_AGGREGATION, or
CORPUS_GLOBAL.

When a JSON schema is supplied, populate every field in it. Otherwise preserve
the legacy fallback and output strictly one word: SIMPLE, COMPLEX, or GLOBAL.

Question: {question}

Classification:""",
    },
    "suggested_questions": {
        "prompt_id": "SUGGESTED_QUESTIONS_PROMPT_V2",
        "text": """Based on the user question and the assistant answer, propose 3 short follow-up questions.
The questions must:
- stay on topic
- be short (up to 60 characters)
- help the user go one step deeper
- be written in the language of the QUESTION

QUESTION: {question}
ANSWER: {answer_excerpt}{context_block}

Return ONLY 3 questions, one per line. No numbering. No bullets.""",
    },
    "query_transform": {
        "prompt_id": "QUERY_TRANSFORM_PROMPT_V1",
        "text": """Ты — специалист по поисковым запросам.

Пользователь задал вопрос к базе знаний технической поддержки.
Твоя задача — переформулировать вопрос в оптимальный поисковый запрос,
чтобы найти максимально релевантные документы.

Правила:
- Убери разговорный стиль, оставь ключевые термины
- Добавь синонимы и альтернативные термины через пробел
- Если есть коды ошибок (E20, E21...) — оставь как есть
- Если вопрос уже лаконичный — верни его без изменений
- Выведи ТОЛЬКО переформулированный запрос, одной строкой, БЕЗ пояснений

ВОПРОС:
{question}

Поисковый запрос:
""",
    },
    "doc_grade": {
        "prompt_id": "DOC_GRADE_PROMPT_V1",
        "text": """Ты — эксперт по оценке релевантности документов.

Определи, содержит ли данный документ информацию, полезную для ответа
на вопрос пользователя. Учитывай: частичная релевантность тоже считается.

ВОПРОС:
{question}

ДОКУМЕНТ (source={source}):
{text}

Ответь ОДНИМ словом: YES или NO.
""",
    },
    "doc_grade_batch": {
        "prompt_id": "DOC_GRADE_BATCH_PROMPT_V1",
        "text": """Ты — эксперт по оценке релевантности документов.

Для каждого документа определи, содержит ли он информацию, полезную для ответа
на вопрос пользователя. Учитывай: частичная релевантность тоже считается.

ВОПРОС:
{question}

ДОКУМЕНТЫ:
{documents}

Верни только JSON без Markdown:
{{"grades":[{{"index":1,"relevant":true,"reason":"коротко"}}]}}
""",
    },
    "query_rewrite": {
        "prompt_id": "QUERY_REWRITE_PROMPT_V1",
        "text": """Ты — специалист по улучшению поисковых запросов.

Система пыталась ответить на вопрос пользователя, но качество ответа
оказалось низким (оценка: {quality_score}/100).

Исходный вопрос:
{question}

Предыдущий ответ (неудачный):
{previous_answer}

Твоя задача — переформулировать вопрос так, чтобы поиск по базе знаний
нашёл более релевантные документы. Попробуй:
- Использовать другие ключевые слова
- Разбить сложный вопрос на более конкретный
- Добавить контекст или уточнения

Выведи ТОЛЬКО новый поисковый запрос, одной строкой, БЕЗ пояснений:
""",
    },
    "conversational_qa": {
        "prompt_id": "CONVERSATIONAL_QA_PROMPT_V4",
        "text": """You are a support assistant.

You are given context from a knowledge base, the conversation history and the current question.
Use the history to understand what follow-up questions refer to.
Answer strictly from the knowledge base context.

--------------------
CONVERSATION HISTORY:
{history_block}
--------------------
CONTEXT:
{context_block}
--------------------

CURRENT QUESTION:
{question}

When you rely on a specific fact from the context, put the number of its document
in square brackets right after it: [1] for the first document in the context list,
[2] for the second, and so on. Do not invent citation numbers. If a statement is not
supported by the context, do not add a reference.

Answer in the language of the QUESTION, even when the context is written in another language.
Answer:
""",
    },
    "conversational_query_transform": {
        "prompt_id": "CONVERSATIONAL_QUERY_TRANSFORM_PROMPT_V1",
        "text": """Ты — специалист по поисковым запросам.

Пользователь ведёт диалог с ассистентом поддержки.
Его текущий вопрос может быть уточняющим (ссылается на предыдущие сообщения).

Твоя задача — переформулировать текущий вопрос в самодостаточный поисковый
запрос, который можно использовать для поиска по базе знаний БЕЗ истории.

ИСТОРИЯ ДИАЛОГА:
{history_block}

ТЕКУЩИЙ ВОПРОС:
{question}

Выведи ТОЛЬКО полноценный поисковый запрос, одной строкой:
""",
    },
    "multi_query": {
        "prompt_id": "MULTI_QUERY_PROMPT_V1",
        "text": """Разбей вопрос пользователя на 2-3 независимых поисковых запроса.
Каждый запрос должен искать один конкретный аспект вопроса.
Если вопрос простой и не требует разбиения — верни его как есть.

ВОПРОС:
{question}

Выведи запросы, по одному на строку (2-3 строки, без нумерации и маркеров):
""",
    },
}
# BEGIN DEPLOYED_PROMPT_OVERRIDES
DEPLOYED_PROMPT_OVERRIDES: dict[str, str] = {}
# END DEPLOYED_PROMPT_OVERRIDES


def _resolve_prompt(name: str, experiment: Any | None = None) -> str:
    from agent.prompt_registry import get_prompt

    return get_prompt(name, experiment)


def _format_context_block(context_docs: list[dict[str, Any]]) -> str:
    if not context_docs:
        # No words of any language in the context block: the documents speak for themselves.
        return "[]"

    parts = []
    for idx, doc in enumerate(context_docs, start=1):
        text = str(doc.get("page_content", ""))
        metadata = doc.get("metadata", {}) or {}
        source = metadata.get("source") or metadata.get("file_name") or f"doc_{idx}"
        parts.append(f"[{idx} | source={source}]\n{text}")
    return "\n\n".join(parts)


def build_qa_prompt(
    question: str,
    context_docs: list[dict[str, Any]],
    experiment: Any | None = None,
) -> str:
    context_block = _format_context_block(context_docs)
    return _resolve_prompt("qa", experiment).format(
        context_block=context_block,
        question=question,
    )


def build_self_eval_prompt(
    question: str,
    answer: str,
    context_docs: list[dict[str, Any]],
    experiment: Any | None = None,
) -> str:
    context_block = _format_context_block(context_docs)
    return _resolve_prompt("self_eval", experiment).format(
        question=question,
        context_block=context_block,
        answer=answer,
    )


def build_extract_claims_prompt(answer: str, experiment: Any | None = None) -> str:
    return _resolve_prompt("extract_claims", experiment).format(answer=answer)


def build_verify_claim_prompt(
    claim: str,
    context: str,
    experiment: Any | None = None,
) -> str:
    return _resolve_prompt("verify_claim", experiment).format(
        context=context,
        claim=claim,
    )


def build_classify_complexity_prompt(question: str, experiment: Any | None = None) -> str:
    return _resolve_prompt("classify_complexity", experiment).format(question=question)


def build_suggested_questions_prompt(
    question: str,
    answer: str,
    context_snippet: str = "",
    experiment: Any | None = None,
) -> str:
    context_block = ""
    if context_snippet:
        context_block = f"\n\nCONTEXT:\n{context_snippet[:500]}"
    return _resolve_prompt("suggested_questions", experiment).format(
        question=question,
        answer_excerpt=answer[:500],
        context_block=context_block,
    )


def build_query_transform_prompt(question: str, experiment: Any | None = None) -> str:
    return _resolve_prompt("query_transform", experiment).format(question=question)


def build_doc_grade_prompt(
    question: str,
    document: dict[str, Any],
    experiment: Any | None = None,
) -> str:
    text = str(document.get("page_content", ""))
    source = (document.get("metadata") or {}).get("source", "unknown")
    return _resolve_prompt("doc_grade", experiment).format(
        question=question,
        source=source,
        text=text,
    )


def build_doc_grade_batch_prompt(
    question: str,
    documents: list[dict[str, Any]],
    experiment: Any | None = None,
) -> str:
    parts = []
    for idx, document in enumerate(documents, start=1):
        text = str(document.get("page_content", ""))
        metadata = document.get("metadata") or {}
        source = metadata.get("source") or metadata.get("file_name") or f"doc_{idx}"
        parts.append(f"[{idx}] source={source}\n{text}")
    return _resolve_prompt("doc_grade_batch", experiment).format(
        question=question,
        documents="\n\n".join(parts),
    )


def build_query_rewrite_prompt(
    question: str,
    previous_answer: str,
    quality_score: int,
    experiment: Any | None = None,
) -> str:
    return _resolve_prompt("query_rewrite", experiment).format(
        quality_score=quality_score,
        question=question,
        previous_answer=previous_answer,
    )


def build_conversational_qa_prompt(
    question: str,
    context_docs: list[dict[str, Any]],
    chat_history: list[dict[str, str]],
    experiment: Any | None = None,
) -> str:
    context_block = _format_context_block(context_docs)
    history_block = ""
    if chat_history:
        parts = []
        for msg in chat_history[-5:]:
            role = msg.get("role", "user")
            text = msg.get("content", "")
            label = "user" if role == "user" else "assistant"
            parts.append(f"{label}: {text}")
        history_block = "\n".join(parts)

    if history_block:
        return _resolve_prompt("conversational_qa", experiment).format(
            history_block=history_block,
            context_block=context_block,
            question=question,
        )
    return build_qa_prompt(question=question, context_docs=context_docs, experiment=experiment)


def build_conversational_query_transform_prompt(
    question: str,
    chat_history: list[dict[str, str]],
    experiment: Any | None = None,
) -> str:
    if not chat_history:
        return build_query_transform_prompt(question, experiment)

    history_parts = []
    for msg in chat_history[-4:]:
        role = msg.get("role", "user")
        text = msg.get("content", "")[:200]
        label = "Q" if role == "user" else "A"
        history_parts.append(f"{label}: {text}")
    history_block = "\n".join(history_parts)

    return _resolve_prompt("conversational_query_transform", experiment).format(
        history_block=history_block,
        question=question,
    )


def build_multi_query_prompt(question: str, experiment: Any | None = None) -> str:
    return _resolve_prompt("multi_query", experiment).format(question=question)
