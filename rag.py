"""
rag.py — Production Modular RAG Pipeline.

Pipeline Sequence:
  User Question
  → Conversation Context
  → Query Rewriting
  → Hybrid Retrieval (Dense FAISS + Sparse BM25 via Reciprocal Rank Fusion)
  → Cross-Encoder Reranking
  → Context Construction (Context-window budgeting & Prompt Injection Defense)
  → Gemini LLM
  → Grounded Streaming Response & Citations

Features:
  - Token-aware and character-aware chunking support.
  - Hybrid search combining semantic embeddings with BM25 keyword matching.
  - Optional neural cross-encoder reranking.
  - Strict context-window budgeting (MAX_CONTEXT_TOKENS).
  - Protection against adversarial prompt injections within retrieved documents.
  - Graceful fallback when retrieval returns no relevant results.
  - Conversation-aware query rewriting for contextual follow-up questions.
  - Grounded citations with accurate source filenames and 1-indexed page numbers.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Generator, List, Optional, Tuple

from google import genai  # pyright: ignore
from google.genai import types  # pyright: ignore
from langchain_community.vectorstores import FAISS  # pyright: ignore

from chat_manager import ChatMemory
from config.prompts import CONDENSE_QUESTION_PROMPT, RAG_SYSTEM_PROMPT
from config.settings import (
    DEFAULT_MODEL,
    HYBRID_ALPHA,
    HYBRID_SEARCH_ENABLED,
    MAX_CONTEXT_TOKENS,
    PROMPT_INJECTION_DEFENSE,
    RERANKING_ENABLED,
    RETRIEVER_K,
)
from src.bm25_retriever import BM25Retriever
from src.context_manager import construct_guarded_context
from src.hybrid_retriever import retrieve_hybrid
from src.logger import get_logger
from src.reranker import rerank_chunks
from src.retriever import (
    RetrievalResult,
    retrieve_relevant_chunks,
)

logger = get_logger(__name__)


# ── Gemini Client ──────────────────────────────────────────────────────────────

def _get_client() -> genai.Client:
    """
    Returns an initialized google.genai Client.
    Supports both standard API keys (AIza...) and OAuth access tokens (AQ...).
    Raises ValueError with actionable instructions if GOOGLE_API_KEY is missing.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "GOOGLE_API_KEY is not set. Please configure it in your .env file."
        )

    if api_key.startswith("AQ."):
        try:
            from google.oauth2.credentials import Credentials
            credentials = Credentials(token=api_key)
            return genai.Client(credentials=credentials)
        except ImportError:
            pass

    return genai.Client(api_key=api_key)


# ── Stage 1: Query Rewriting ───────────────────────────────────────────────────

def _condense_query(
    question: str,
    chat_history_str: str,
    model: str = DEFAULT_MODEL,
) -> str:
    """
    Rewrites a context-dependent follow-up question into an explicit, standalone query.
    Uses Gemini with temperature=0.0 for deterministic rewriting.
    """
    if not chat_history_str.strip():
        return question

    logger.info("Rewriting follow-up question with conversation context...")
    try:
        client = _get_client()
        prompt = CONDENSE_QUESTION_PROMPT.format(
            chat_history=chat_history_str,
            question=question,
        )
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.0),
        )
        condensed = (response.text or "").strip()
        if condensed:
            logger.info(f"Rewritten standalone query: '{condensed}'")
            return condensed
        return question
    except Exception as exc:
        logger.error(f"Query condensation failed ({exc}). Falling back to raw question.")
        return question


# ── Stage 2: Hybrid Retrieval & Reranking ─────────────────────────────────────

def retrieve_and_rerank(
    query: str,
    db: Optional[FAISS] = None,
    bm25: Optional[BM25Retriever] = None,
    k: int = RETRIEVER_K,
    threshold: float = 0.0,
    hybrid: bool = HYBRID_SEARCH_ENABLED,
    rerank: bool = RERANKING_ENABLED,
) -> List[RetrievalResult]:
    """
    Executes the multi-stage retrieval pipeline:
      1. Hybrid retrieval (FAISS dense vector search + BM25 sparse keyword search).
      2. Neural / heuristic reranking of candidates.
      3. Threshold filtering and Top-K selection.
    """
    if not query or not query.strip():
        return []

    # 1. Retrieve candidates
    if hybrid and (db is not None or bm25 is not None):
        candidates = retrieve_hybrid(
            db=db,
            bm25=bm25,
            query=query,
            k=max(k * 2, 8),
            threshold=0.0,
            alpha=HYBRID_ALPHA,
        )
    elif db is not None:
        candidates = retrieve_relevant_chunks(db, query, k=max(k * 2, 8), threshold=0.0)
    elif bm25 is not None:
        candidates = bm25.retrieve_as_results(query, k=max(k * 2, 8))
    else:
        return []

    if not candidates:
        return []

    # 2. Rerank candidates
    if rerank and len(candidates) > 1:
        reranked = rerank_chunks(query=query, results=candidates, top_n=k, enabled=True)
    else:
        reranked = candidates[:k]

    # 3. Threshold filter
    filtered = [r for r in reranked if r.similarity >= threshold]
    logger.info(f"Retrieved & reranked {len(filtered)} chunk(s) above threshold {threshold:.2f}")
    return filtered


