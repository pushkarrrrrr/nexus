"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { Card } from "../../src/components/ui/Card";
import { MetricCard } from "../../src/components/ui/MetricCard";
import { StatusBadge } from "../../src/components/ui/StatusBadge";
import type { DocumentItem, SourceAttribution, RAGQueryResponse } from "@nexus/types";
import {
  BookOpen,
  Search,
  FileText,
  Database,
  Layers,
  Sparkles,
  UploadCloud,
  Trash2,
  ExternalLink,
  CheckCircle2,
  AlertCircle,
  Clock,
  Quote,
  Network,
} from "lucide-react";

export default function KnowledgePage() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SourceAttribution[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);

  // RAG query state
  const [ragQuery, setRagQuery] = useState("");
  const [ragResponse, setRagResponse] = useState<RAGQueryResponse | null>(null);
  const [isRagRunning, setIsRagRunning] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fetch documents on mount
  useEffect(() => {
    fetchDocuments();
  }, []);

  async function fetchDocuments() {
    try {
      const token = localStorage.getItem("nexus_token");
      const res = await fetch("http://127.0.0.1:8000/api/v1/knowledge/documents", {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const data = await res.json();
        setDocuments(data || []);
      }
    } catch {
      // Fallback empty if offline
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadMessage(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const token = localStorage.getItem("nexus_token");
      const res = await fetch("http://127.0.0.1:8000/api/v1/knowledge/upload", {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });

      if (res.status === 202) {
        const data = await res.json();
        setUploadMessage(`Accepted "${file.name}" for background indexing.`);
        await fetchDocuments();
        // Poll once after 2 seconds to check if indexing completed
        setTimeout(fetchDocuments, 2000);
      } else {
        const err = await res.json();
        setUploadMessage(`Upload failed: ${err.detail || "Unknown error"}`);
      }
    } catch (err: any) {
      setUploadMessage(`Upload error: ${err.message}`);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleDeleteDocument = async (docId: string) => {
    try {
      const token = localStorage.getItem("nexus_token");
      await fetch(`http://127.0.0.1:8000/api/v1/knowledge/documents/${docId}`, {
        method: "DELETE",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
    } catch {
      // Optimistic delete
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
    }
  };

  const handleSemanticSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    setIsSearching(true);
    try {
      const token = localStorage.getItem("nexus_token");
      const res = await fetch("http://127.0.0.1:8000/api/v1/knowledge/search", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          query: searchQuery,
          limit: 5,
          min_similarity: 0.2,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setSearchResults(data.results || []);
      }
    } catch {
      // Search failed or offline
    } finally {
      setIsSearching(false);
    }
  };

  const handleRAGQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ragQuery.trim()) return;

    setIsRagRunning(true);
    setRagResponse(null);
    try {
      const token = localStorage.getItem("nexus_token");
      const res = await fetch("http://127.0.0.1:8000/api/v1/knowledge/rag", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          query: ragQuery,
          include_memory: true,
          max_context_chunks: 5,
          min_similarity: 0.2,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setRagResponse(data);
      }
    } catch {
      // RAG failed or offline
    } finally {
      setIsRagRunning(false);
    }
  };

  const totalChunks = documents.reduce((acc, d) => acc + (d.chunk_count || 0), 0);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/10 pb-4">
        <div>
          <h2 className="text-xl font-bold font-mono text-white flex items-center gap-2">
            <BookOpen size={20} className="text-cyan-400" />
            Personal Knowledge Base (RAG)
          </h2>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Asynchronous multi-format ingestion (PDF, Markdown, TXT, CSV, JSON), dual vector indexing &amp; grounded RAG
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2.5">
          <Link
            href="/knowledge/graph"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-600/20 hover:bg-purple-600/30 border border-purple-500/30 text-purple-300 font-medium font-mono text-xs transition-colors"
          >
            <Network size={14} />
            <span>Knowledge Graph</span>
          </Link>
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            accept=".pdf,.txt,.md,.markdown,.csv,.json"
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold font-mono text-xs transition-colors shadow-lg shadow-cyan-500/20 disabled:opacity-50"
          >
            <UploadCloud size={14} />
            {isUploading ? "Uploading..." : "Upload Document"}
          </button>
        </div>
      </div>

      {uploadMessage && (
        <div className="p-3 rounded-lg bg-slate-900 border border-cyan-500/30 text-xs font-mono text-cyan-300 flex items-center justify-between">
          <span>{uploadMessage}</span>
          <button onClick={() => setUploadMessage(null)} className="text-slate-400 hover:text-white">
            Dismiss
          </button>
        </div>
      )}

      {/* Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Vector Engine"
          value="pgvector + Fallback"
          subvalue="Dynamic Dialect-Aware Column"
          icon={<Database size={16} />}
        />
        <MetricCard
          label="Indexed Documents"
          value={`${documents.length} Docs`}
          subvalue="PDF, TXT, MD, CSV, JSON"
          icon={<FileText size={16} />}
        />
        <MetricCard
          label="Vector Chunks"
          value={`${totalChunks} Chunks`}
          subvalue="Overlap &amp; Page boundary"
          icon={<Layers size={16} />}
        />
        <MetricCard
          label="RAG Citations"
          value="100% Attributed"
          subvalue="Page &amp; Character Offsets"
          icon={<Sparkles size={16} />}
        />
      </div>

      {/* Main Grid: Left Column Documents / Search, Right Column RAG Console */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Document List & Semantic Search (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          {/* Document Ingestion Catalog */}
          <Card
            title={
              <div className="flex items-center gap-2">
                <FileText size={16} className="text-cyan-400" />
                <span>Ingested Documents</span>
              </div>
            }
            subtitle={`${documents.length} registered files in workspace`}
          >
            <div className="divide-y divide-white/5">
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className="py-3 flex items-center justify-between gap-4 font-mono text-xs"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-white truncate">{doc.filename}</span>
                      <span className="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] text-cyan-400 uppercase">
                        {doc.file_type}
                      </span>
                      {doc.status === "completed" && (
                        <span className="flex items-center gap-1 text-[10px] text-emerald-400">
                          <CheckCircle2 size={12} /> Indexed ({doc.chunk_count} chunks)
                        </span>
                      )}
                      {doc.status === "processing" && (
                        <span className="flex items-center gap-1 text-[10px] text-amber-400">
                          <Clock size={12} /> Processing...
                        </span>
                      )}
                      {doc.status === "failed" && (
                        <span className="flex items-center gap-1 text-[10px] text-rose-400">
                          <AlertCircle size={12} /> Failed
                        </span>
                      )}
                    </div>
                    <div className="text-[10px] text-slate-500 mt-0.5">
                      {(doc.file_size_bytes / 1024).toFixed(1)} KB • ID: {doc.id}
                    </div>
                  </div>

                  <button
                    onClick={() => handleDeleteDocument(doc.id)}
                    className="p-1 rounded hover:bg-rose-500/20 text-slate-500 hover:text-rose-400 transition-colors"
                    title="Delete document and chunks"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}

              {documents.length === 0 && (
                <div className="py-8 text-center text-slate-500 font-mono text-xs">
                  No documents uploaded yet. Upload a PDF, Markdown, or text file to begin.
                </div>
              )}
            </div>
          </Card>

          {/* Semantic Vector Search Interactive Tester */}
          <Card
            title={
              <div className="flex items-center gap-2">
                <Search size={16} className="text-cyan-400" />
                <span>Semantic Retrieval Inspector</span>
              </div>
            }
            subtitle="Search vector index with cosine similarity and source attribution"
          >
            <form onSubmit={handleSemanticSearch} className="flex items-center gap-2 mb-4">
              <input
                type="text"
                placeholder="Enter query to retrieve matching chunks..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="flex-1 bg-slate-900 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white font-mono placeholder:text-slate-500 focus:outline-none focus:border-cyan-500"
              />
              <button
                type="submit"
                disabled={isSearching}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-cyan-400 font-mono text-xs font-bold transition-colors disabled:opacity-50"
              >
                {isSearching ? "Searching..." : "Retrieve"}
              </button>
            </form>

            {/* Results */}
            <div className="space-y-3 font-mono text-xs">
              {searchResults.map((res, i) => (
                <div
                  key={i}
                  className="p-3 rounded-lg bg-slate-900/60 border border-white/10 space-y-1.5"
                >
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="font-bold text-cyan-300 flex items-center gap-1.5">
                      <FileText size={12} />
                      {res.source_title}
                      {res.page_number && ` (Page ${res.page_number})`}
                    </span>
                    <span className="text-emerald-400 font-bold">
                      Sim: {(res.similarity_score * 100).toFixed(1)}%
                    </span>
                  </div>
                  <p className="text-slate-300 text-[11px] leading-relaxed italic bg-black/20 p-2 rounded border border-white/5">
                    &ldquo;{res.snippet}&rdquo;
                  </p>
                  <div className="text-[10px] text-slate-500 flex items-center gap-3">
                    <span>Chunk: #{res.chunk_index}</span>
                    {res.char_start !== undefined && (
                      <span>Offsets: L{res.char_start} - L{res.char_end}</span>
                    )}
                  </div>
                </div>
              ))}

              {searchResults.length === 0 && searchQuery && !isSearching && (
                <div className="text-center py-4 text-slate-500 text-xs">
                  No matching chunks found above similarity threshold.
                </div>
              )}
            </div>
          </Card>
        </div>

        {/* Right: End-to-End RAG Console (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          <Card
            title={
              <div className="flex items-center gap-2">
                <Sparkles size={16} className="text-cyan-400" />
                <span>Grounded RAG Reasoning Console</span>
              </div>
            }
            subtitle="Synthesize answers strictly verified by documents &amp; user memories"
          >
            <form onSubmit={handleRAGQuery} className="space-y-3 mb-4">
              <textarea
                rows={3}
                placeholder="Ask a question about your knowledge base or memories..."
                value={ragQuery}
                onChange={(e) => setRagQuery(e.target.value)}
                className="w-full bg-slate-900 border border-white/10 rounded-lg p-2.5 text-xs text-white font-mono placeholder:text-slate-500 focus:outline-none focus:border-cyan-500"
              />
              <button
                type="submit"
                disabled={isRagRunning || !ragQuery.trim()}
                className="w-full py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold font-mono text-xs transition-colors shadow-lg shadow-cyan-500/20 disabled:opacity-50"
              >
                {isRagRunning ? "Synthesizing Grounded Answer..." : "Ask RAG Engine"}
              </button>
            </form>

            {/* Answer Display */}
            {ragResponse && (
              <div className="space-y-4 font-mono text-xs border-t border-white/10 pt-4">
                <div>
                  <div className="text-[11px] font-bold text-cyan-400 mb-1 flex items-center gap-1.5">
                    <Quote size={13} />
                    Synthesized Answer:
                  </div>
                  <div className="p-3 rounded-lg bg-slate-900 border border-white/10 text-slate-200 text-xs leading-relaxed whitespace-pre-wrap">
                    {ragResponse.answer}
                  </div>
                </div>

                {/* Supporting Sources */}
                {ragResponse.supporting_sources.length > 0 && (
                  <div>
                    <div className="text-[11px] font-bold text-slate-400 mb-1.5">
                      Supporting Sources ({ragResponse.supporting_sources.length}):
                    </div>
                    <div className="space-y-1.5">
                      {ragResponse.supporting_sources.map((src, i) => (
                        <div
                          key={i}
                          className="p-2 rounded bg-slate-900/40 border border-white/5 text-[10px] text-slate-300 flex items-center justify-between"
                        >
                          <span className="truncate font-bold text-cyan-300">
                            [{i + 1}] {src.source_title}
                            {src.page_number ? ` (p.${src.page_number})` : ""}
                          </span>
                          <span className="text-emerald-400 shrink-0 ml-2">
                            {(src.similarity_score * 100).toFixed(0)}% match
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Memory Citations */}
                {ragResponse.memory_citations.length > 0 && (
                  <div>
                    <div className="text-[11px] font-bold text-slate-400 mb-1.5">
                      Memory Citations ({ragResponse.memory_citations.length}):
                    </div>
                    <div className="space-y-1">
                      {ragResponse.memory_citations.map((mem, i) => (
                        <div
                          key={i}
                          className="text-[10px] text-slate-400 bg-slate-900/30 p-1.5 rounded"
                        >
                          • [{String(mem.class || "")}] <span className="text-slate-200">{String(mem.title || "")}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
