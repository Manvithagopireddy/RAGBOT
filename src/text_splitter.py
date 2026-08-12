from typing import List
# pyright: ignore [missing-import]
from langchain_core.documents import Document
# pyright: ignore [missing-import]
from langchain_text_splitters import RecursiveCharacterTextSplitter
from config.settings import CHUNK_SIZE, CHUNK_OVERLAP
from src.logger import get_logger

logger = get_logger(__name__)

def split_documents(documents: List[Document]) -> List[Document]:
    """Splits a list of Document objects into chunks using RecursiveCharacterTextSplitter."""
    logger.info(f"Splitting {len(documents)} document pages with chunk_size={CHUNK_SIZE}, chunk_overlap={CHUNK_OVERLAP}")
    
    # Recursive splitter is intelligent; it splits on paragraphs, sentences, and words to avoid context breakages
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )
    
    try:
        chunks = splitter.split_documents(documents)
        logger.info(f"Generated {len(chunks)} text chunks from original documents.")
        return chunks
    except Exception as e:
        logger.error(f"Error splitting documents: {e}")
        raise e