# ── Stage 3: Context Construction & Prompt Injection Defense ──────────────────

def _build_context(
    results: List[RetrievalResult],
    max_tokens: int = MAX_CONTEXT_TOKENS,
    defend_injection: bool = PROMPT_INJECTION_DEFENSE,
) -> Tuple[str, List[Dict[str, Any]], float]:
    """
    Constructs an injection-guarded, token-budgeted context string with citations.
    """
    if not results:
        return "No document context available.", [], 0.0

    return construct_guarded_context(
        results,
        max_tokens=max_tokens,
        defend_injection=defend_injection,
    )


def _retrieve_and_format(
    db: Optional[FAISS],
    standalone_query: str,
    retriever_k: int,
    pre_retrieved: Optional[List[RetrievalResult]] = None,
) -> Tuple[str, List[Dict[str, Any]], float]:
    """Backward-compatible retrieval and context formatting helper."""
    if pre_retrieved is not None:
        results = pre_retrieved
    elif db is not None:
        results = retrieve_relevant_chunks(db, standalone_query, k=retriever_k)
    else:
        results = []
    return _build_context(results)


# ── Stage 4: Prompt Construction ──────────────────────────────────────────────

def _build_prompt(
    context_text: str,
    chat_history_str: str,
    question: str,
    persona: str = "",
) -> Tuple[str, str]:
    """Constructs system instruction and prompt template text."""
    system_instruction = persona.strip() if persona.strip() else (
        "You are BotTech AI, an expert, intelligent, and helpful AI assistant. "
        "Provide clear, accurate, and structured answers using rich Markdown formatting."
    )

    prompt_text = RAG_SYSTEM_PROMPT.format(
        context=context_text,
        chat_history=chat_history_str if chat_history_str.strip() else "No prior history.",
        question=question,
    )
    return system_instruction, prompt_text


# ── Stage 5: Streaming Generation ─────────────────────────────────────────────

def _stream_llm(
    model: str,
    system_instruction: str,
    prompt_text: str,
    temperature: float,
    image_bytes: Optional[bytes] = None,
    image_mime: str = "image/jpeg",
    web_search: bool = False,
    web_citations: Optional[List[Dict[str, Any]]] = None,
) -> Generator[str, None, None]:
    """Streams response tokens from Gemini with web search grounding and pure LLM fallbacks."""
    def build_contents():
        if image_bytes:
            return [
                types.Part(inline_data=types.Blob(mime_type=image_mime, data=image_bytes)),
                types.Part(text=prompt_text),
            ]
        return prompt_text

    logger.info(f"Calling Gemini ({model}) stream (web_search={web_search})...")
    client = _get_client()
    yielded_any = False

    # 1. Web search branch
    if web_search:
        try:
            cfg = types.GenerateContentConfig(
                temperature=temperature,
                system_instruction=system_instruction,
                max_output_tokens=8192,
                tools=[{"google_search": {}}],
            )
            for chunk in client.models.generate_content_stream(
                model=model,
                contents=build_contents(),
                config=cfg,
            ):
                if chunk.candidates and chunk.candidates[0].grounding_metadata:
                    g_meta = chunk.candidates[0].grounding_metadata
                    if g_meta.grounding_chunks:
                        for gc in g_meta.grounding_chunks:
                            if gc.web and web_citations is not None:
                                uri = gc.web.uri
                                if not any(wc.get("uri") == uri for wc in web_citations):
                                    web_citations.append({"title": gc.web.title, "uri": uri})
                if chunk.text:
                    yielded_any = True
                    yield chunk.text
            return
        except Exception as exc:
            logger.warning(f"Web search stream failed ({exc}). Falling back to pure LLM.")
            if yielded_any:
                yield f"\n\n🚨 *Stream interrupted: {exc}*"
                return

    # 2. Pure LLM branch
    try:
        cfg = types.GenerateContentConfig(
            temperature=temperature,
            system_instruction=system_instruction,
            max_output_tokens=8192,
        )
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=build_contents(),
            config=cfg,
        ):
            if chunk.text:
                yield chunk.text
    except Exception as exc:
        logger.error(f"Error streaming response from Gemini: {exc}")
        yield f"\n\n🚨 *An error occurred: {exc}*"


