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
        Deletes a document completely:
        1. Validates ownership (returns False if not found/unauthorized).
        2. Removes the uploaded file from disk.
        3. Rebuilds the user's FAISS and BM25 indexes excluding the deleted document's chunks.
           This is the only safe way to remove vectors from FAISS (no incremental vector deletion).
        4. Persists the updated index to disk.
        5. Removes the database record.

        Note: Historical chat messages that quoted this document's content are preserved as-is.
        Only the retrieval index is updated — past citations remain in message history.
        """
        doc = self.store.get_document(document_id, user_id=user_id)
        if not doc:
            return False

        # 1. Remove file from disk if present
        file_path = doc.get("file_path")
        if file_path:
            p = Path(file_path)
            p.unlink(missing_ok=True)

        # 2. Delete database record first (before index rebuild to avoid race)
        success = self.store.delete_document(document_id, user_id=user_id)
        if not success:
            logger.warning(f"Database deletion returned False for document {document_id}")

        # 3. Rebuild FAISS and BM25 without the deleted document's chunks.
        #    Strategy: re-index all *remaining* documents for this user from disk.
        #    Chunks from the deleted doc will be excluded because they no longer appear in the catalog.
        self._rebuild_indexes_excluding(document_id)

        logger.info(f"Deleted document {document_id} and rebuilt retrieval indexes (success: {success})")
        return success

    def _rebuild_indexes_excluding(self, excluded_document_id: str) -> None:
        """
        Rebuilds the global FAISS and BM25 indexes from scratch, excluding
        any chunk whose document_id metadata matches excluded_document_id.

        This is the safe approach for FAISS which doesn't support incremental deletion.
        The rebuilt index still contains knowledge-base documents and all other users'
        documents (filtered at retrieval time by ownership metadata).
        """
        try:
            current_bm25 = retrieval_service.bm25_retriever

            # Collect surviving chunks from BM25 (excludes the deleted doc)
            surviving_chunks = []
            if current_bm25 is not None and current_bm25.documents:
                for chunk in current_bm25.documents:
                    chunk_doc_id = chunk.metadata.get("document_id")
                    if chunk_doc_id != excluded_document_id:
                        surviving_chunks.append(chunk)

            if not surviving_chunks:
                # All chunks removed — clear indexes
                VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
                retrieval_service.set_indexes(None, None)
                # Remove persisted index files
                for f in VECTOR_STORE_DIR.glob(f"{FAISS_INDEX_NAME}.*"):
                    f.unlink(missing_ok=True)
                BM25_INDEX_PATH.unlink(missing_ok=True)
                logger.info(f"All chunks removed after deleting {excluded_document_id}. Cleared indexes.")
                return

            # Rebuild BM25 from surviving chunks
            new_bm25 = build_bm25_index(surviving_chunks, save_path=BM25_INDEX_PATH)

            # Rebuild FAISS from surviving chunks
            embeddings = get_embeddings()
            new_faiss = FAISS.from_documents(surviving_chunks, embeddings)
            VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
            new_faiss.save_local(folder_path=str(VECTOR_STORE_DIR), index_name=FAISS_INDEX_NAME)

            retrieval_service.set_indexes(new_faiss, new_bm25)
            logger.info(
                f"Rebuilt indexes after deleting {excluded_document_id}: "
                f"{len(surviving_chunks)} surviving chunks, "
                f"{new_faiss.index.ntotal if hasattr(new_faiss, 'index') else '?'} FAISS vectors."
            )
        except Exception as exc:
            logger.error(f"Index rebuild failed after deleting {excluded_document_id}: {exc}", exc_info=True)
            # Do not re-raise — the DB deletion already succeeded. The stale FAISS data
            # will not appear in results for this user because the ownership filter in
            # retrieval_service excludes it (document_id no longer in user's catalog).

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
