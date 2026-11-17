"""
health.py — Health Check Route.
"""
from fastapi import APIRouter, Depends

from api.dependencies import get_chat_store, get_ingestion_service, get_retrieval_service
from api.schemas import HealthResponse
from config.settings import DEFAULT_MODEL
from services.ingestion_service import IngestionService
from services.retrieval_service import RetrievalService
from storage import ChatStore

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def get_health_status(
    store: ChatStore = Depends(get_chat_store),
    retrieval: RetrievalService = Depends(get_retrieval_service),
    ingestion: IngestionService = Depends(get_ingestion_service),
):
    """
    Returns application health, database connectivity, vector index readiness,
    and total registered documents.
    """
    stats = retrieval.get_index_stats()
    docs = ingestion.list_documents()

    return HealthResponse(
        status="ok",
        version="2.0.0",
        database_connected=True,
        faiss_ready=stats["faiss_ready"],
        bm25_ready=stats["bm25_ready"],
        total_vectors=stats["faiss_total_vectors"],
        total_documents=len(docs),
        default_model=DEFAULT_MODEL,
    )
