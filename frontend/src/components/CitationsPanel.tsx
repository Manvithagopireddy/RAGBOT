import React from 'react';
import { X, BookOpen, ExternalLink, ShieldCheck, CheckCircle2 } from 'lucide-react';
import { Citation } from '../types';

interface CitationsPanelProps {
  isOpen: boolean;
  onClose: () => void;
  citations: Citation[];
  confidenceScore?: number | null;
  confidenceDesc?: string | null;
}

export const CitationsPanel: React.FC<CitationsPanelProps> = ({
  isOpen,
  onClose,
  citations,
  confidenceScore,
  confidenceDesc,
}) => {
  if (!isOpen) return null;

  const score = confidenceScore ?? 0;
  const isHigh = score >= 75;
  const isMedium = score >= 50 && score < 75;

  return (
    <aside className="w-80 border-l border-slate-800 bg-slate-900/40 p-4 flex flex-col h-[calc(100vh-3.5rem)] shrink-0 overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-teal-400" />
          <h3 className="font-semibold text-xs text-slate-100 uppercase tracking-wider">
            Verification & Citations
          </h3>
        </div>
        <button
          onClick={onClose}
          className="p-1 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Confidence gauge card */}
      {confidenceScore !== null && confidenceScore !== undefined && (
        <div className="mt-4 p-3 rounded-xl bg-slate-950/80 border border-slate-800/80">
          <div className="flex items-center justify-between text-xs mb-1.5">
            <span className="text-slate-400 font-medium">Grounding Confidence:</span>
            <span
              className={`font-mono font-bold ${
                isHigh ? 'text-emerald-400' : isMedium ? 'text-amber-400' : 'text-rose-400'
              }`}
            >
              {score}%
            </span>
          </div>

          <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                isHigh ? 'bg-emerald-500' : isMedium ? 'bg-amber-500' : 'bg-rose-500'
              }`}
              style={{ width: `${Math.min(100, Math.max(5, score))}%` }}
            />
          </div>

          {confidenceDesc && (
            <p className="mt-2 text-[11px] text-slate-400 leading-tight">
              {confidenceDesc}
            </p>
          )}
        </div>
      )}

      {/* Citations List */}
      <div className="mt-4 flex-1">
        <div className="flex items-center justify-between text-[11px] font-medium text-slate-400 uppercase tracking-wider mb-2">
          <span>Source References</span>
          <span className="font-mono text-teal-400">{citations.length} sources</span>
        </div>

        {citations.length === 0 ? (
          <div className="text-center py-10 text-xs text-slate-500">
            No document citations for this turn (answered from general model knowledge or web grounding).
          </div>
        ) : (
          <div className="space-y-2.5">
            {citations.map((c, i) => (
              <div
                key={c.id || i}
                className="p-3 rounded-lg bg-slate-950 border border-slate-800/60 hover:border-teal-500/30 transition-colors"
              >
                <div className="flex items-center justify-between text-xs mb-1">
                  <div className="font-semibold text-teal-300 truncate max-w-[170px]" title={c.source}>
                    [{c.id || i + 1}] {c.source}
                  </div>
                  {c.page !== null && c.page !== undefined && (
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                      Page {c.page}
                    </span>
                  )}
                </div>

                <p className="text-[11px] text-slate-400 italic line-clamp-4 leading-relaxed font-serif bg-slate-900/50 p-2 rounded border border-slate-800/40">
                  "{c.snippet}"
                </p>

                {c.score !== undefined && c.score !== null && (
                  <div className="mt-2 flex items-center justify-between text-[10px] text-slate-500 font-mono">
                    <span>Relevance:</span>
                    <span className="text-slate-400">{Math.round(c.score * 100)}%</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
};
