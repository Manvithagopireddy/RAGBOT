import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure the root project folder is in the path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.settings import KNOWLEDGE_BASE_DIR, FAISS_INDEX_PATH
from vectorstore import get_or_build_vector_store
from src.retriever import retrieve_relevant_chunks, format_retrieved_context
from src.llm import get_llm
from chat_manager import ChatMemory
from rag import execute_rag_pipeline

def test_rag_backend():
    print("=" * 60)
    print("AI TECH ASSISTANT - BACKEND DIAGNOSTIC TEST")
    print("=" * 60)
    
    # 1. Load env
    load_dotenv()
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        print("[ERROR] GOOGLE_API_KEY environment variable is not set in .env")
        print("Please configure your Gemini API Key in the .env file before running.")
        return
    else:
        print("[OK] Env check: GOOGLE_API_KEY found.")

    # 2. Check PDFs
    pdfs = list(KNOWLEDGE_BASE_DIR.glob("*.pdf"))
    print(f"[OK] Knowledge base check: Found {len(pdfs)} PDF(s) in {KNOWLEDGE_BASE_DIR}")
    if len(pdfs) == 0:
        print("[WARN] No PDFs found. Please run 'python scripts/generate_mock_knowledge.py' first.")

    # 3. Load or Build Vector Store
    print("\n[Step 1] Loading/Building Vector Store...")
    db = get_or_build_vector_store()
    if db is None:
        print("[ERROR] Failed to load or build vector database.")
        return
    print("[OK] Vector DB: Ready.")

    # 4. Run Retrieval Test
    print("\n[Step 2] Testing Semantic Search retrieval...")
    test_query = "What is the difference between LangGraph and CrewAI?"
    print(f"Query: '{test_query}'")
    
    results = retrieve_relevant_chunks(db, test_query, k=3)
    if not results:
        print("[ERROR] No matching chunks retrieved from vector database.")
        return
        
    print(f"[OK] Retrieved {len(results)} relevant chunks:")
    for idx, (doc, score) in enumerate(results):
        source = doc.metadata.get("source", "Unknown")
        page = doc.metadata.get("page", 0) + 1
        print(f"   [{idx + 1}] Source: {source} (Page {page}) | Similarity: {score:.4f}")
        print(f"       Text snippet: {doc.page_content.strip()[:140]}...")
        
    # 5. Run LLM Grounding Test
    print("\n[Step 3] Querying Google Gemini 2.5 Flash via RAG...")
    memory = ChatMemory()
    
    token_generator, citations, avg_sim = execute_rag_pipeline(db, memory, test_query)
    
    print("\nResponse stream from LLM:")
    print("-" * 50)
    full_response = ""
    for chunk in token_generator:
        # Avoid print issues during streaming output
        try:
            sys.stdout.write(chunk)
            sys.stdout.flush()
        except UnicodeEncodeError:
            # Fallback to ascii representation if console fails
            sys.stdout.write(chunk.encode('ascii', errors='replace').decode('ascii'))
            sys.stdout.flush()
        full_response += chunk
    print("\n" + "-" * 50)
    print("[OK] LLM query successfully completed.")
    print(f"[OK] Avg Context Similarity: {avg_sim:.4f}")
    print(f"[OK] Citations loaded: {[c['source'] for c in citations]}")
    print("=" * 60)
    print("RAG BACKEND VERIFICATION SUCCESSFUL!")
    print("=" * 60)

if __name__ == "__main__":
    test_rag_backend()
