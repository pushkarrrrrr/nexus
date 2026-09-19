'use client';

import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import Link from 'next/link';
import {
  Network,
  Search,
  Filter,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Plus,
  ArrowRight,
  Info,
  Layers,
  FileText,
  Cpu,
  User,
  CheckCircle2,
  FolderGit2,
  Sparkles,
  RefreshCw,
  X,
  Compass,
} from 'lucide-react';
import type {
  KnowledgeNodeItem,
  KnowledgeEdgeItem,
  GraphOverview,
  NodeType,
  RelationType,
  GraphShortestPath,
} from '@nexus/types';

interface SimulationNode extends KnowledgeNodeItem {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

const TYPE_CONFIG: Record<string, { color: string; border: string; bg: string; icon: React.ReactNode }> = {
  concept: {
    color: 'text-purple-400',
    border: 'border-purple-500/50',
    bg: 'bg-purple-950/80',
    icon: <Sparkles className="w-3.5 h-3.5 text-purple-400" />,
  },
  document: {
    color: 'text-blue-400',
    border: 'border-blue-500/50',
    bg: 'bg-blue-950/80',
    icon: <FileText className="w-3.5 h-3.5 text-blue-400" />,
  },
  technology: {
    color: 'text-emerald-400',
    border: 'border-emerald-500/50',
    bg: 'bg-emerald-950/80',
    icon: <Cpu className="w-3.5 h-3.5 text-emerald-400" />,
  },
  task: {
    color: 'text-amber-400',
    border: 'border-amber-500/50',
    bg: 'bg-amber-950/80',
    icon: <CheckCircle2 className="w-3.5 h-3.5 text-amber-400" />,
  },
  project: {
    color: 'text-rose-400',
    border: 'border-rose-500/50',
    bg: 'bg-rose-950/80',
    icon: <FolderGit2 className="w-3.5 h-3.5 text-rose-400" />,
  },
  person: {
    color: 'text-cyan-400',
    border: 'border-cyan-500/50',
    bg: 'bg-cyan-950/80',
    icon: <User className="w-3.5 h-3.5 text-cyan-400" />,
  },
  other: {
    color: 'text-slate-400',
    border: 'border-slate-500/50',
    bg: 'bg-slate-900/80',
    icon: <Network className="w-3.5 h-3.5 text-slate-400" />,
  },
};

export default function KnowledgeGraphPage() {
  const [nodes, setNodes] = useState<SimulationNode[]>([]);
  const [edges, setEdges] = useState<KnowledgeEdgeItem[]>([]);
  const [overview, setOverview] = useState<GraphOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDraggingCanvas, setIsDraggingCanvas] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [draggedNodeId, setDraggedNodeId] = useState<string | null>(null);
  const [expandingNeighborhood, setExpandingNeighborhood] = useState(false);
  const [shortestPathData, setShortestPathData] = useState<GraphShortestPath | null>(null);

  // Modals
  const [showAddNodeModal, setShowAddNodeModal] = useState(false);
  const [showAddEdgeModal, setShowAddEdgeModal] = useState(false);
  const [showPathModal, setShowPathModal] = useState(false);

  // Forms
  const [newNodeLabel, setNewNodeLabel] = useState('');
  const [newNodeType, setNewNodeType] = useState<NodeType>('concept');
  const [newEdgeSource, setNewEdgeSource] = useState('');
  const [newEdgeTarget, setNewEdgeTarget] = useState('');
  const [newEdgeRelation, setNewEdgeRelation] = useState<RelationType>('related_to');
  const [pathSourceId, setPathSourceId] = useState('');
  const [pathTargetId, setPathTargetId] = useState('');

  const svgRef = useRef<SVGSVGElement>(null);
  const animFrameRef = useRef<number | null>(null);
  const alphaRef = useRef<number>(1.0);

  const token = typeof window !== 'undefined' ? localStorage.getItem('nexus_token') : null;

