import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Send,
  Bot,
  User as UserIcon,
  Copy,
  Check,
  RotateCcw,
  Sparkles,
  Sliders,
  BookOpen,
  ArrowRight,
  Shield,
  Layers,
} from 'lucide-react';
import { api } from '../api/client';
import { Message, Session, Citation } from '../types';
import { Sidebar } from '../components/Sidebar';
import { CitationsPanel } from '../components/CitationsPanel';

export const ChatPage: React.FC = () => {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputPrompt, setInputPrompt] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Settings
  const [showSettings, setShowSettings] = useState(false);
  const [selectedModel, setSelectedModel] = useState('gemini-2.5-flash');
  const [temperature, setTemperature] = useState(0.7);
  const [retrieverK, setRetrieverK] = useState(4);
  const [hybridSearch, setHybridSearch] = useState(true);
  const [reranking, setReranking] = useState(true);

  // Citations drawer state
  const [showCitations, setShowCitations] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [activeCitations, setActiveCitations] = useState<Citation[]>([]);
  const [activeConfidenceScore, setActiveConfidenceScore] = useState<number | null>(null);
  const [activeConfidenceDesc, setActiveConfidenceDesc] = useState<string | null>(null);
  const [docCount, setDocCount] = useState(0);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isStreaming]);

  // Load initial sessions & documents count
  useEffect(() => {
    loadSessions();
    api.listDocuments()
      .then((docs) => setDocCount(docs.length))
      .catch((err) => console.error(err));
  }, []);

  const loadSessions = async () => {
    try {
      const data = await api.listSessions();
      setSessions(data);
      if (data.length > 0 && !activeSessionId) {
        selectSession(data[0].session_id);
      }
    } catch (err) {
      console.error('Error loading sessions:', err);
    }
  };

  const selectSession = async (id: string) => {
    setActiveSessionId(id);
    try {
      const details = await api.getSession(id);
      setMessages(details.messages || []);
      // Update citation view to last assistant message
      const lastAssistant = [...(details.messages || [])].reverse().find((m) => m.role === 'assistant');
      if (lastAssistant) {
        setActiveCitations(lastAssistant.citations || []);
        setActiveConfidenceScore(lastAssistant.confidence_score ?? null);
        setActiveConfidenceDesc(lastAssistant.confidence_desc ?? null);
      } else {
        setActiveCitations([]);
        setActiveConfidenceScore(null);
        setActiveConfidenceDesc(null);
      }
    } catch (err) {
      console.error('Error fetching session messages:', err);
    }
  };

  const handleNewSession = async () => {
    try {
      const newSess = await api.createSession({
        title: 'New Chat',
        model: selectedModel,
        temperature,
        retriever_k: retrieverK,
      });
      setSessions([newSess, ...sessions]);
      setActiveSessionId(newSess.session_id);
      setMessages([]);
      setActiveCitations([]);
      setActiveConfidenceScore(null);
      setActiveConfidenceDesc(null);
    } catch (err) {
      console.error('Error creating new session:', err);
    }
  };

  const handleDeleteSession = async (id: string) => {
    try {
      await api.deleteSession(id);
      const remaining = sessions.filter((s) => s.session_id !== id);
      setSessions(remaining);
      if (activeSessionId === id) {
        if (remaining.length > 0) {
          selectSession(remaining[0].session_id);
        } else {
          setActiveSessionId(null);
          setMessages([]);
        }
      }
    } catch (err) {
      console.error('Error deleting session:', err);
    }
  };

  const handleRenameSession = async (id: string, newTitle: string) => {
    try {
      const updated = await api.updateSession(id, { title: newTitle });
      setSessions(sessions.map((s) => (s.session_id === id ? { ...s, title: updated.title } : s)));
    } catch (err) {
      console.error('Error renaming session:', err);
    }
  };

  const handleCopyMessage = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleSendMessage = async (textToSend?: string) => {
    const query = (textToSend || inputPrompt).trim();
    if (!query || isStreaming) return;

    setInputPrompt('');
    setIsStreaming(true);

    const tempUserMsgId = `usr_${Date.now()}`;
    const userMessage: Message = {
      message_id: tempUserMsgId,
      session_id: activeSessionId || '',
      role: 'user',
      content: query,
      created_at: new Date().toISOString(),
    };

    const tempAssistantMsgId = `ast_${Date.now()}`;
    const assistantMessage: Message = {
      message_id: tempAssistantMsgId,
      session_id: activeSessionId || '',
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);

    let accumulatedContent = '';

    await api.streamMessage(
      {
        message: query,
        session_id: activeSessionId || undefined,
        model: selectedModel,
        temperature,
        retriever_k: retrieverK,
        hybrid: hybridSearch,
        rerank: reranking,
      },
      {
        onMetadata: (data) => {
          if (!activeSessionId && data.session_id) {
            setActiveSessionId(data.session_id);
            loadSessions();
          }
        },
        onCitations: (data) => {
          setActiveCitations(data.citations || []);
          setMessages((prev) =>
            prev.map((m) =>
              m.message_id === tempAssistantMsgId ? { ...m, citations: data.citations } : m
            )
          );
        },
        onToken: (token) => {
          accumulatedContent += token;
          setMessages((prev) =>
            prev.map((m) =>
              m.message_id === tempAssistantMsgId ? { ...m, content: accumulatedContent } : m
            )
          );
        },
        onDone: (data) => {
          setActiveConfidenceScore(data.confidence_score);
          setActiveConfidenceDesc(data.confidence_desc);
          setMessages((prev) =>
            prev.map((m) =>
              m.message_id === tempAssistantMsgId
                ? {
                    ...m,
                    confidence_score: data.confidence_score,
                    confidence_desc: data.confidence_desc,
                  }
                : m
            )
          );
          setIsStreaming(false);
          loadSessions();
        },
        onError: (err) => {
          console.error('Streaming error:', err);
          setMessages((prev) =>
            prev.map((m) =>
              m.message_id === tempAssistantMsgId
                ? { ...m, content: `${m.content}\n\n⚠️ *Generation encountered an error: ${err.message}*` }
                : m
            )
          );
          setIsStreaming(false);
        },
      }
    );
  };

  const samplePrompts = [
    'What is RAG and how does hybrid retrieval work?',
    'Explain Reciprocal Rank Fusion (RRF) with BM25 and FAISS.',
    'Summarize the knowledge base documents.',
    'How do Cross-Encoder rerankers improve retrieval precision?',
  ];

  return (
    <div className="relative flex h-[calc(100dvh-3.5rem)] overflow-hidden">
      {/* Session History Sidebar */}
      <div className={`${showHistory ? 'absolute inset-y-0 left-0 z-30 bg-slate-950' : 'hidden'} lg:relative lg:block`}>
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={(id) => { if (!isStreaming) { selectSession(id); setShowHistory(false); } }}
        onNewSession={() => { if (!isStreaming) { handleNewSession(); setShowHistory(false); } }}
        onDeleteSession={(id) => { if (!isStreaming) handleDeleteSession(id); }}
        onRenameSession={handleRenameSession}
        documentCount={docCount}
      />

      </div>
      {/* Main Chat Workspace */}
      <main className="min-w-0 flex-1 flex flex-col h-full bg-slate-950 relative overflow-hidden">
        {/* Top Chat Toolbar */}
        <div className="h-11 border-b border-slate-800/80 px-4 flex items-center justify-between text-xs bg-slate-900/30">
          <div className="flex min-w-0 items-center gap-2">
            <button className="lg:hidden p-1 text-teal-400" aria-expanded={showHistory} onClick={() => setShowHistory(!showHistory)}>Chats</button>
            <span className="truncate font-semibold text-slate-200">
              {sessions.find((s) => s.session_id === activeSessionId)?.title || 'New Conversation'}
            </span>
            <span className="hidden xl:inline-flex text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-teal-400 border border-slate-700/60">
              ⚡ {selectedModel}
            </span>
            {hybridSearch && (
              <span className="hidden xl:inline-flex text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-indigo-400 border border-slate-700/60 flex items-center gap-1">
                <Layers className="w-3 h-3" /> Hybrid (BM25+FAISS)
              </span>
            )}
            {reranking && (
              <span className="hidden xl:inline-flex text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-amber-400 border border-slate-700/60 flex items-center gap-1">
                <Sparkles className="w-3 h-3" /> Cross-Encoder
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowSettings(!showSettings)}
              className={`p-1.5 rounded-lg border text-xs flex items-center gap-1 transition-colors ${
                showSettings
                  ? 'bg-slate-800 border-teal-500/50 text-teal-300'
                  : 'border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-900'
              }`}
            >
              <Sliders className="w-3.5 h-3.5" />
              <span>Parameters</span>
            </button>

            <button
              onClick={() => setShowCitations(!showCitations)}
              className={`p-1.5 rounded-lg border text-xs flex items-center gap-1 transition-colors ${
                showCitations
                  ? 'bg-slate-800 border-teal-500/50 text-teal-300'
                  : 'border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-900'
              }`}
            >
              <BookOpen className="w-3.5 h-3.5" />
              <span>Sources ({activeCitations.length})</span>
            </button>
          </div>
        </div>

        {/* Collapsible Model Parameters Card */}
        {showSettings && (
          <div className="p-4 border-b border-slate-800 bg-slate-900/90 backdrop-blur-md grid grid-cols-1 md:grid-cols-4 gap-4 text-xs">
            <div>
              <label className="block text-slate-400 font-medium mb-1">Model Selection</label>
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-teal-500"
              >
                <option value="gemini-2.5-flash">Gemini 2.5 Flash (Fast)</option>
                <option value="gemini-2.5-pro">Gemini 2.5 Pro (Reasoning)</option>
                <option value="gemini-1.5-flash">Gemini 1.5 Flash</option>
              </select>
            </div>

            <div>
              <div className="flex justify-between text-slate-400 font-medium mb-1">
                <span>Temperature:</span>
                <span className="font-mono text-teal-400">{temperature}</span>
              </div>
              <input
                type="range"
                min="0.0"
                max="1.0"
                step="0.05"
                value={temperature}
                onChange={(e) => setTemperature(parseFloat(e.target.value))}
                className="w-full accent-teal-500"
              />
            </div>

            <div>
              <div className="flex justify-between text-slate-400 font-medium mb-1">
                <span>Retriever K:</span>
                <span className="font-mono text-teal-400">{retrieverK} chunks</span>
              </div>
              <input
                type="range"
                min="1"
                max="10"
                step="1"
                value={retrieverK}
                onChange={(e) => setRetrieverK(parseInt(e.target.value))}
                className="w-full accent-teal-500"
              />
            </div>

            <div className="flex items-center gap-4 pt-4">
              <label className="flex items-center gap-2 cursor-pointer text-slate-300">
                <input
                  type="checkbox"
                  checked={hybridSearch}
                  onChange={(e) => setHybridSearch(e.target.checked)}
                  className="rounded border-slate-700 text-teal-500 focus:ring-0"
                />
                <span>Hybrid BM25</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer text-slate-300">
                <input
                  type="checkbox"
                  checked={reranking}
                  onChange={(e) => setReranking(e.target.checked)}
                  className="rounded border-slate-700 text-teal-500 focus:ring-0"
                />
                <span>Reranker</span>
              </label>
            </div>
          </div>
        )}

        {/* Message Feed */}
        <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
          {messages.length === 0 ? (
            <div className="max-w-xl mx-auto py-12 text-center">
              <div className="w-14 h-14 rounded-2xl bg-teal-500/10 border border-teal-500/20 text-teal-400 flex items-center justify-center mx-auto mb-4">
                <Bot className="w-7 h-7" />
              </div>
              <h2 className="text-xl font-bold text-slate-100 mb-2">
                Enterprise AI Knowledge Assistant
              </h2>
              <p className="text-sm text-slate-400 mb-8 leading-relaxed">
                Ask questions grounded directly in your uploaded PDFs, Word documents, text files, and spreadsheets with retrieved source citations.
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-left">
                {samplePrompts.map((prompt, i) => (
                  <button
                    key={i}
                    onClick={() => handleSendMessage(prompt)}
                    className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-teal-500/50 hover:bg-slate-900 text-xs text-slate-300 transition-all flex items-center justify-between group"
                  >
                    <span className="line-clamp-2">{prompt}</span>
                    <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-teal-400 group-hover:translate-x-0.5 transition-all shrink-0 ml-2" />
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((msg, idx) => {
              const isAssistant = msg.role === 'assistant';
              const isCopied = copiedId === msg.message_id;

              return (
                <div
                  key={msg.message_id || idx}
                  className={`flex gap-3 max-w-3xl ${isAssistant ? 'mr-auto' : 'ml-auto flex-row-reverse'}`}
                >
                  {/* Avatar */}
                  <div
                    className={`w-8 h-8 rounded-lg shrink-0 flex items-center justify-center ${
                      isAssistant
                        ? 'bg-teal-500/10 border border-teal-500/20 text-teal-400'
                        : 'bg-indigo-500/10 border border-indigo-500/20 text-indigo-400'
                    }`}
                  >
                    {isAssistant ? <Bot className="w-4 h-4" /> : <UserIcon className="w-4 h-4" />}
                  </div>

                  {/* Bubble Container */}
                  <div
                    className={`rounded-2xl p-4 text-xs md:text-sm leading-relaxed max-w-[85%] border shadow-sm ${
                      isAssistant
                        ? 'bg-slate-900 border-slate-800 text-slate-200'
                        : 'bg-teal-600 border-teal-500 text-white'
                    }`}
                  >
                    <div className="prose prose-invert prose-sm max-w-none break-words">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {msg.content || (isStreaming && idx === messages.length - 1 ? 'Thinking & retrieving…' : '')}
                      </ReactMarkdown>
                    </div>

                    {/* Action Bar */}
                    <div
                      className={`flex items-center gap-2 mt-3 pt-2 border-t text-[11px] ${
                        isAssistant
                          ? 'border-slate-800/80 text-slate-400'
                          : 'border-teal-500/50 text-teal-100'
                      }`}
                    >
                      <button
                        onClick={() => handleCopyMessage(msg.message_id, msg.content)}
                        className="hover:text-slate-200 flex items-center gap-1 transition-colors"
                      >
                        {isCopied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                        <span>{isCopied ? 'Copied' : 'Copy'}</span>
                      </button>

                      {isAssistant && msg.citations && msg.citations.length > 0 && (
                        <button
                          onClick={() => {
                            setActiveCitations(msg.citations || []);
                            setActiveConfidenceScore(msg.confidence_score ?? null);
                            setActiveConfidenceDesc(msg.confidence_desc ?? null);
                            setShowCitations(true);
                          }}
                          className="hover:text-teal-400 flex items-center gap-1 transition-colors ml-2"
                        >
                          <BookOpen className="w-3 h-3 text-teal-400" />
                          <span>{msg.citations.length} Sources</span>
                        </button>
                      )}

                      {isAssistant && msg.confidence_score !== undefined && msg.confidence_score !== null && (
                        <span className="ml-auto font-mono text-[10px] text-slate-500">
                          {msg.confidence_score}% retrieval confidence
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <div className="p-4 border-t border-slate-800/80 bg-slate-900/60 backdrop-blur-md">
          <div className="max-w-3xl mx-auto relative flex items-center">
            <textarea
              rows={1}
              aria-label="Chat message"
              value={inputPrompt}
              onChange={(e) => setInputPrompt(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSendMessage();
                }
              }}
              placeholder="Ask anything about your documents (Shift+Enter for newline)..."
              disabled={isStreaming}
              className="w-full bg-slate-950 border border-slate-800 focus:border-teal-500/60 rounded-xl pl-4 pr-12 py-3 text-xs md:text-sm text-slate-100 placeholder-slate-500 focus:outline-none resize-none shadow-inner"
            />
            <button
              onClick={() => handleSendMessage()}
              aria-label="Send message"
              disabled={!inputPrompt.trim() || isStreaming}
              className="absolute right-2 p-2 rounded-lg bg-teal-600 hover:bg-teal-500 disabled:opacity-40 disabled:hover:bg-teal-600 text-white transition-all shadow-sm"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
          <div className="max-w-3xl mx-auto mt-2 text-center text-[10px] text-slate-500">
            Grounded responses derived through hybrid BM25 + FAISS search and Cross-Encoder neural reranking.
          </div>
        </div>
      </main>

      {/* Citations Panel */}
      <CitationsPanel
        isOpen={showCitations}
        onClose={() => setShowCitations(false)}
        citations={activeCitations}
        confidenceScore={activeConfidenceScore}
        confidenceDesc={activeConfidenceDesc}
      />
    </div>
  );
};
