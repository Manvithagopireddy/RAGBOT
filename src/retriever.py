from typing import List, Dict, Any, Tuple
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from config.settings import RETRIEVER_K, SIMILARITY_SCORE_THRESHOLD
from src.logger import get_logger

logger = get_logger(__name__)

def retrieve_relevant_chunks(db: FAISS, query: str, k: int = RETRIEVER_K) -> List[Tuple[Document, float]]:
    """Searches the vector store for chunks matching the query.
    Returns a list of tuples containing the Document and its similarity score.
    """
    logger.info(f"Querying vector store for: '{query}' with k={k}")
    try:
        # similarity_search_with_score returns (Document, float_distance)
        # Note: For FAISS, distance is L2 distance by default. Since embeddings are normalized,
        # L2 distance range is typically [0, 2], where 0 is identical and 2 is opposite.
        # We convert this distance to a normalized similarity score: 1.0 - (distance / 2.0).
        results = db.similarity_search_with_score(query, k=k)
        
        normalized_results = []
        for doc, distance in results:
            # Map distance (0 to 2) to similarity score (1 to 0) and cast to native float to avoid JSON serialization errors
            similarity = float(max(0.0, min(1.0, 1.0 - (float(distance) / 2.0))))
            normalized_results.append((doc, similarity))
            
        logger.info(f"Retrieved {len(normalized_results)} chunks from vector store.")
        return normalized_results
    except Exception as e:
        logger.error(f"Error during vector retrieval: {e}")
        return []

def format_retrieved_context(results: List[Tuple[Document, float]]) -> Tuple[str, List[Dict[str, Any]], float]:
    """Formats retrieved search results for prompt injection and citation display.
    Returns:
        context_text: Merged text chunks for the LLM prompt.
        citations: List of dicts representing sources.
        avg_confidence: Average confidence score from retrieved chunks.
    """
    if not results:
        return "", [], 0.0
        
    context_parts = []
    citations = []
    total_score = 0.0
    
    for idx, (doc, score) in enumerate(results):
        source_name = doc.metadata.get("source", "Unknown PDF")
        page_num = doc.metadata.get("page", 0) + 1 # 0-indexed to 1-indexed for display
        text_content = doc.page_content.strip()
        
        # Format text chunk block for LLM prompt context
        context_block = f"--- Document Source: {source_name} (Page {page_num}) ---\n{text_content}\n"
        context_parts.append(context_block)
        
        # Create citation metadata
        citations.append({
            "id": idx + 1,
            "source": source_name,
            "page": page_num,
            "snippet": text_content[:200] + "...",
            "score": score
        })
        total_score += score
        
    context_text = "\n".join(context_parts)
    avg_confidence = total_score / len(results) if results else 0.0
    
    return context_text, citations, avg_confidence
