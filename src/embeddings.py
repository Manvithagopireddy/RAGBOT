from langchain_huggingface import HuggingFaceEmbeddings  # pyright: ignore [missing-import]
from config.settings import EMBEDDING_MODEL_NAME
from src.logger import get_logger

logger = get_logger(__name__)

# Cache the embeddings instance to avoid loading it multiple times
_embeddings_instance = None

def get_embeddings() -> HuggingFaceEmbeddings:
    """Initializes and returns the HuggingFace Sentence Transformers embeddings model.
    Uses a singleton pattern to reuse the model across calls.
    """
    global _embeddings_instance
    if _embeddings_instance is None:
        logger.info(f"Initializing HuggingFace embeddings: {EMBEDDING_MODEL_NAME}")
        try:
            # Note: sentence-transformers model all-MiniLM-L6-v2 runs locally on CPU or GPU
            _embeddings_instance = HuggingFaceEmbeddings(
                model_name=EMBEDDING_MODEL_NAME,
                model_kwargs={"device": "cpu"}  # Force CPU for stability and cross-compatibility
            )
            logger.info("Embeddings initialized successfully.")
        except Exception as e:
            logger.error(f"Error initializing HuggingFace embeddings: {e}")
            raise e
    return _embeddings_instance
