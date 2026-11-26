"""
documents.py — Document Upload, Catalog, and Index Management Routes.
All endpoints require valid JWT authentication. User ID is derived from the token — never from the request body.
"""
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from starlette.concurrency import run_in_threadpool

from api.dependencies import (
    check_rate_limit,
    get_current_user,
    get_ingestion_service,
)
from api.schemas import DocumentResponse, DocumentUploadResponse
from services.ingestion_service import IngestionService
from src.file_handler import MAX_UPLOAD_BYTES

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/upload", response_model=DocumentUploadResponse, dependencies=[Depends(check_rate_limit)])
async def upload_document(
    file: UploadFile = File(...),
    ingestion: IngestionService = Depends(get_ingestion_service),
    current_user: dict = Depends(get_current_user),
):
    """
    Uploads and indexes a document (PDF, DOCX, TXT, CSV, PPTX) into FAISS and BM25.
    Document is owned by the authenticated user. User ID is derived from JWT — never from body.
    """
    try:
        raw_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(raw_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File exceeds upload limit.")
        doc_record = await run_in_threadpool(
            ingestion.ingest_bytes,
            raw_bytes=raw_bytes,
            filename=file.filename or "upload.bin",
            user_id=current_user["user_id"],
        )
        return DocumentUploadResponse(
            message=f"Document '{doc_record['filename']}' successfully uploaded and indexed.",
            document=DocumentResponse(**doc_record),
        )
    except HTTPException:
        raise
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document ingestion failed. Please try again.",
        ) from exc


@router.get("", response_model=List[DocumentResponse])
def list_documents(
    ingestion: IngestionService = Depends(get_ingestion_service),
    current_user: dict = Depends(get_current_user),
):
    """
    Lists all documents belonging to the authenticated user only.
    """
    docs = ingestion.list_documents(user_id=current_user["user_id"])
    return [DocumentResponse(**d) for d in docs]


@router.delete("/{document_id}")
def delete_document(
    document_id: str,
    ingestion: IngestionService = Depends(get_ingestion_service),
    current_user: dict = Depends(get_current_user),
):
    """
    Deletes a document from the catalog, filesystem, FAISS index, and BM25 index.
    Returns 404 if the document does not belong to the authenticated user.
    """
    success = ingestion.delete_document(document_id, user_id=current_user["user_id"])
    if not success:
        # Return 404 — not 403 — to avoid confirming existence to unauthorized callers
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )
    return {"message": f"Document '{document_id}' deleted successfully."}


@router.post("/{document_id}/reindex", response_model=DocumentResponse)
def reindex_document(
    document_id: str,
    ingestion: IngestionService = Depends(get_ingestion_service),
    current_user: dict = Depends(get_current_user),
):
    """
    Re-chunks and re-indexes an existing document from disk.
    Validates ownership before re-indexing.
    """
    try:
        doc = ingestion.reindex_document(document_id, user_id=current_user["user_id"])
        return DocumentResponse(**doc)
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(fnf))
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Reindexing failed. Please try again.",
        ) from exc