# ── Public API ─────────────────────────────────────────────────────────────────

def execute_rag_pipeline(
    db: Optional[FAISS],
    memory: ChatMemory,
    question: str,
    temperature: float = 0.7,
    retriever_k: int = RETRIEVER_K,
    model: str = DEFAULT_MODEL,
    persona: str = "",
    image_bytes: Optional[bytes] = None,
    image_mime: str = "image/jpeg",
    web_search: bool = False,
    web_citations: Optional[List[Dict[str, Any]]] = None,
    pre_retrieved: Optional[List[RetrievalResult]] = None,
    bm25: Optional[BM25Retriever] = None,
    hybrid: bool = HYBRID_SEARCH_ENABLED,
    rerank: bool = RERANKING_ENABLED,
) -> Tuple[Generator[str, None, None], List[Dict[str, Any]], float]:
    """
    Executes the complete modular RAG pipeline.

    Args:
        db:             FAISS vector store.
        memory:         ChatMemory for conversation history (current question NOT included yet).
        question:       Raw user question.
        temperature:    Sampling temperature.
        retriever_k:    Number of top chunks to return.
        model:          Gemini model name.
        persona:        Optional persona or system instruction.
        image_bytes:    Optional image bytes for multimodal input.
        image_mime:     Image MIME type.
        web_search:     Whether to enable Google search grounding.
        web_citations:  List to populate with web citations.
        pre_retrieved:  Pre-retrieved RetrievalResult chunks (skips retrieval if provided).
        bm25:           Optional BM25Retriever for hybrid search.
        hybrid:         Enable hybrid retrieval (FAISS + BM25).
        rerank:         Enable cross-encoder reranking.

    Returns:
        (token_generator, citations, avg_similarity)
    """
    # Step 1: Format conversation history (excluding current turn)
    chat_history_str = memory.format_chat_history(limit=6)

    # Step 2: Query Rewriting
    standalone_query = question
    if pre_retrieved is None and (db is not None or bm25 is not None) and not image_bytes:
        standalone_query = _condense_query(question, chat_history_str, model=model)

    # Step 3: Hybrid Retrieval & Reranking
    if pre_retrieved is not None:
        retrieved_results = pre_retrieved
    elif db is not None or bm25 is not None:
        retrieved_results = retrieve_and_rerank(
            query=standalone_query,
            db=db,
            bm25=bm25,
            k=retriever_k,
            threshold=0.0,
            hybrid=hybrid,
            rerank=rerank,
        )
    else:
        retrieved_results = []

    # Step 4: Context Construction & Prompt Injection Defense
    context_text, citations, avg_similarity = _build_context(retrieved_results)

    # Step 5: Build Prompt
    system_instruction, prompt_text = _build_prompt(
        context_text=context_text,
        chat_history_str=chat_history_str,
        question=question,
        persona=persona,
    )

    # Step 6: Stream Grounded Response
    token_generator = _stream_llm(
        model=model,
        system_instruction=system_instruction,
        prompt_text=prompt_text,
        temperature=temperature,
        image_bytes=image_bytes,
        image_mime=image_mime,
        web_search=web_search,
        web_citations=web_citations,
    )

    return token_generator, citations, avg_similarity


def calculate_confidence(avg_similarity: float, citations: list) -> Tuple[int, str]:
    """
    Computes a grounded confidence score (0-100) and descriptive label
    based on vector retrieval similarity and number of citations.
    """
    if not citations or avg_similarity <= 0.0:
        return 20, "Low Confidence (Answering mainly from general training data)"

    score = int(round(min(1.0, max(0.0, avg_similarity)) * 100))
    if score >= 80:
        desc = "High Confidence (Strong local document matches)"
    elif score >= 65:
        desc = "Medium-High Confidence (Moderate document matches)"
    elif score >= 45:
        desc = "Medium Confidence (Weak matches or partial details)"
    else:
        desc = "Low Confidence (Answering mainly from general training data)"
    return score, desc


_calculate_confidence = calculate_confidence

