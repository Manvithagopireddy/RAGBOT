import { Session, Message, DocumentItem, User, HealthStatus, DiagnosticsResult } from '../types';

const API_BASE = '/api/v1';

export function getAuthToken(): string | null {
  return localStorage.getItem('ragbot_token');
}

export function setAuthToken(token: string | null) {
  if (token) {
    localStorage.setItem('ragbot_token', token);
  } else {
    localStorage.removeItem('ragbot_token');
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = getAuthToken();
  const headers = new Headers(options.headers || {});
  
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = response.statusText;
    try {
      const errJson = await response.json();
      errorDetail = errJson.error || errJson.detail || errorDetail;
    } catch {
      // fallback to statusText
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export const api = {
  // Health
  getHealth: () => request<HealthStatus>('/health'),

  // Auth
  register: (data: { username: string; email: string; password: string }) =>
    request<User>('/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  login: (data: { username_or_email: string; password: string }) =>
    request<{ access_token: string; token_type: string; user_id: string; username: string; role: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getMe: () => request<User>('/auth/me'),

  // Sessions
  listSessions: () => request<Session[]>('/sessions'),
  createSession: (data: { title?: string; model?: string; temperature?: number; retriever_k?: number; persona?: string; web_search?: boolean }) =>
    request<Session>('/sessions', { method: 'POST', body: JSON.stringify(data) }),
  getSession: (sessionId: string) => request<Session & { messages: Message[] }>(`/sessions/${sessionId}`),
  updateSession: (sessionId: string, data: Partial<Session>) =>
    request<Session>(`/sessions/${sessionId}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteSession: (sessionId: string) => request<{ message: string }>(`/sessions/${sessionId}`, { method: 'DELETE' }),

  // Documents
  listDocuments: () => request<DocumentItem[]>('/documents'),
  uploadDocument: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return request<{ message: string; document: DocumentItem }>('/documents/upload', {
      method: 'POST',
      body: formData,
    });
  },
  deleteDocument: (documentId: string) => request<{ message: string }>(`/documents/${documentId}`, { method: 'DELETE' }),
  reindexDocument: (documentId: string) => request<DocumentItem>(`/documents/${documentId}/reindex`, { method: 'POST' }),

  // Diagnostics
  runDiagnostics: (data: { query: string; k?: number; threshold?: number; hybrid?: boolean; rerank?: boolean }) =>
    request<DiagnosticsResult>('/diagnostics/retrieve', { method: 'POST', body: JSON.stringify(data) }),

  // Chat Non-streaming
  sendMessage: (data: { message: string; session_id?: string; model?: string; temperature?: number; retriever_k?: number; persona?: string; web_search?: boolean; hybrid?: boolean; rerank?: boolean }) =>
    request<{ session_id: string; user_message_id: string; assistant_message_id: string; content: string; citations: any[]; confidence_score: number; confidence_desc: string; model: string }>('/chat', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Chat Streaming (Server-Sent Events)
  streamMessage: async (
    payload: {
      message: string;
      session_id?: string;
      model?: string;
      temperature?: number;
      retriever_k?: number;
      persona?: string;
      web_search?: boolean;
      hybrid?: boolean;
      rerank?: boolean;
    },
    callbacks: {
      onMetadata?: (data: { session_id: string; user_message_id: string }) => void;
      onCitations?: (data: { citations: any[] }) => void;
      onToken?: (token: string) => void;
      onDone?: (data: { session_id: string; assistant_message_id: string; confidence_score: number; confidence_desc: string }) => void;
      onError?: (err: Error) => void;
    }
  ) => {
    const token = getAuthToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    try {
      const response = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`Streaming failed with status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No readable response body stream');

      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      let completed = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split('\n\n');
        buffer = events.pop() || '';

        for (const rawEvent of events) {
          if (!rawEvent.trim()) continue;
          const lines = rawEvent.split('\n');
          let eventType = 'message';
          let dataStr = '';

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              eventType = line.replace('event: ', '').trim();
            } else if (line.startsWith('data: ')) {
              dataStr = line.replace('data: ', '').trim();
            }
          }

          if (dataStr) {
            try {
              const parsed = JSON.parse(dataStr);
              if (eventType === 'metadata' && callbacks.onMetadata) {
                callbacks.onMetadata(parsed);
              } else if (eventType === 'citations' && callbacks.onCitations) {
                callbacks.onCitations(parsed);
              } else if (eventType === 'token' && callbacks.onToken) {
                callbacks.onToken(parsed.token || '');
              } else if (eventType === 'done') {
                completed = true;
                callbacks.onDone?.(parsed);
              }
            } catch (pErr) {
              console.error('Failed to parse SSE JSON chunk:', dataStr, pErr);
            }
          }
        }
      }
      if (!completed) throw new Error('The response stream ended before completion. Please retry.');
    } catch (err: any) {
      if (callbacks.onError) callbacks.onError(err);
    }
  },
};
