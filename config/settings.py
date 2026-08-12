import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"
VECTOR_STORE_DIR = BASE_DIR / "vector_store"
ASSETS_DIR = BASE_DIR / "assets"
CHATS_DIR = BASE_DIR / "chats"
UPLOADS_DIR = BASE_DIR / "uploads"

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

# Model Configurations
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Available LLM Models
AVAILABLE_MODELS = {
    "⚡ Gemini 2.5 Flash (Fast)": "gemini-2.5-flash",
    "🧠 Gemini 2.5 Pro (Smart)": "gemini-2.5-pro",
    "🌀 Gemini 1.5 Flash (Legacy)": "gemini-1.5-flash",
}
DEFAULT_MODEL = "gemini-2.5-flash"
GEMINI_MODEL_NAME = DEFAULT_MODEL

DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_OUTPUT_TOKENS = 8192

# RAG Pipeline Configuration
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
RETRIEVER_K = 4
SIMILARITY_SCORE_THRESHOLD = 0.4
