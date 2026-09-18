"use client";

import React, { useState } from "react";
import { Card } from "../../src/components/ui/Card";
import { MetricCard } from "../../src/components/ui/MetricCard";
import { StatusBadge } from "../../src/components/ui/StatusBadge";
import { BookOpen, Search, FileText, Database, Layers, Sparkles } from "lucide-react";

interface ChunkItem {
  id: string;
  source_file: string;
  lines: string;
  similarity_score: number;
  snippet: string;
}

const mockChunks: ChunkItem[] = [
  {
    id: "chunk_01_arch",
    source_file: "docs/ARCHITECTURE.md",
    lines: "L15-L42",
    similarity_score: 0.94,
    snippet: "The Policy Engine acts as the mandatory governance air-gap. No tool can execute without explicit risk classification and session grants.",
  },
  {
    id: "chunk_02_sec",
    source_file: "docs/SECURITY_MODEL.md",
    lines: "L50-L75",
    similarity_score: 0.89,
    snippet: "Before invoking any mutating tool (filesystem.write, filesystem.modify), a pre-execution snapshot is saved with SHA-256 integrity checks.",
  },
  {
    id: "chunk_03_db",
    source_file: "docs/DATABASE_ENTITIES.md",
    lines: "L80-L102",
    similarity_score: 0.82,
    snippet: "Table 'audit_logs' stores append-only security events with duration_ms, inputs, outputs, policy_verdict, and snapshot_id.",
  },
];

export default function KnowledgePage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [chunks] = useState<ChunkItem[]>(mockChunks);

  const filteredChunks = chunks.filter(
    (c) =>
      c.source_file.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.snippet.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 pb-4">
        <div>
          <h2 className="text-xl font-bold font-mono text-white">Personal Knowledge Base (RAG)</h2>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Local vector embeddings &amp; hybrid semantic search over personal workspace files
          </p>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Vector Database"
          value="pgvector"
          subvalue="Embedding: all-MiniLM-L6-v2"
          icon={<Database size={16} />}
        />
        <MetricCard
          label="Indexed Files"
          value="15 Docs"
          subvalue="Architecture, specs, code"
          icon={<FileText size={16} />}
        />
        <MetricCard
          label="Indexed Chunks"
          value="142 Chunks"
          subvalue="Avg chunk size: 450 tokens"
          icon={<Layers size={16} />}
        />
        <MetricCard
          label="Retrieval Precision"
          value="89.2%"
          subvalue="BM25 + Cosine distance"
          icon={<Sparkles size={16} />}
        />
      </div>

      {/* Search Sandbox */}
      <div className="glass-panel p-4 rounded-xl border border-white/10">
        <div className="flex items-center gap-3">
          <Search size={16} className="text-cyan-400" />
          <input
            type="text"
            placeholder="Search knowledge chunks by semantic query or file path..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="flex-1 bg-transparent border-none outline-none text-xs font-mono text-white placeholder-slate-500"
          />
        </div>
      </div>

      {/* Chunks List */}
      <div className="space-y-4">
        {filteredChunks.map((chunk) => (
          <Card
            key={chunk.id}
            title={
              <div className="flex items-center gap-2">
                <FileText size={14} className="text-cyan-400" />
                <span className="font-mono text-xs">{chunk.source_file}</span>
                <span className="text-[10px] text-slate-500 font-mono">
                  ({chunk.lines})
                </span>
              </div>
            }
            badge={
              <StatusBadge
                label={`Sim: ${(chunk.similarity_score * 100).toFixed(1)}%`}
                status="ready"
              />
            }
            subtitle={`Chunk ID: ${chunk.id}`}
          >
            <p className="text-xs text-slate-300 font-mono leading-relaxed bg-black/40 p-3 rounded-lg border border-white/5">
              {chunk.snippet}
            </p>
          </Card>
        ))}
      </div>
    </div>
  );
}
