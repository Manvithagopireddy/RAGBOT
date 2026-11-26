"""
diagnostics.py — Retrieval Diagnostics and Inspection Routes.
Requires valid JWT authentication. Passes user_id to ensure retrieval isolation.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import check_rate_limit, get_current_user, get_retrieval_service
from api.schemas import DiagnosticsRequest, DiagnosticsResponse
from services.retrieval_service import RetrievalService
from src.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/diagnostics", tags=["Diagnostics"])


@router.post("/retrieve", response_model=DiagnosticsResponse, dependencies=[Depends(check_rate_limit)])
def run_retrieval_diagnostics(
    payload: DiagnosticsRequest,
    retrieval: RetrievalService = Depends(get_retrieval_service),
    current_user: dict = Depends(get_current_user),
):
    """
    Executes hybrid retrieval and reranking for inspection, returning
    candidate chunks, similarity scores, source metadata, and retrieval latency.
    Scoped to the authenticated user's documents.
    """
    try:
        results, diagnostics = retrieval.retrieve(
            query=payload.query,
            k=payload.k or 4,
            threshold=payload.threshold or 0.0,
            hybrid=bool(payload.hybrid),
            rerank=bool(payload.rerank),
            user_id=current_user["user_id"],
        )

        formatted_results = [
            {
                "source": r.source,
                "page": r.page,
                "similarity": round(r.similarity, 4),
                "distance": round(r.distance, 4) if r.distance is not None else None,
                "text_snippet": r.text[:300] + ("..." if len(r.text) > 300 else ""),
            }
            for r in results
        ]

        return DiagnosticsResponse(
            query=payload.query,
            results_count=len(results),
            latency_ms=diagnostics.get("latency_ms", 0.0),
            diagnostics=diagnostics,
            results=formatted_results,
        )
    except Exception as exc:
        logger.error(f"Diagnostics execution error: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Diagnostics execution failed. Please check server logs.",
        )
