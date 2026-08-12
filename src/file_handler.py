"""
file_handler.py — Handles multi-format uploads (PDF, DOCX, TXT, CSV, PPTX).
Uploaded files are indexed into a session-scoped FAISS store merged with global DB.
"""
import os
import tempfile
from pathlib import Path
from typing import Optional
from src.logger import get_logger

logger = get_logger(__name__)

SUPPORTED_TYPES = [".pdf", ".txt", ".csv", ".docx", ".pptx"]
SUPPORTED_MIME_TYPES = ["pdf", "txt", "csv", "docx", "pptx"]


def index_uploaded_file(uploaded_file, global_db) -> Optional[object]:
    """
    Takes a Streamlit UploadedFile object (any supported type) and merges it
    into a copy of the global FAISS store. Returns the merged FAISS db.
    """
    try:
        from langchain.text_splitter import RecursiveCharacterTextSplitter  # pyright: ignore
        from langchain_community.vectorstores import FAISS  # pyright: ignore
        from src.embeddings import load_embedding_model
        from src.document_loader import load_file
        from config.settings import CHUNK_SIZE, CHUNK_OVERLAP, UPLOADS_DIR

        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        suffix = Path(uploaded_file.name).suffix.lower() or ".pdf"
        tmp_path = UPLOADS_DIR / f"upload_{uploaded_file.name}"

        with open(tmp_path, "wb") as f:
            f.write(uploaded_file.read())

        logger.info(f"Saved uploaded file to: {tmp_path}")

        # Use the unified document loader
        documents = load_file(tmp_path)

        if not documents:
            logger.warning(f"Uploaded file produced no documents: {uploaded_file.name}")
            return global_db

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        )
        chunks = splitter.split_documents(documents)
        logger.info(f"Indexed {len(chunks)} chunks from: {uploaded_file.name}")

        embeddings = load_embedding_model()
        upload_db = FAISS.from_documents(chunks, embeddings)

        if global_db is not None:
            try:
                global_db.merge_from(upload_db)
                logger.info("Successfully merged upload into global FAISS store.")
                return global_db
            except Exception as merge_err:
                logger.warning(f"Merge failed, returning upload-only store: {merge_err}")
                return upload_db
        else:
            return upload_db

    except Exception as e:
        logger.error(f"Error indexing uploaded file: {e}")
        return global_db


def get_file_size_label(uploaded_file) -> str:
    """Returns a human-readable file size string."""
    try:
        size = len(uploaded_file.getvalue())
    except Exception:
        size = 0
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size // 1024} KB"
    else:
        return f"{size // (1024 * 1024)} MB"


def get_file_icon(filename: str) -> str:
    """Returns an emoji icon for the given file type."""
    ext = Path(filename).suffix.lower()
    icons = {
        ".pdf": "📄",
        ".txt": "📝",
        ".csv": "📊",
        ".docx": "📘",
        ".pptx": "📑",
    }
    return icons.get(ext, "📎")
