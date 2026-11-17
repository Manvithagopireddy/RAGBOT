from typing import Optional

from langchain_community.vectorstores import FAISS

from config.settings import (
    BM25_INDEX_PATH,
    FAISS_INDEX_NAME,
    FAISS_INDEX_PATH,
    KNOWLEDGE_BASE_DIR,
    VECTOR_STORE_DIR,
)
from src.bm25_retriever import BM25Retriever, build_bm25_index
from src.document_loader import load_all_documents
from src.embeddings import get_embeddings
from src.logger import get_logger
from src.text_splitter import split_documents

logger = get_logger(__name__)


def build_vector_store() -> Optional[FAISS]:
    """Loads PDFs, splits them into chunks, builds a new FAISS vector store and BM25 index, and saves both locally."""
    logger.info("Starting build process for the FAISS vector database and BM25 index...")
    try:
        # Load
        documents = load_all_documents(KNOWLEDGE_BASE_DIR)
        if not documents:
            logger.warning("No documents loaded. Vector database build aborted.")
            return None

        # Split
        chunks = split_documents(documents)
        if not chunks:
            logger.warning("No chunks generated. Vector database build aborted.")
            return None

        # Embed and Index with FAISS
        embeddings = get_embeddings()
        logger.info("Generating embeddings and building FAISS index...")
        db = FAISS.from_documents(chunks, embeddings)

        # Save FAISS
        VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
        db.save_local(folder_path=str(VECTOR_STORE_DIR), index_name=FAISS_INDEX_NAME)
        logger.info(f"FAISS vector store saved locally at {VECTOR_STORE_DIR}")

        # Build and Save BM25 Index
        logger.info("Building BM25 keyword index...")
        build_bm25_index(chunks, save_path=BM25_INDEX_PATH)
        logger.info(f"BM25 index saved locally at {BM25_INDEX_PATH}")

        return db
    except Exception as e:
        logger.error(f"Failed to build vector store: {e}")
        return None


def load_vector_store() -> Optional[FAISS]:
    """Loads the FAISS index from disk. Returns None if it does not exist."""
    logger.info("Checking for existing FAISS vector store...")
    if not FAISS_INDEX_PATH.exists():
        logger.warning(f"Vector store file {FAISS_INDEX_PATH} not found.")
        return None

    try:
        embeddings = get_embeddings()
        logger.info(f"Loading local FAISS database from {VECTOR_STORE_DIR}...")
        db = FAISS.load_local(
            folder_path=str(VECTOR_STORE_DIR),
            embeddings=embeddings,
            index_name=FAISS_INDEX_NAME,
            allow_dangerous_deserialization=True,
        )
        logger.info("FAISS vector store loaded successfully.")
        return db
    except Exception as e:
        logger.error(f"Error loading local FAISS index: {e}")
        return None


def get_or_build_vector_store() -> Optional[FAISS]:
    """Gets existing vector store or builds a new one if not present."""
    db = load_vector_store()
    if db is None:
        logger.info("No vector store found. Proceeding to build a new one.")
        db = build_vector_store()
    return db


def get_or_build_bm25_retriever() -> Optional[BM25Retriever]:
    """Loads existing BM25 index from disk or builds a new one from knowledge_base documents."""
    bm25 = BM25Retriever.load(BM25_INDEX_PATH)
    if bm25 is not None and bm25.documents:
        return bm25

    logger.info("No BM25 index found. Building from knowledge base documents...")
    documents = load_all_documents(KNOWLEDGE_BASE_DIR)
    if documents:
        chunks = split_documents(documents)
        if chunks:
            return build_bm25_index(chunks, save_path=BM25_INDEX_PATH)
    return None
