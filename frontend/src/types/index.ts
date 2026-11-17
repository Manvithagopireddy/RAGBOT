export interface Citation {
  id: number;
  source: string;
  page?: number | null;
  snippet: string;
  score?: number | null;
  url?: string | null;
}

export interface Message {
  message_id: string;
  session_id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  confidence_score?: number | null;
  confidence_desc?: string | null;
  feedback?: string | null;
  pinned?: number;
  created_at: string;
}

export interface Session {
  session_id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  model: string;
  temperature: number;
  retriever_k: number;
  rag_enabled: number;
  persona?: string;
  web_search: number;
  is_pinned: number;
  is_favorited: number;
  is_archived: number;
  messages?: Message[];
}

export interface DocumentItem {
  document_id: string;
  user_id: string;
  filename: string;
  file_path: string;
  file_type: string;
  file_size: number;
  chunk_count: number;
  checksum?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface User {
  user_id: string;
  username: string;
  email: string;
  role: string;
  created_at: string;
}

export interface HealthStatus {
  status: string;
  version: string;
  database_connected: boolean;
  faiss_ready: boolean;
  bm25_ready: boolean;
  total_vectors: number;
  total_documents: number;
  default_model: string;
}

export interface DiagnosticsResult {
  query: string;
  results_count: number;
  latency_ms: number;
  diagnostics: {
    k_requested: number;
    hybrid_enabled: boolean;
    rerank_enabled: boolean;
    top_similarity: number;
    sources: string[];
  };
  results: Array<{
    source: string;
    page?: number;
    similarity: number;
    distance?: number;
    text_snippet: string;
  }>;
}
