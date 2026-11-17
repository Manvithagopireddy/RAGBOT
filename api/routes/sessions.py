"""
sessions.py — Chat Session and History Management Routes.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import get_chat_store, get_current_user_optional
from api.schemas import (
    MessageItem,
    SessionCreateRequest,
    SessionDetailResponse,
    SessionResponse,
    SessionUpdateRequest,
)
from storage import ChatStore

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.get("", response_model=List[SessionResponse])
def list_sessions(
    store: ChatStore = Depends(get_chat_store),
    current_user: dict = Depends(get_current_user_optional),
):
    """
    Returns all chat sessions belonging to the current user.
    """
    sessions = store.get_all_sessions(user_id=current_user["user_id"])
    return [SessionResponse(**s) for s in sessions]


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: SessionCreateRequest,
    store: ChatStore = Depends(get_chat_store),
    current_user: dict = Depends(get_current_user_optional),
):
    """
    Creates a new conversational session.
    """
    session_id = store.create_session(
        title=payload.title or "New Chat",
        model=payload.model or "gemini-2.5-flash",
        temperature=payload.temperature or 0.7,
        retriever_k=payload.retriever_k or 4,
        persona=payload.persona or "",
        web_search=bool(payload.web_search),
        user_id=current_user["user_id"],
    )
    sess = store.get_session(session_id)
    if not sess:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve newly created session.",
        )
    return SessionResponse(**sess)


@router.get("/{session_id}", response_model=SessionDetailResponse)
def get_session_details(
    session_id: str,
    store: ChatStore = Depends(get_chat_store),
    current_user: dict = Depends(get_current_user_optional),
):
    """
    Retrieves session settings and chronological message history.
    """
    sess = store.get_session(session_id)
    if not sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )

    # Check user ownership if not default_user
    if current_user["user_id"] != "default_user" and sess.get("user_id") != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this session.",
        )

    raw_messages = store.get_messages(session_id)
    messages = [MessageItem(**m) for m in raw_messages]

    return SessionDetailResponse(
        **sess,
        messages=messages,
    )


@router.patch("/{session_id}", response_model=SessionResponse)
def update_session(
    session_id: str,
    payload: SessionUpdateRequest,
    store: ChatStore = Depends(get_chat_store),
    current_user: dict = Depends(get_current_user_optional),
):
    """
    Updates session title or generation parameters.
    """
    sess = store.get_session(session_id)
    if not sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )

    if current_user["user_id"] != "default_user" and sess.get("user_id") != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this session.",
        )

    if payload.title is not None:
        store.rename_session(session_id, payload.title)

    # Update settings if provided
    current_temp = payload.temperature if payload.temperature is not None else sess["temperature"]
    current_k = payload.retriever_k if payload.retriever_k is not None else sess["retriever_k"]
    current_rag = payload.rag_enabled if payload.rag_enabled is not None else bool(sess["rag_enabled"])
    current_model = payload.model if payload.model is not None else sess["model"]
    current_persona = payload.persona if payload.persona is not None else sess["persona"]
    current_web = payload.web_search if payload.web_search is not None else bool(sess["web_search"])

    store.update_session_settings(
        session_id=session_id,
        temperature=current_temp,
        retriever_k=current_k,
        rag_enabled=current_rag,
        model=current_model,
        persona=current_persona,
        web_search=current_web,
    )

    updated_sess = store.get_session(session_id)
    if not updated_sess:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve updated session.",
        )
    return SessionResponse(**updated_sess)


@router.delete("/{session_id}")
def delete_session(
    session_id: str,
    store: ChatStore = Depends(get_chat_store),
    current_user: dict = Depends(get_current_user_optional),
):
    """
    Deletes a session and its associated messages.
    """
    sess = store.get_session(session_id)
    if not sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )

    if current_user["user_id"] != "default_user" and sess.get("user_id") != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this session.",
        )

    store.delete_session(session_id)
    return {"message": f"Session '{session_id}' deleted successfully."}
