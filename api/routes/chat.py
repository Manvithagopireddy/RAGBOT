"""
chat.py — Conversational RAG Endpoints (Synchronous and Server-Sent Events Streaming).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from api.dependencies import (
    check_rate_limit,
    get_current_user,
    get_rag_service,
)
from api.schemas import ChatRequest, ChatResponse
from services.rag_service import RAGService
from src.security import sanitize_html

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse, dependencies=[Depends(check_rate_limit)])
def send_chat_message(
    payload: ChatRequest,
    rag: RAGService = Depends(get_rag_service),
    current_user: dict = Depends(get_current_user),
):
    """
    Submits a user prompt, retrieves relevant knowledge base context via hybrid search,
    invokes Gemini, and returns a grounded response with source citations.
    Requires valid JWT authentication.
    """
    clean_question = sanitize_html(payload.message.strip())
    if not clean_question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message content cannot be empty.",
        )

    try:
        result = rag.generate_response(
            question=clean_question,
            session_id=payload.session_id,
            model=payload.model or "gemini-2.5-flash",
            temperature=payload.temperature if payload.temperature is not None else 0.7,
            retriever_k=payload.retriever_k or 4,
            persona=payload.persona or "",
            web_search=bool(payload.web_search),
            hybrid=bool(payload.hybrid),
            rerank=bool(payload.rerank),
            user_id=current_user["user_id"],
        )
        return ChatResponse(
            session_id=result["session_id"],
            user_message_id=result["user_message_id"],
            assistant_message_id=result["assistant_message_id"],
            content=result["content"],
            citations=result["citations"],
            confidence_score=result["confidence_score"],
            confidence_desc=result["confidence_desc"],
            model=result["model"],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Chat generation failed. Please try again.",
        ) from exc


@router.post("/stream", dependencies=[Depends(check_rate_limit)])
def stream_chat_message(
    payload: ChatRequest,
    rag: RAGService = Depends(get_rag_service),
    current_user: dict = Depends(get_current_user),
):
    """
    Streams a grounded response in real-time using Server-Sent Events (SSE).
    Emits events: metadata, citations, token, and done.
    Requires valid JWT authentication.
    """
    clean_question = sanitize_html(payload.message.strip())
    if not clean_question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message content cannot be empty.",
        )

    stream_generator = rag.generate_stream(
        question=clean_question,
        session_id=payload.session_id,
        model=payload.model or "gemini-2.5-flash",
        temperature=payload.temperature if payload.temperature is not None else 0.7,
        retriever_k=payload.retriever_k or 4,
        persona=payload.persona or "",
        web_search=bool(payload.web_search),
        hybrid=bool(payload.hybrid),
        rerank=bool(payload.rerank),
        user_id=current_user["user_id"],
    )

    return StreamingResponse(
        stream_generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
