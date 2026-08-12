from pathlib import Path
from typing import Optional
# pyright: ignore [missing-import]
from langchain_community.vectorstores import FAISS
from config.settings import VECTOR_STORE_DIR, FAISS_INDEX_NAME, KNOWLEDGE_BASE_DIR, FAISS_INDEX_PATH
from src.embeddings import get_embeddings
from src.document_loader import load_all_documents
from src.text_splitter import split_documents
from src.logger import get_logger

logger = get_logger(__name__)

def build_vector_store() -> Optional[FAISS]:
    """Loads PDFs, splits them into chunks, builds a new FAISS vector store, and saves it locally."""
    logger.info("Starting build process for the FAISS vector database...")
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
            
        # Embed and Index
        embeddings = get_embeddings()
        logger.info("Generating embeddings and building FAISS index...")
        db = FAISS.from_documents(chunks, embeddings)
        
        # Save
        VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
        db.save_local(folder_path=str(VECTOR_STORE_DIR), index_name=FAISS_INDEX_NAME)
        logger.info(f"FAISS vector store saved locally at {VECTOR_STORE_DIR}")
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
        # Note: allow_dangerous_deserialization=True is required to load local pickle/faiss files with LangChain
        db = FAISS.load_local(
            folder_path=str(VECTOR_STORE_DIR),
            embeddings=embeddings,
            index_name=FAISS_INDEX_NAME,
            allow_dangerous_deserialization=True
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
