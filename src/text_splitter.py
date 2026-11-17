"""
text_splitter.py — Token-aware and character-aware document chunking.

Features:
  - Token-aware chunking using tiktoken (cl100k_base) to ensure chunks strictly respect LLM context budgets.
  - Character-based recursive chunking fallback.
  - Configurable chunk size and chunk overlap.
  - Unique chunk IDs and metadata enrichment (chunk_index, chunk_id).
"""
from typing import List, Optional

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config.settings import (
    CHUNK_METHOD,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    TOKEN_CHUNK_OVERLAP,
    TOKEN_CHUNK_SIZE,
)
from src.logger import get_logger

logger = get_logger(__name__)


def get_text_splitter(
    method: str = CHUNK_METHOD,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> RecursiveCharacterTextSplitter:
    """
    Factory creating a text splitter.
    If method is 'token', uses tiktoken cl100k_base tokenizer.
    If method is 'character', uses character length function.
    """
    if method == "token":
        c_size = chunk_size if chunk_size is not None else TOKEN_CHUNK_SIZE
        c_overlap = chunk_overlap if chunk_overlap is not None else TOKEN_CHUNK_OVERLAP
        try:
            splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
                encoding_name="cl100k_base",
                chunk_size=c_size,
                chunk_overlap=c_overlap,
                separators=["\n\n", "\n", " ", ""],
            )
            logger.info(f"Initialized token-aware text splitter (tokens={c_size}, overlap={c_overlap})")
            return splitter
        except Exception as e:
            logger.warning(f"Could not initialize tiktoken splitter: {e}. Falling back to character splitter.")

    # Character-based recursive splitter fallback
    c_size = chunk_size if chunk_size is not None else CHUNK_SIZE
    c_overlap = chunk_overlap if chunk_overlap is not None else CHUNK_OVERLAP
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=c_size,
        chunk_overlap=c_overlap,
        length_function=len,
        separators=["\n\n", "\n", " ", ""],
    )
    logger.info(f"Initialized character-based text splitter (chars={c_size}, overlap={c_overlap})")
    return splitter


def split_documents(
    documents: List[Document],
    method: str = CHUNK_METHOD,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> List[Document]:
    """
    Splits a list of Document objects into chunks using token or character splitting,
    preserving metadata and assigning deterministic unique chunk IDs.
    """
    if not documents:
        return []

    splitter = get_text_splitter(method=method, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    try:
        chunks = splitter.split_documents(documents)

        # Enrich chunks with consistent chunk IDs and tracking metadata
        for idx, chunk in enumerate(chunks):
            source = chunk.metadata.get("source", "unknown")
            page = chunk.metadata.get("page", 0)
            chunk.metadata["chunk_index"] = idx
            chunk.metadata["chunk_id"] = f"{source}::p{page}::c{idx}"

        logger.info(f"Generated {len(chunks)} text chunks from {len(documents)} original documents.")
        return chunks
    except Exception as e:
        logger.error(f"Error splitting documents: {e}")
        raise e
