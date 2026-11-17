"""
rag_service.py — Production RAG Service.

Encapsulates complete conversational RAG execution for both the
FastAPI backend and the Streamlit frontend:
  - Session and message lifecycle persistence via ChatStore.
  - Hybrid retrieval (FAISS + BM25) and neural reranking.
  - Token-aware context window budgeting and prompt defense.
  - Streaming (Server-Sent Events) and synchronous complete responses.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Generator, List, Optional

from chat_manager import ChatMemory
from config.settings import (
    CHAT_DB_PATH,
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    HYBRID_SEARCH_ENABLED,
    RERANKING_ENABLED,
    RETRIEVER_K,
)
from rag import _calculate_confidence, execute_rag_pipeline
from services.retrieval_service import retrieval_service
from src.logger import get_logger
from storage import ChatStore

logger = get_logger(__name__)


class RAGService:
    """
    Unified RAG orchestration service.
    """

    def __init__(self, db_store: Optional[ChatStore] = None):
        self.store = db_store or ChatStore(CHAT_DB_PATH)

    def _prepare_memory(self, session_id: str) -> ChatMemory:
        """Loads historical messages from storage into ChatMemory."""
        memory = ChatMemory()
        messages = self.store.get_messages(session_id)
        for msg in messages:
            memory.add_message(msg["role"], msg["content"])
        return memory

    def generate_response(
        self,
        question: str,
        session_id: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
        retriever_k: int = RETRIEVER_K,
        persona: str = "",
        web_search: bool = False,
        hybrid: bool = HYBRID_SEARCH_ENABLED,
        rerank: bool = RERANKING_ENABLED,
        user_id: str = "default_user",
    ) -> Dict[str, Any]:
        """
        Executes non-streaming end-to-end RAG and returns complete result.
        """
        # Ensure session exists
        if not session_id:
            session_id = self.store.create_session(
                title=question[:40].strip() or "New Chat",
                model=model,
                temperature=temperature,
                retriever_k=retriever_k,
                persona=persona,
                web_search=web_search,
                user_id=user_id,
            )

        # Build memory from prior turns (excluding current question)
        memory = self._prepare_memory(session_id)

        # Run pipeline
        db = retrieval_service.faiss_store
        bm25 = retrieval_service.bm25_retriever
        web_citations: List[Dict[str, Any]] = []

        token_gen, citations, avg_sim = execute_rag_pipeline(
            db=db,
            memory=memory,
            question=question,
            temperature=temperature,
            retriever_k=retriever_k,
            model=model,
            persona=persona,
            web_search=web_search,
            web_citations=web_citations,
            bm25=bm25,
            hybrid=hybrid,
            rerank=rerank,
        )

        # Gather tokens
        response_text = "".join(list(token_gen))

        # Merge citations
        all_citations = citations + (web_citations if web_search else [])
        conf_score, conf_desc = _calculate_confidence(avg_sim, citations)

        # Save to DB
        user_msg_id = self.store.add_message(
            session_id=session_id,
            role="user",
            content=question,
        )
        assistant_msg_id = self.store.add_message(
            session_id=session_id,
            role="assistant",
            content=response_text,
            citations=all_citations,
            confidence_score=conf_score,
            confidence_desc=conf_desc,
        )

        return {
            "session_id": session_id,
            "user_message_id": user_msg_id,
            "assistant_message_id": assistant_msg_id,
            "content": response_text,
            "citations": all_citations,
            "confidence_score": conf_score,
            "confidence_desc": conf_desc,
            "model": model,
        }

    def generate_stream(
        self,
        question: str,
        session_id: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
        retriever_k: int = RETRIEVER_K,
        persona: str = "",
        web_search: bool = False,
        hybrid: bool = HYBRID_SEARCH_ENABLED,
        rerank: bool = RERANKING_ENABLED,
        user_id: str = "default_user",
    ) -> Generator[str, None, None]:
        """
        Executes streaming RAG pipeline, yielding SSE formatted strings:
          event: metadata\ndata: {...}\n\n
          event: token\ndata: {...}\n\n
          event: citations\ndata: {...}\n\n
          event: done\ndata: {...}\n\n
        """
        # Ensure session exists
        if not session_id:
            session_id = self.store.create_session(
                title=question[:40].strip() or "New Chat",
                model=model,
                temperature=temperature,
                retriever_k=retriever_k,
                persona=persona,
                web_search=web_search,
                user_id=user_id,
            )

        # Record user question in DB
        user_msg_id = self.store.add_message(
            session_id=session_id,
            role="user",
            content=question,
        )

        # Notify stream listener of session creation
        yield f"event: metadata\ndata: {json.dumps({'session_id': session_id, 'user_message_id': user_msg_id})}\n\n"

        # Build memory (prior turns only)
        memory = self._prepare_memory(session_id)
        # remove the user question just added so memory doesn't double-count it
        if memory.messages and memory.messages[-1]["content"] == question:
            memory.messages.pop()

        db = retrieval_service.faiss_store
        bm25 = retrieval_service.bm25_retriever
        web_citations: List[Dict[str, Any]] = []

        token_gen, citations, avg_sim = execute_rag_pipeline(
            db=db,
            memory=memory,
            question=question,
            temperature=temperature,
            retriever_k=retriever_k,
            model=model,
            persona=persona,
            web_search=web_search,
            web_citations=web_citations,
            bm25=bm25,
            hybrid=hybrid,
            rerank=rerank,
        )

        # Emit citations as soon as retrieved
        all_citations = citations + (web_citations if web_search else [])
        yield f"event: citations\ndata: {json.dumps({'citations': all_citations})}\n\n"

        accumulated_tokens = []
        for token in token_gen:
            accumulated_tokens.append(token)
            yield f"event: token\ndata: {json.dumps({'token': token})}\n\n"

        full_content = "".join(accumulated_tokens)
        conf_score, conf_desc = _calculate_confidence(avg_sim, citations)

        # Save assistant message to DB
        assistant_msg_id = self.store.add_message(
            session_id=session_id,
            role="assistant",
            content=full_content,
            citations=all_citations,
            confidence_score=conf_score,
            confidence_desc=conf_desc,
        )

        done_payload = {
            "session_id": session_id,
            "assistant_message_id": assistant_msg_id,
            "confidence_score": conf_score,
            "confidence_desc": conf_desc,
            "content_length": len(full_content),
        }
        yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"


# Global singleton instance
rag_service = RAGService()
