import React, { useState, useEffect } from 'react';
import { Upload, FileText, Trash2, RefreshCw, AlertCircle, CheckCircle2, Search, FileUp } from 'lucide-react';
import { api } from '../api/client';
import { DocumentItem } from '../types';

export const DocumentsPage: React.FC = () => {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [reindexingId, setReindexingId] = useState<string | null>(null);

  const loadDocuments = async () => {
    try {
      setLoading(true);
      const data = await api.listDocuments();
      setDocuments(data);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to fetch documents.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, []);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setErrorMsg(null);
    setSuccessMsg(null);
    setUploading(true);

    try {
      const file = files[0];
      const res = await api.uploadDocument(file);
      setSuccessMsg(res.message);
      loadDocuments();
    } catch (err: any) {
      setErrorMsg(err.message || 'Upload failed.');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!window.confirm(`Are you sure you want to delete '${name}'?`)) return;

    try {
      await api.deleteDocument(id);
      setDocuments(documents.filter((d) => d.document_id !== id));
      setSuccessMsg(`Document '${name}' deleted.`);
    } catch (err: any) {
      setErrorMsg(err.message || 'Delete failed.');
    }
  };

  const handleReindex = async (id: string) => {
    try {
      setReindexingId(id);
      await api.reindexDocument(id);
      setSuccessMsg('Document successfully re-indexed.');
      loadDocuments();
    } catch (err: any) {
      setErrorMsg(err.message || 'Reindexing failed.');
    } finally {
      setReindexingId(null);
    }
  };

  const filtered = documents.filter((d) =>
    d.filename.toLowerCase().includes(search.toLowerCase())
  );

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  return (
    <div className="max-w-6xl mx-auto p-6 md:p-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <FileText className="w-5 h-5 text-teal-400" />
            Knowledge Base Documents
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Manage multi-format corporate files indexed for vector embeddings and keyword search.
          </p>
        </div>

        {/* Upload Button */}
        <div>
          <label className="cursor-pointer inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-teal-600 hover:bg-teal-500 text-white shadow-sm transition-all">
            <FileUp className="w-4 h-4" />
            <span>{uploading ? 'Processing & Indexing…' : 'Upload Document'}</span>
            <input
              type="file"
              accept=".pdf,.docx,.txt,.csv,.pptx"
              onChange={handleFileUpload}
              disabled={uploading}
              className="hidden"
            />
          </label>
        </div>
      </div>

      {/* Alert Messages */}
      {errorMsg && (
        <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {successMsg && (
        <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Search Bar */}
      <div className="relative">
        <Search className="w-4 h-4 absolute left-3 top-3 text-slate-500" />
        <input
          type="text"
          placeholder="Filter documents by filename..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full bg-slate-900 border border-slate-800 rounded-xl pl-9 pr-4 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-teal-500/50"
        />
      </div>

      {/* Table Container */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/40 overflow-hidden shadow-sm">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-900/80 border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
            <tr>
              <th className="py-3 px-4">Document</th>
              <th className="py-3 px-4">Type</th>
              <th className="py-3 px-4">Size</th>
              <th className="py-3 px-4">Chunks</th>
              <th className="py-3 px-4">Status</th>
              <th className="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 text-slate-300">
            {loading ? (
              <tr>
                <td colSpan={6} className="text-center py-12 text-slate-500">
                  Loading catalog…
                </td>
              </tr>
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={6} className="text-center py-12 text-slate-500">
                  No documents found. Upload PDF, DOCX, or TXT files to populate the knowledge base.
                </td>
              </tr>
            ) : (
              filtered.map((doc) => (
                <tr key={doc.document_id} className="hover:bg-slate-800/30 transition-colors">
                  <td className="py-3 px-4 font-medium text-slate-100 flex items-center gap-2">
                    <FileText className="w-4 h-4 text-teal-400 shrink-0" />
                    <span className="truncate max-w-xs">{doc.filename}</span>
                  </td>
                  <td className="py-3 px-4 font-mono uppercase text-[10px] text-slate-400">
                    {doc.file_type}
                  </td>
                  <td className="py-3 px-4 font-mono text-slate-400">
                    {formatBytes(doc.file_size)}
                  </td>
                  <td className="py-3 px-4 font-mono text-teal-400">
                    {doc.chunk_count}
                  </td>
                  <td className="py-3 px-4">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                      {doc.status}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => handleReindex(doc.document_id)}
                        disabled={reindexingId === doc.document_id}
                        title="Reindex document"
                        className="p-1.5 text-slate-400 hover:text-teal-400 hover:bg-slate-800 rounded transition-colors disabled:opacity-50"
                      >
                        <RefreshCw className={`w-3.5 h-3.5 ${reindexingId === doc.document_id ? 'animate-spin' : ''}`} />
                      </button>
                      <button
                        onClick={() => handleDelete(doc.document_id, doc.filename)}
                        title="Delete document"
                        className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-slate-800 rounded transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
