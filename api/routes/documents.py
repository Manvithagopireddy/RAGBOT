"""
documents.py — Document Upload, Catalog, and Index Management Routes.
"""
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from api.dependencies import (
    check_rate_limit,
    get_current_user_optional,
    get_ingestion_service,
)
from api.schemas import DocumentResponse, DocumentUploadResponse
from services.ingestion_service import IngestionService

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/upload", response_model=DocumentUploadResponse, dependencies=[Depends(check_rate_limit)])
async def upload_document(
    file: UploadFile = File(...),
    ingestion: IngestionService = Depends(get_ingestion_service),
    current_user: dict = Depends(get_current_user_optional),
):
    """
    Uploads and indexes a document (PDF, DOCX, TXT, CSV, PPTX) into FAISS and BM25.
    """
    try:
        raw_bytes = await file.read()
        doc_record = ingestion.ingest_bytes(
            raw_bytes=raw_bytes,
            filename=file.filename or "upload.bin",
            user_id=current_user["user_id"],
        )
        return DocumentUploadResponse(
            message=f"Document '{doc_record['filename']}' successfully uploaded and indexed.",
            document=DocumentResponse(**doc_record),
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document ingestion error: {exc}",
        )


@router.get("", response_model=List[DocumentResponse])
def list_documents(
    ingestion: IngestionService = Depends(get_ingestion_service),
    current_user: dict = Depends(get_current_user_optional),
):
    """
    Lists all documents belonging to the current user (or public/default documents).
    """
    docs = ingestion.list_documents(user_id=current_user["user_id"])
    return [DocumentResponse(**d) for d in docs]


@router.delete("/{document_id}")
def delete_document(
    document_id: str,
    ingestion: IngestionService = Depends(get_ingestion_service),
    current_user: dict = Depends(get_current_user_optional),
):
    """
    Deletes a document from the catalog and filesystem.
    """
    success = ingestion.delete_document(document_id, user_id=current_user["user_id"])
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found or access denied.",
        )
    return {"message": f"Document '{document_id}' deleted successfully."}


@router.post("/{document_id}/reindex", response_model=DocumentResponse)
def reindex_document(
    document_id: str,
    ingestion: IngestionService = Depends(get_ingestion_service),
    current_user: dict = Depends(get_current_user_optional),
):
    """
    Re-chunks and re-indexes an existing document from disk.
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
            detail=f"Reindexing failed: {exc}",
        )