  const authHeaders = useMemo(() => {
    return {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
  }, [token]);

  // 1. Fetch initial graph data
  const fetchGraph = useCallback(async () => {
    setLoading(true);
    try {
      const [overviewRes, nodesRes, edgesRes] = await Promise.all([
        fetch('http://127.0.0.1:8000/api/v1/graph/overview', { headers: authHeaders }),
        fetch('http://127.0.0.1:8000/api/v1/graph/nodes?limit=250', { headers: authHeaders }),
        fetch('http://127.0.0.1:8000/api/v1/graph/edges?limit=400', { headers: authHeaders }),
      ]);

      if (overviewRes.ok) setOverview(await overviewRes.json());

      if (nodesRes.ok && edgesRes.ok) {
        const rawNodes: KnowledgeNodeItem[] = await nodesRes.json();
        const rawEdges: KnowledgeEdgeItem[] = await edgesRes.json();

        // Assign initial radial or randomized coordinates
        const count = rawNodes.length;
        const radius = Math.min(350, Math.max(150, count * 15));
        const simNodes: SimulationNode[] = rawNodes.map((n, i) => {
          const angle = (i / Math.max(1, count)) * 2 * Math.PI;
          return {
            ...n,
            x: 500 + radius * Math.cos(angle) + (Math.random() - 0.5) * 50,
            y: 350 + radius * Math.sin(angle) + (Math.random() - 0.5) * 50,
            vx: 0,
            vy: 0,
          };
        });

        setNodes(simNodes);
        setEdges(rawEdges);
        alphaRef.current = 1.0;
      }
    } catch (err) {
      console.error('Failed to load knowledge graph:', err);
    } finally {
      setLoading(false);
    }
  }, [authHeaders]);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  // 2. Performant Force Simulation Loop with Clean Damping and Unbind
  useEffect(() => {
    if (nodes.length === 0) return;

    const tick = () => {
      if (alphaRef.current < 0.005) {
        if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
        animFrameRef.current = null;
        return;
      }

      setNodes((prevNodes) => {
        const nodeMap = new Map(prevNodes.map((n) => [n.id, n]));
        const updated = prevNodes.map((n) => ({ ...n }));

        // Center gravity
        const cx = 500;
        const cy = 350;
        for (const n of updated) {
          if (n.id === draggedNodeId) continue;
          n.vx += (cx - n.x) * 0.001 * alphaRef.current;
          n.vy += (cy - n.y) * 0.001 * alphaRef.current;
        }

        // Repulsion between nodes
        for (let i = 0; i < updated.length; i++) {
          for (let j = i + 1; j < updated.length; j++) {
            const na = updated[i];
            const nb = updated[j];
            const dx = nb.x - na.x;
            const dy = nb.y - na.y;
            const distSq = dx * dx + dy * dy || 1;
            const dist = Math.sqrt(distSq);
            if (dist < 280) {
              const force = (280 - dist) / dist * 0.4 * alphaRef.current;
              if (na.id !== draggedNodeId) {
                na.vx -= dx * force;
                na.vy -= dy * force;
              }
              if (nb.id !== draggedNodeId) {
                nb.vx += dx * force;
                nb.vy += dy * force;
              }
            }
          }
        }

        // Spring attraction along edges
        for (const edge of edges) {
          const src = nodeMap.get(edge.source_node_id);
          const tgt = nodeMap.get(edge.target_node_id);
          if (!src || !tgt) continue;

          const nSrc = updated.find((n) => n.id === src.id);
          const nTgt = updated.find((n) => n.id === tgt.id);
          if (!nSrc || !nTgt) continue;

          const dx = nTgt.x - nSrc.x;
          const dy = nTgt.y - nSrc.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const targetDist = 120;
          const force = (dist - targetDist) * 0.02 * alphaRef.current;

          if (nSrc.id !== draggedNodeId) {
            nSrc.vx += (dx / dist) * force;
            nSrc.vy += (dy / dist) * force;
          }
          if (nTgt.id !== draggedNodeId) {
            nTgt.vx -= (dx / dist) * force;
            nTgt.vy -= (dy / dist) * force;
          }
        }

        // Velocity damping and integration
        for (const n of updated) {
          if (n.id === draggedNodeId) continue;
          n.vx *= 0.85;
          n.vy *= 0.85;
          n.x += n.vx;
          n.y += n.vy;

          // Soft boundary clamping
          n.x = Math.max(80, Math.min(920, n.x));
          n.y = Math.max(80, Math.min(620, n.y));
        }

        alphaRef.current *= 0.96;
        return updated;
      });

      animFrameRef.current = requestAnimationFrame(tick);
    };

    animFrameRef.current = requestAnimationFrame(tick);

    return () => {
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current);
        animFrameRef.current = null;
      }
    };
  }, [nodes.length, edges, draggedNodeId]);

  // 3. Filtered Nodes and Edges
  const filteredNodes = useMemo(() => {
    return nodes.filter((node) => {
      const matchesType = typeFilter === 'all' || node.node_type.toLowerCase() === typeFilter.toLowerCase();
      const matchesSearch =
        !searchQuery || node.label.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesType && matchesSearch;
    });
  }, [nodes, typeFilter, searchQuery]);

  const visibleNodeIds = useMemo(() => {
    return new Set(filteredNodes.map((n) => n.id));
  }, [filteredNodes]);

  const filteredEdges = useMemo(() => {
    return edges.filter(
      (e) => visibleNodeIds.has(e.source_node_id) && visibleNodeIds.has(e.target_node_id)
    );
  }, [edges, visibleNodeIds]);

  const selectedNode = useMemo(() => {
    return nodes.find((n) => n.id === selectedNodeId) || null;
  }, [nodes, selectedNodeId]);

  // 4. Neighborhood expansion
  const handleExpandNeighborhood = async (nodeId: string) => {
    setExpandingNeighborhood(true);
    try {
      const res = await fetch(
        `http://127.0.0.1:8000/api/v1/graph/neighborhood/${nodeId}?depth=2&direction=all`,
        { headers: authHeaders }
      );
      if (res.ok) {
        const neighborhood = await res.json();
        const existingNodeIds = new Set(nodes.map((n) => n.id));
        const newSimNodes: SimulationNode[] = [];

        for (const n of neighborhood.nodes) {
          if (!existingNodeIds.has(n.id)) {
            newSimNodes.push({
              ...n,
              x: 500 + (Math.random() - 0.5) * 200,
              y: 350 + (Math.random() - 0.5) * 200,
              vx: 0,
              vy: 0,
            });
          }
        }

        const existingEdgeIds = new Set(edges.map((e) => e.id));
        const newEdges = neighborhood.edges.filter((e: KnowledgeEdgeItem) => !existingEdgeIds.has(e.id));

        if (newSimNodes.length > 0 || newEdges.length > 0) {
          setNodes((prev) => [...prev, ...newSimNodes]);
          setEdges((prev) => [...prev, ...newEdges]);
          alphaRef.current = 0.8;
        }
      }
    } catch (err) {
      console.error('Failed to expand neighborhood:', err);
    } finally {
      setExpandingNeighborhood(false);
    }
  };

  // 5. Shortest path search
  const handleFindShortestPath = async () => {
    if (!pathSourceId || !pathTargetId) return;
    try {
      const res = await fetch(
        `http://127.0.0.1:8000/api/v1/graph/shortest-path?source_node_id=${pathSourceId}&target_node_id=${pathTargetId}`,
        { headers: authHeaders }
      );
      if (res.ok) {
        const data: GraphShortestPath = await res.json();
        setShortestPathData(data);
      }
    } catch (err) {
      console.error('Shortest path error:', err);
    }
  };

  // 6. Create Node
  const handleCreateNode = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNodeLabel.trim()) return;

    try {
      const res = await fetch('http://127.0.0.1:8000/api/v1/graph/nodes', {
        method: 'POST',
        headers: authHeaders,
        body: JSON.stringify({
          label: newNodeLabel.trim(),
          node_type: newNodeType,
        }),
      });
      if (res.ok) {
        const created: KnowledgeNodeItem = await res.json();
        setNodes((prev) => [
          ...prev,
          {
            ...created,
            x: 500 + (Math.random() - 0.5) * 100,
            y: 350 + (Math.random() - 0.5) * 100,
            vx: 0,
            vy: 0,
          },
        ]);
        setNewNodeLabel('');
        setShowAddNodeModal(false);
        alphaRef.current = 0.8;
      }
    } catch (err) {
      console.error('Failed to create node:', err);
    }
  };

  // 7. Create Edge
  const handleCreateEdge = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEdgeSource || !newEdgeTarget || newEdgeSource === newEdgeTarget) return;

    try {
      const res = await fetch('http://127.0.0.1:8000/api/v1/graph/edges', {
        method: 'POST',
        headers: authHeaders,
        body: JSON.stringify({
          source_node_id: newEdgeSource,
          target_node_id: newEdgeTarget,
          relation_type: newEdgeRelation,
        }),
      });
      if (res.ok) {
        const created: KnowledgeEdgeItem = await res.json();
        setEdges((prev) => [...prev, created]);
        setShowAddEdgeModal(false);
        alphaRef.current = 0.8;
      }
    } catch (err) {
      console.error('Failed to create edge:', err);
    }
  };

  // 8. Delete Node
  const handleDeleteNode = async (id: string) => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/v1/graph/nodes/${id}`, {
        method: 'DELETE',
        headers: authHeaders,
      });
      if (res.ok) {
        setNodes((prev) => prev.filter((n) => n.id !== id));
        setEdges((prev) => prev.filter((e) => e.source_node_id !== id && e.target_node_id !== id));
        if (selectedNodeId === id) setSelectedNodeId(null);
      }
    } catch (err) {
      console.error('Failed to delete node:', err);
    }
  };

  // Pan & Zoom controls
  const handleMouseDownCanvas = (e: React.MouseEvent) => {
    if (e.target === svgRef.current || (e.target as HTMLElement).tagName === 'svg') {
      setIsDraggingCanvas(true);
      setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDraggingCanvas) {
      setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
    } else if (draggedNodeId) {
      setNodes((prev) =>
        prev.map((n) => {
          if (n.id === draggedNodeId) {
            return {
              ...n,
              x: (e.clientX - pan.x - 200) / zoom,
              y: (e.clientY - pan.y - 100) / zoom,
              vx: 0,
              vy: 0,
            };
          }
          return n;
        })
      );
      alphaRef.current = 0.3;
    }
  };

  const handleMouseUp = () => {
    setIsDraggingCanvas(false);
    setDraggedNodeId(null);
  };

  return (
    <div className="flex flex-col h-screen bg-[#0a0d14] text-slate-100 overflow-hidden font-sans">
      {/* Top Navigation & Status Bar */}
      <header className="flex items-center justify-between px-6 py-3.5 border-b border-slate-800 bg-[#0f1422]/90 backdrop-blur z-20">
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400">
              <Network className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-base font-semibold text-white tracking-wide flex items-center gap-2">
                Knowledge Graph
                <span className="text-xs px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 font-mono">
                  Phase 7
                </span>
              </h1>
              <p className="text-xs text-slate-400">Relational topology & hybrid graph expansion</p>
            </div>
          </div>

          <div className="h-6 w-px bg-slate-800" />

          {/* Quick tab switch back to documents */}
          <div className="flex items-center bg-slate-900 border border-slate-800 rounded-lg p-0.5 text-xs">
            <Link
              href="/knowledge"
              className="px-3 py-1.5 rounded-md text-slate-400 hover:text-white transition"
            >
              Documents & RAG
            </Link>
            <span className="px-3 py-1.5 rounded-md bg-purple-600/20 text-purple-300 font-medium border border-purple-500/30">
              Graph Topology
            </span>
          </div>
        </div>

        {/* Global Action Tools */}
        <div className="flex items-center space-x-3">
          <button
            onClick={() => setShowPathModal(true)}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800/80 hover:bg-slate-700 text-xs font-medium text-slate-200 transition"
          >
            <Compass className="w-3.5 h-3.5 text-amber-400" />
            <span>Find Shortest Path</span>
          </button>

          <button
            onClick={() => setShowAddEdgeModal(true)}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800/80 hover:bg-slate-700 text-xs font-medium text-slate-200 transition"
          >
            <ArrowRight className="w-3.5 h-3.5 text-cyan-400" />
            <span>Connect Relation</span>
          </button>

          <button
            onClick={() => setShowAddNodeModal(true)}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-xs font-medium text-white shadow-lg shadow-purple-900/30 transition"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Entity</span>
          </button>

          <button
            onClick={fetchGraph}
            title="Reload graph"
            className="p-1.5 rounded-lg border border-slate-800 hover:bg-slate-800 text-slate-400 hover:text-white transition"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </header>

      {/* Control Bar: Filters & Search */}
      <div className="flex items-center justify-between px-6 py-2 border-b border-slate-800/80 bg-[#0d111c] text-xs z-10">
        <div className="flex items-center space-x-2">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2" />
            <input
              type="text"
              placeholder="Search entity nodes..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-slate-900 border border-slate-800 rounded-lg pl-8 pr-3 py-1 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-purple-500 w-52 text-xs"
            />
          </div>

          <div className="flex items-center space-x-1 pl-2">
            <Filter className="w-3.5 h-3.5 text-slate-500 mr-1" />
            {['all', 'concept', 'document', 'technology', 'task', 'person'].map((t) => (
              <button
                key={t}
                onClick={() => setTypeFilter(t)}
                className={`px-2.5 py-1 rounded-md capitalize transition ${
                  typeFilter === t
                    ? 'bg-purple-950/80 text-purple-300 border border-purple-500/40 font-medium'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {/* Overview metric pills */}
        <div className="flex items-center space-x-4 text-slate-400">
          <div className="flex items-center space-x-1.5">
            <span className="w-2 h-2 rounded-full bg-purple-400" />
            <span>Entities: <strong className="text-slate-200">{filteredNodes.length}</strong></span>
          </div>
          <div className="flex items-center space-x-1.5">
            <span className="w-2 h-2 rounded-full bg-cyan-400" />
            <span>Relations: <strong className="text-slate-200">{filteredEdges.length}</strong></span>
          </div>
          {overview && (
            <div className="text-slate-500">
              Database total: {overview.total_nodes} nodes / {overview.total_edges} edges
            </div>
          )}
        </div>
      </div>

      {/* Main Canvas Area + Side Drawer */}
      <div className="relative flex-1 flex overflow-hidden">
        {/* SVG Graph Canvas */}
        <div
          className="flex-1 relative cursor-grab active:cursor-grabbing bg-radial from-slate-900/30 to-[#07090e]"
          onMouseDown={handleMouseDownCanvas}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
        >
          {loading && nodes.length === 0 ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center space-y-3 z-10 bg-[#0a0d14]/70">
              <RefreshCw className="w-8 h-8 text-purple-400 animate-spin" />
              <p className="text-xs text-slate-400 tracking-wide">Synthesizing relational knowledge graph...</p>
            </div>
          ) : null}

          <svg
            ref={svgRef}
            className="w-full h-full select-none"
            viewBox="0 0 1000 700"
          >
            <defs>
              <marker
                id="arrow"
                viewBox="0 0 10 10"
                refX="22"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b" />
              </marker>
              <marker
                id="arrow-active"
                viewBox="0 0 10 10"
                refX="22"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#a855f7" />
              </marker>
            </defs>

            <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
              {/* Directed Edges */}
              {filteredEdges.map((edge) => {
                const src = nodes.find((n) => n.id === edge.source_node_id);
                const tgt = nodes.find((n) => n.id === edge.target_node_id);
                if (!src || !tgt) return null;

                const isIncident =
                  selectedNodeId &&
                  (edge.source_node_id === selectedNodeId || edge.target_node_id === selectedNodeId);

                const isPathEdge =
                  shortestPathData &&
                  shortestPathData.edges.some((pe) => pe.id === edge.id);

                const midX = (src.x + tgt.x) / 2;
                const midY = (src.y + tgt.y) / 2;

                return (
                  <g key={edge.id} className="transition-opacity duration-300">
                    <line
                      x1={src.x}
                      y1={src.y}
                      x2={tgt.x}
                      y2={tgt.y}
                      stroke={isPathEdge ? '#f59e0b' : isIncident ? '#a855f7' : '#334155'}
                      strokeWidth={isPathEdge ? 2.5 : isIncident ? 2 : 1.2}
                      strokeDasharray={isPathEdge ? '4 2' : undefined}
                      markerEnd={isIncident || isPathEdge ? 'url(#arrow-active)' : 'url(#arrow)'}
                    />
                    {/* Relation badge on edge */}
                    <rect
                      x={midX - 25}
                      y={midY - 8}
                      width="50"
                      height="16"
                      rx="4"
                      fill="#0f172a"
                      stroke={isIncident ? '#9333ea' : '#1e293b'}
                      strokeWidth="0.8"
                    />
                    <text
                      x={midX}
                      y={midY + 3.5}
                      textAnchor="middle"
                      fill={isIncident ? '#c084fc' : '#64748b'}
                      fontSize="8"
                      fontFamily="monospace"
                    >
                      {edge.relation_type.slice(0, 8)}
                    </text>
                  </g>
                );
              })}

              {/* Entity Nodes */}
              {filteredNodes.map((node) => {
                const isSelected = selectedNodeId === node.id;
                const config = TYPE_CONFIG[node.node_type] || TYPE_CONFIG.other;

                const isPathNode =
                  shortestPathData &&
                  shortestPathData.nodes.some((pn) => pn.id === node.id);

                return (
                  <g
                    key={node.id}
                    transform={`translate(${node.x}, ${node.y})`}
                    className="cursor-pointer group"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedNodeId(node.id);
                    }}
                    onMouseDown={(e) => {
                      e.stopPropagation();
                      setDraggedNodeId(node.id);
                    }}
                  >
                    {/* Selected glow ring */}
                    {(isSelected || isPathNode) && (
                      <circle
                        r="26"
                        fill="none"
                        stroke={isPathNode ? '#f59e0b' : '#a855f7'}
                        strokeWidth="2"
                        strokeDasharray="4 2"
                        className="animate-spin-slow"
                      />
                    )}

                    {/* Node base circle */}
                    <circle
                      r="18"
                      fill="#0f172a"
                      stroke={isSelected ? '#c084fc' : isPathNode ? '#fbbf24' : '#334155'}
                      strokeWidth={isSelected ? 2.5 : 1.5}
                      className="transition duration-200 group-hover:stroke-purple-400"
                    />

                    {/* Node center indicator */}
                    <circle
                      r="6"
                      fill={
                        node.node_type === 'concept'
                          ? '#a855f7'
                          : node.node_type === 'document'
                          ? '#3b82f6'
                          : node.node_type === 'technology'
                          ? '#10b981'
                          : node.node_type === 'task'
                          ? '#f59e0b'
                          : node.node_type === 'person'
                          ? '#06b6d4'
                          : '#94a3b8'
                      }
                    />

                    {/* Label pill */}
                    <g transform="translate(0, 28)">
                      <rect
                        x={-Math.min(80, Math.max(30, node.label.length * 4.2))}
                        y="-7"
                        width={Math.min(160, Math.max(60, node.label.length * 8.4))}
                        height="14"
                        rx="4"
                        fill="#0b0f19"
                        stroke={isSelected ? '#9333ea' : '#1e293b'}
                        strokeWidth="0.8"
                      />
                      <text
                        x="0"
                        y="3"
                        textAnchor="middle"
                        fill={isSelected ? '#ffffff' : '#cbd5e1'}
                        fontSize="9"
                        fontWeight={isSelected ? '600' : '400'}
                      >
                        {node.label.length > 18 ? node.label.slice(0, 16) + '...' : node.label}
                      </text>
                    </g>
                  </g>
                );
              })}
            </g>
          </svg>

          {/* Canvas Floating Controls */}
          <div className="absolute bottom-4 right-4 flex items-center space-x-1.5 bg-[#0f1422]/90 border border-slate-800 p-1.5 rounded-xl shadow-xl backdrop-blur">
            <button
              onClick={() => setZoom((z) => Math.min(2.5, z + 0.2))}
              className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition"
              title="Zoom In"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
            <button
              onClick={() => setZoom((z) => Math.max(0.4, z - 0.2))}
              className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition"
              title="Zoom Out"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <button
              onClick={() => {
                setZoom(1);
                setPan({ x: 0, y: 0 });
              }}
              className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition"
              title="Reset View"
            >
              <Maximize2 className="w-4 h-4" />
            </button>
          </div>

          {/* Node Legend */}
          <div className="absolute top-4 left-4 flex flex-wrap gap-2 p-2 rounded-xl bg-[#0f1422]/80 border border-slate-800/80 backdrop-blur max-w-sm">
            {Object.entries(TYPE_CONFIG).map(([typeKey, cfg]) => (
              <div key={typeKey} className="flex items-center space-x-1.5 text-[10px] text-slate-300">
                <span className={`p-1 rounded-md ${cfg.bg} border ${cfg.border}`}>{cfg.icon}</span>
                <span className="capitalize">{typeKey}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Node Inspector Side Drawer */}
        {selectedNode && (
          <aside className="w-84 border-l border-slate-800 bg-[#0d111c] flex flex-col p-5 overflow-y-auto shadow-2xl z-20">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center space-x-2">
                <div
                  className={`p-1.5 rounded-lg ${
                    (TYPE_CONFIG[selectedNode.node_type] || TYPE_CONFIG.other).bg
                  } border ${(TYPE_CONFIG[selectedNode.node_type] || TYPE_CONFIG.other).border}`}
                >
                  {(TYPE_CONFIG[selectedNode.node_type] || TYPE_CONFIG.other).icon}
                </div>
                <span className="text-xs uppercase font-mono tracking-wider text-slate-400">
                  {selectedNode.node_type}
                </span>
              </div>
              <button
                onClick={() => setSelectedNodeId(null)}
                className="p-1 rounded-md text-slate-500 hover:text-white hover:bg-slate-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="mt-4">
              <h2 className="text-base font-semibold text-white break-words">{selectedNode.label}</h2>
              <p className="text-[10px] font-mono text-slate-500 mt-1">ID: {selectedNode.id}</p>
            </div>

            {/* Neighborhood Expansion Button */}
            <div className="mt-4">
              <button
                onClick={() => handleExpandNeighborhood(selectedNode.id)}
                disabled={expandingNeighborhood}
                className="w-full flex items-center justify-center space-x-2 py-2 px-3 rounded-lg bg-purple-600/20 hover:bg-purple-600/30 border border-purple-500/30 text-purple-300 text-xs font-medium transition"
              >
                <Layers className={`w-3.5 h-3.5 ${expandingNeighborhood ? 'animate-pulse' : ''}`} />
                <span>
                  {expandingNeighborhood ? 'Expanding 2-Hop Network...' : 'Expand 2-Hop Neighborhood'}
                </span>
              </button>
            </div>

            {/* Incident Relations list */}
            <div className="mt-5">
              <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Incident Relations
              </h3>
              <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                {edges
                  .filter(
                    (e) =>
                      e.source_node_id === selectedNode.id || e.target_node_id === selectedNode.id
                  )
                  .map((e) => {
                    const isOutgoing = e.source_node_id === selectedNode.id;
                    const otherNodeId = isOutgoing ? e.target_node_id : e.source_node_id;
                    const otherNode = nodes.find((n) => n.id === otherNodeId);

                    return (
                      <div
                        key={e.id}
                        className="flex items-center justify-between p-2 rounded-lg bg-slate-900/70 border border-slate-800 text-xs"
                      >
                        <div className="flex items-center space-x-1.5 truncate">
                          <span
                            className={`text-[9px] font-mono uppercase px-1.5 py-0.5 rounded ${
                              isOutgoing
                                ? 'bg-indigo-950 text-indigo-300 border border-indigo-500/30'
                                : 'bg-cyan-950 text-cyan-300 border border-cyan-500/30'
                            }`}
                          >
                            {isOutgoing ? 'OUT' : 'IN'}
                          </span>
                          <span className="text-purple-400 font-mono text-[11px] font-medium">
                            {e.relation_type}
                          </span>
                          <span className="text-slate-300 truncate">
                            {otherNode?.label || otherNodeId}
                          </span>
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>

            {/* Node Properties */}
            {selectedNode.properties && Object.keys(selectedNode.properties).length > 0 && (
              <div className="mt-5">
                <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                  Properties
                </h3>
                <pre className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-[11px] font-mono text-slate-300 overflow-x-auto">
                  {JSON.stringify(selectedNode.properties, null, 2)}
                </pre>
              </div>
            )}

            {/* Danger Zone: Delete Node */}
            <div className="mt-auto pt-6">
              <button
                onClick={() => handleDeleteNode(selectedNode.id)}
                className="w-full py-2 px-3 rounded-lg border border-red-500/30 bg-red-950/30 hover:bg-red-900/40 text-red-400 text-xs font-medium transition"
              >
                Delete Entity & Cascade Edges
              </button>
            </div>
          </aside>
        )}
      </div>

      {/* MODAL 1: Create Entity Node */}
      {showAddNodeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-md p-6 rounded-2xl bg-[#0f1422] border border-slate-800 shadow-2xl">
            <h3 className="text-base font-semibold text-white mb-1">Create Knowledge Entity</h3>
            <p className="text-xs text-slate-400 mb-4">Add a new conceptual or domain entity node</p>
            <form onSubmit={handleCreateNode} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Entity Label</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. ModelGateway, Authentication, PostgreSQL"
                  value={newNodeLabel}
                  onChange={(e) => setNewNodeLabel(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-purple-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Node Type</label>
                <select
                  value={newNodeType}
                  onChange={(e) => setNewNodeType(e.target.value as NodeType)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-purple-500"
                >
                  <option value="concept">Concept</option>
                  <option value="technology">Technology</option>
                  <option value="document">Document</option>
                  <option value="task">Task</option>
                  <option value="project">Project</option>
                  <option value="person">Person</option>
                  <option value="other">Other</option>
                </select>
              </div>

              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddNodeModal(false)}
                  className="px-4 py-2 rounded-lg text-xs font-medium text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg text-xs font-medium bg-purple-600 hover:bg-purple-500 text-white transition"
                >
                  Create Entity
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: Create Relation Edge */}
      {showAddEdgeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-md p-6 rounded-2xl bg-[#0f1422] border border-slate-800 shadow-2xl">
            <h3 className="text-base font-semibold text-white mb-1">Connect Relational Edge</h3>
            <p className="text-xs text-slate-400 mb-4">Create a directed relation between two existing entities</p>
            <form onSubmit={handleCreateEdge} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Source Entity</label>
                <select
                  required
                  value={newEdgeSource}
                  onChange={(e) => setNewEdgeSource(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-purple-500"
                >
                  <option value="">Select source entity...</option>
                  {nodes.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.label} ({n.node_type})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Relation Type</label>
                <select
                  value={newEdgeRelation}
                  onChange={(e) => setNewEdgeRelation(e.target.value as RelationType)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-purple-500"
                >
                  <option value="knows">knows</option>
                  <option value="contains">contains</option>
                  <option value="references">references</option>
                  <option value="uses">uses</option>
                  <option value="depends_on">depends_on</option>
                  <option value="authored_by">authored_by</option>
                  <option value="related_to">related_to</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Target Entity</label>
                <select
                  required
                  value={newEdgeTarget}
                  onChange={(e) => setNewEdgeTarget(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-purple-500"
                >
                  <option value="">Select target entity...</option>
                  {nodes.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.label} ({n.node_type})
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddEdgeModal(false)}
                  className="px-4 py-2 rounded-lg text-xs font-medium text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg text-xs font-medium bg-cyan-600 hover:bg-cyan-500 text-white transition"
                >
                  Connect
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 3: Shortest Path */}
      {showPathModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-lg p-6 rounded-2xl bg-[#0f1422] border border-slate-800 shadow-2xl">
            <h3 className="text-base font-semibold text-white mb-1">Find Shortest Directed Path</h3>
            <p className="text-xs text-slate-400 mb-4">
              Compute the shortest path using recursive SQL CTE traversal
            </p>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Start Node</label>
                <select
                  value={pathSourceId}
                  onChange={(e) => setPathSourceId(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100"
                >
                  <option value="">Select origin...</option>
                  {nodes.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Destination Node</label>
                <select
                  value={pathTargetId}
                  onChange={(e) => setPathTargetId(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100"
                >
                  <option value="">Select destination...</option>
                  {nodes.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.label}
                    </option>
                  ))}
                </select>
              </div>

              {shortestPathData && (
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs">
                  {shortestPathData.found ? (
                    <div>
                      <div className="text-emerald-400 font-medium mb-1">
                        Path found ({shortestPathData.length} hops, total weight: {shortestPathData.total_weight}):
                      </div>
                      <div className="flex flex-wrap items-center gap-1.5 mt-2">
                        {shortestPathData.nodes.map((pn, i) => (
                          <React.Fragment key={pn.id}>
                            <span className="px-2 py-1 rounded bg-slate-800 text-purple-300 font-medium">
                              {pn.label}
                            </span>
                            {i < shortestPathData.nodes.length - 1 && (
                              <ArrowRight className="w-3.5 h-3.5 text-slate-500" />
                            )}
                          </React.Fragment>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div className="text-amber-400">No path exists between the selected nodes within 5 hops.</div>
                  )}
                </div>
              )}

              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowPathModal(false);
                    setShortestPathData(null);
                  }}
                  className="px-4 py-2 rounded-lg text-xs font-medium text-slate-400 hover:text-white"
                >
                  Close
                </button>
                <button
                  onClick={handleFindShortestPath}
                  className="px-4 py-2 rounded-lg text-xs font-medium bg-amber-600 hover:bg-amber-500 text-white transition"
                >
                  Compute Path
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
