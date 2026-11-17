import React, { useState } from 'react';
import { Activity, Search, Sparkles, Layers, Clock, CheckCircle2, AlertCircle } from 'lucide-react';
import { api } from '../api/client';
import { DiagnosticsResult } from '../types';

export const DiagnosticsPage: React.FC = () => {
  const [query, setQuery] = useState('');
  const [k, setK] = useState(4);
  const [hybrid, setHybrid] = useState(true);
  const [rerank, setRerank] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DiagnosticsResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleTestRetrieval = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setErrorMsg(null);
    setLoading(true);

    try {
      const data = await api.runDiagnostics({
        query: query.trim(),
        k,
        hybrid,
        rerank,
      });
      setResult(data);
    } catch (err: any) {
      setErrorMsg(err.message || 'Diagnostics execution failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto p-6 md:p-8 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
          <Activity className="w-5 h-5 text-teal-400" />
          RAG Retrieval Diagnostics & Tuning
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Inspect dense vector embeddings, sparse BM25 keyword rankings, and neural Cross-Encoder score distributions in real-time.
        </p>
      </div>

      {/* Query Form */}
      <form onSubmit={handleTestRetrieval} className="p-4 rounded-2xl border border-slate-800 bg-slate-900/60 backdrop-blur-md space-y-4">
        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1">
            Test Query
          </label>
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-3 text-slate-500" />
            <input
              type="text"
              placeholder="e.g. 'What is the refund policy?' or 'vector similarity calculation'..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-4 py-2.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-teal-500/60"
            />
          </div>
        </div>

        {/* Controls */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs pt-1">
          <div>
            <div className="flex justify-between text-slate-400 font-medium mb-1">
              <span>Top-K Results:</span>
              <span className="font-mono text-teal-400">{k}</span>
            </div>
            <input
              type="range"
              min="1"
              max="10"
              value={k}
              onChange={(e) => setK(parseInt(e.target.value))}
              className="w-full accent-teal-500"
            />
          </div>

          <div className="flex items-center gap-2 pt-4">
            <label className="flex items-center gap-2 cursor-pointer text-slate-300">
              <input
                type="checkbox"
                checked={hybrid}
                onChange={(e) => setHybrid(e.target.checked)}
                className="rounded border-slate-700 text-teal-500 focus:ring-0"
              />
              <span>Reciprocal Rank Fusion (BM25 + FAISS)</span>
            </label>
          </div>

          <div className="flex items-center gap-2 pt-4">
            <label className="flex items-center gap-2 cursor-pointer text-slate-300">
              <input
                type="checkbox"
                checked={rerank}
                onChange={(e) => setRerank(e.target.checked)}
                className="rounded border-slate-700 text-teal-500 focus:ring-0"
              />
              <span>Neural Cross-Encoder</span>
            </label>
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={!query.trim() || loading}
            className="px-5 py-2 rounded-xl text-xs font-semibold bg-teal-600 hover:bg-teal-500 disabled:opacity-40 text-white shadow-sm transition-all"
          >
            {loading ? 'Evaluating Pipeline…' : 'Run Diagnostics'}
          </button>
        </div>
      </form>

      {/* Errors */}
      {errorMsg && (
        <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-4">
          {/* Diagnostic Metrics Overview */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800">
              <div className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">Latency</div>
              <div className="mt-1 text-lg font-mono font-bold text-teal-400 flex items-center gap-1">
                <Clock className="w-4 h-4" />
                {result.latency_ms} ms
              </div>
            </div>

            <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800">
              <div className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">Candidates Returned</div>
              <div className="mt-1 text-lg font-mono font-bold text-indigo-400 flex items-center gap-1">
                <Layers className="w-4 h-4" />
                {result.results_count} chunks
              </div>
            </div>

            <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800">
              <div className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">Top Similarity</div>
              <div className="mt-1 text-lg font-mono font-bold text-emerald-400 flex items-center gap-1">
                <Sparkles className="w-4 h-4" />
                {Math.round(result.diagnostics.top_similarity * 100)}%
              </div>
            </div>

            <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800">
              <div className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">Distinct Sources</div>
              <div className="mt-1 text-lg font-mono font-bold text-amber-400">
                {result.diagnostics.sources.length} docs
              </div>
            </div>
          </div>

          {/* Retrieved Chunks Table */}
          <div className="space-y-3">
            <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
              Retrieved & Reranked Context Chunks
            </h3>

            {result.results.map((r, i) => (
              <div key={i} className="p-4 rounded-xl bg-slate-900/40 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-teal-300">
                    #{i + 1} — {r.source} {r.page ? `(Page ${r.page})` : ''}
                  </span>
                  <div className="flex items-center gap-2 font-mono text-[10px]">
                    <span className="px-2 py-0.5 rounded bg-slate-800 text-teal-400">
                      Similarity: {Math.round(r.similarity * 100)}%
                    </span>
                    {r.distance !== undefined && r.distance !== null && (
                      <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400">
                        L2 Distance: {r.distance.toFixed(4)}
                      </span>
                    )}
                  </div>
                </div>

                <p className="text-xs text-slate-300 font-serif leading-relaxed bg-slate-950 p-3 rounded-lg border border-slate-800/80">
                  {r.text_snippet}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
