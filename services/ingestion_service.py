"""
ingestion_service.py — Document Ingestion and Indexing Service.

Handles multi-format document ingestion (PDF, DOCX, TXT, CSV, PPTX),
file validation, chunking, FAISS vector updating, BM25 keyword index updating,
and SQLite catalog recording.
"""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_community.vectorstores import FAISS

from config.settings import (
    BM25_INDEX_PATH,
    CHAT_DB_PATH,
    FAISS_INDEX_NAME,
    UPLOADS_DIR,
    VECTOR_STORE_DIR,
)
from services.retrieval_service import retrieval_service
from src.bm25_retriever import BM25Retriever, build_bm25_index
from src.document_loader import load_file
from src.embeddings import get_embeddings
from src.file_handler import MAX_UPLOAD_BYTES, SUPPORTED_EXTENSIONS, _safe_filename
from src.logger import get_logger
from src.text_splitter import split_documents
from storage import ChatStore

logger = get_logger(__name__)


class IngestionService:
    """
    Manages document upload, validation, parsing, chunking,
    index merging, and document database persistence.
    """

    def __init__(self, db_store: Optional[ChatStore] = None):
        self.store = db_store or ChatStore(CHAT_DB_PATH)

    def ingest_bytes(
        self,
        raw_bytes: bytes,
        filename: str,
        user_id: str = "default_user",
    ) -> Dict[str, Any]:
        """
        Validates, saves, splits, indexes, and records an uploaded file.
        Returns a dict with document details, chunk count, and index status.
        Raises ValueError on validation failure.
        """
        safe_name = _safe_filename(filename)
        ext = Path(safe_name).suffix.lower()

        # 1. Validation
        if ext not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

        if len(raw_bytes) == 0:
            raise ValueError("File is empty.")

        if len(raw_bytes) > MAX_UPLOAD_BYTES:
            mb = len(raw_bytes) / (1024 * 1024)
            raise ValueError(
                f"File is too large ({mb:.1f} MB). Maximum allowed size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
            )

        # 2. Compute Checksum
        checksum = hashlib.sha256(raw_bytes).hexdigest()

        # Check if identical checksum already exists for this user
        existing_docs = self.store.get_documents(user_id=user_id)
        for doc in existing_docs:
            if doc.get("checksum") == checksum and doc.get("status") == "indexed":
                logger.info(f"Duplicate document detected (checksum: {checksum[:8]}...). Returning existing.")
                return doc

        # 3. Save to disk
        doc_id = str(uuid.uuid4())
        unique_prefix = doc_id[:8]
        dest_filename = f"upload_{unique_prefix}_{safe_name}"
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        dest_path = UPLOADS_DIR / dest_filename
        dest_path.write_bytes(raw_bytes)

        # 4. Load & Parse Document
        try:
            documents = load_file(dest_path)
        except Exception as exc:
            dest_path.unlink(missing_ok=True)
            raise ValueError(f"Failed to parse document content: {exc}")

        if not documents:
            dest_path.unlink(missing_ok=True)
            raise ValueError(f"No extractable text found in '{safe_name}'.")

        # Inject original clean filename into metadata
        for d in documents:
            d.metadata["source"] = safe_name
            d.metadata["document_id"] = doc_id

        # 5. Split Chunks
        chunks = split_documents(documents)
        if not chunks:
            dest_path.unlink(missing_ok=True)
            raise ValueError(f"Text splitting produced no chunks for '{safe_name}'.")

        # 6. Embed & Update FAISS
        try:
            embeddings = get_embeddings()
            new_faiss = FAISS.from_documents(chunks, embeddings)
            current_faiss = retrieval_service.faiss_store

            if current_faiss is not None:
                current_faiss.merge_from(new_faiss)
                merged_faiss = current_faiss
            else:
                merged_faiss = new_faiss

            VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
            merged_faiss.save_local(folder_path=str(VECTOR_STORE_DIR), index_name=FAISS_INDEX_NAME)
        except Exception as exc:
            logger.error(f"Vector indexing failed for {safe_name}: {exc}")
            dest_path.unlink(missing_ok=True)
            raise RuntimeError(f"Vector indexing failed: {exc}")

        # 7. Update BM25 Keyword Index
        new_bm25: Optional[BM25Retriever] = None
        try:
            current_bm25 = retrieval_service.bm25_retriever
            if current_bm25 is not None and current_bm25.documents:
                all_chunks = list(current_bm25.documents) + list(chunks)
            else:
                all_chunks = chunks

            new_bm25 = build_bm25_index(all_chunks, save_path=BM25_INDEX_PATH)
        except Exception as exc:
            logger.warning(f"BM25 index update failed (continuing with FAISS): {exc}")
            new_bm25 = retrieval_service.bm25_retriever

        # Update singleton references
        retrieval_service.set_indexes(merged_faiss, new_bm25)

        # 8. Record in Database
        doc_record = self.store.add_document(
            document_id=doc_id,
            filename=safe_name,
            file_path=str(dest_path),
            file_type=ext.lstrip("."),
            file_size=len(raw_bytes),
            chunk_count=len(chunks),
            checksum=checksum,
            status="indexed",
            user_id=user_id,
        )

        logger.info(f"Successfully ingested and indexed '{safe_name}' ({len(chunks)} chunks, ID: {doc_id})")
        return doc_record

    def list_documents(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns catalog of documents."""
        return self.store.get_documents(user_id=user_id)

    def get_document(self, document_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Returns document details by ID."""
        return self.store.get_document(document_id=document_id, user_id=user_id)

    def delete_document(self, document_id: str, user_id: Optional[str] = None) -> bool:
        """
        Deletes a document from the catalog and filesystem.
        """
        doc = self.store.get_document(document_id, user_id=user_id)
        if not doc:
            return False

        # Remove file from disk if present
        file_path = doc.get("file_path")
        if file_path:
            p = Path(file_path)
            p.unlink(missing_ok=True)

        # Delete database record
        success = self.store.delete_document(document_id, user_id=user_id)
        logger.info(f"Deleted document {document_id} (success: {success})")
        return success

    def reindex_document(self, document_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Re-reads an existing uploaded document from disk and re-indexes its chunks.
        """
        doc = self.store.get_document(document_id, user_id=user_id)
        if not doc:
            raise ValueError(f"Document {document_id} not found.")

        file_path = Path(doc["file_path"])
        if not file_path.exists():
            raise FileNotFoundError(f"Underlying file {file_path.name} not found on disk.")

        documents = load_file(file_path)
        if not documents:
            raise ValueError("Failed to extract content during re-indexing.")

        for d in documents:
            d.metadata["source"] = doc["filename"]
            d.metadata["document_id"] = document_id

        chunks = split_documents(documents)
        embeddings = get_embeddings()
        new_faiss = FAISS.from_documents(chunks, embeddings)

        current_faiss = retrieval_service.faiss_store
        if current_faiss is not None:
            current_faiss.merge_from(new_faiss)
            merged = current_faiss
        else:
            merged = new_faiss

        merged.save_local(str(VECTOR_STORE_DIR), FAISS_INDEX_NAME)
        retrieval_service.set_indexes(merged, retrieval_service.bm25_retriever)

        self.store.update_document_status(document_id, status="indexed", chunk_count=len(chunks))
        doc["chunk_count"] = len(chunks)
        doc["status"] = "indexed"
        return doc


# Global singleton instance
ingestion_service = IngestionService()
