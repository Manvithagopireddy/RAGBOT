import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"
VECTOR_STORE_DIR = BASE_DIR / "vector_store"
ASSETS_DIR = BASE_DIR / "assets"
CHATS_DIR = BASE_DIR / "chats"
UPLOADS_DIR = BASE_DIR / "uploads"
EVALS_DIR = BASE_DIR / "evals"

# Create directories if they do not exist
KNOWLEDGE_BASE_DIR.mkdir(parents=True, exist_ok=True)
VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
CHATS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Chat history DB path
CHAT_DB_PATH = CHATS_DIR / "chat_history.db"

# Vector store files
FAISS_INDEX_NAME = "index"
FAISS_INDEX_PATH = VECTOR_STORE_DIR / f"{FAISS_INDEX_NAME}.faiss"
PKL_INDEX_PATH = VECTOR_STORE_DIR / f"{FAISS_INDEX_NAME}.pkl"
BM25_INDEX_PATH = VECTOR_STORE_DIR / "bm25_index.pkl"

# Model Configurations
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")

# Available LLM Models
AVAILABLE_MODELS = {
    "⚡ Gemini 2.5 Flash (Fast)": "gemini-2.5-flash",
    "🧠 Gemini 2.5 Pro (Smart)": "gemini-2.5-pro",
    "🌀 Gemini 1.5 Flash (Legacy)": "gemini-1.5-flash",
}
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_MODEL_NAME = DEFAULT_MODEL

DEFAULT_TEMPERATURE = float(os.getenv("DEFAULT_TEMPERATURE", "0.7"))
DEFAULT_MAX_OUTPUT_TOKENS = int(os.getenv("DEFAULT_MAX_OUTPUT_TOKENS", "8192"))

# RAG Chunking Configuration
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))
TOKEN_CHUNK_SIZE = int(os.getenv("TOKEN_CHUNK_SIZE", "250"))
TOKEN_CHUNK_OVERLAP = int(os.getenv("TOKEN_CHUNK_OVERLAP", "40"))
CHUNK_METHOD = os.getenv("CHUNK_METHOD", "token")  # "token" or "character"

# Retrieval & Hybrid Search Configuration
RETRIEVER_K = int(os.getenv("RETRIEVER_K", "4"))
SIMILARITY_SCORE_THRESHOLD = float(os.getenv("SIMILARITY_SCORE_THRESHOLD", "0.35"))
HYBRID_SEARCH_ENABLED = os.getenv("HYBRID_SEARCH_ENABLED", "true").lower() in ("true", "1", "yes")
RRF_K = int(os.getenv("RRF_K", "60"))
HYBRID_ALPHA = float(os.getenv("HYBRID_ALPHA", "0.5"))

# Reranker Configuration
RERANKING_ENABLED = os.getenv("RERANKING_ENABLED", "true").lower() in ("true", "1", "yes")
RERANKER_MODEL_NAME = os.getenv("RERANKER_MODEL_NAME", "cross-encoder/ms-marco-MiniLM-L-6-v2")
RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", "4"))

# Context Window & Defense Configuration
MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "3500"))
PROMPT_INJECTION_DEFENSE = True

# API & Security Configuration
API_V1_PREFIX = "/api/v1"
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "ragbot-insecure-dev-secret-change-in-production-2026")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_RPM", "60"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173").split(",")

