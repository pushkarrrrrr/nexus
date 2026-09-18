# NEXUS Engineering Roadmap & Milestone Deliverables

This roadmap establishes the phased development plan for the **NEXUS Agentic AI Operating System** capstone project.

---

## Phase Overview

```
Phase 0: Project Constitution & Monorepo Setup (IN PROGRESS)
   │
   ▼
Phase 1: Policy Engine, Audit Subsystem & Security Kernel
   │
   ▼
Phase 2: AI Gateway, 5-Class Memory & Orchestration Engine
   │
   ▼
Phase 3: NEXUS Web Dashboard (Next.js + Tailwind + shadcn/ui)
   │
   ▼
Phase 4: NEXUS Ambient Layer (Tauri Desktop Overlay + MacOS Adapter)
   │
   ▼
Phase 5: Personal Knowledge RAG & Controlled Browser Automation
   │
   ▼
Phase 6: Academic Evaluation Suite & Capstone Benchmarking
```

---

## Detailed Milestones

### Phase 0: Project Constitution & Monorepo Setup (CURRENT)
- [x] Comprehensive repository audit (clean slate).
- [x] Monorepo directory hierarchy setup (`apps/`, `services/`, `packages/`, `infra/`, `docs/`, `evals/`, `scripts/`).
- [x] Engineering rules established in `AGENTS.md`.
- [x] System Architecture documented in `docs/ARCHITECTURE.md`.
- [x] Product Specification documented in `docs/PRODUCT_SPEC.md`.
- [x] Security & Permission Model documented in `docs/SECURITY_MODEL.md`.
- [x] Shared TypeScript and Python domain contracts defined in `packages/types`.
- [x] Initial database schema entities specified.
- [x] Architecture artifact produced and reviewed.

### Phase 1: Policy Engine, Audit Subsystem & Security Kernel
- [ ] Implement `PolicyEngine` (action classification, risk scoring, session cache).
- [ ] Implement `SnapshotEngine` (pre-execution file backup, SHA-256 hash checks, diff generator).
- [ ] Implement `AuditLedger` (immutable append-only SQLite/Postgres log).
- [ ] Implement `ToolRegistry` with initial sandboxed tools:
  - `filesystem.read`, `filesystem.write`, `filesystem.modify`, `filesystem.delete`
  - `terminal.execute` (command parser, path containment, timeout enforcement)
- [ ] Implement rollback execution handlers.
- [ ] Automated test suite for all security and rollback paths (`pytest` / unit + integration).
- [ ] Verification gate: Linting, type checks, tests, documentation updates.

### Phase 2: AI Gateway, 5-Class Memory & Orchestration Engine
- [ ] Provider-agnostic AI Gateway (OpenAI, Anthropic, Gemini, Ollama) with structured output generation.
- [ ] 5-Class Memory Layer implementation:
  - Working memory (DAG step scratchpad)
  - Conversational memory (multi-turn session context)
  - Episodic memory (historical tasks and outcomes)
  - Semantic memory (user facts and preferences)
  - Procedural memory (reusable tool execution workflows)
- [ ] DAG Task Planner & Orchestrator with topological execution.
- [ ] Multi-agent persona definitions (Orchestrator, Coder, System, Research).
- [ ] FastAPI WebSocket event bus for bidirectional streaming.
- [ ] Verification gate: End-to-end multi-step task simulations.

### Phase 3: NEXUS Web Dashboard
- [ ] Next.js 14+ (App Router, TypeScript, Tailwind CSS, shadcn/ui).
- [ ] Real-time WebSocket connection to NEXUS Core event bus.
- [ ] Live Chat & DAG Execution Graph visualizer.
- [ ] Concrete Diff-Based Approval Modal (Syntax highlighted before/after diffs).
- [ ] Interactive Memory Inspector (view, edit, delete, toggle classes).
- [ ] Actionable Audit Log Viewer with 1-click Undo buttons.
- [ ] Verification gate: Browser verification, component unit tests, and production build test.

### Phase 4: NEXUS Ambient Layer (Desktop Spotlight)
- [ ] Tauri (Rust native layer + React/TS frontend).
- [ ] Global hotkey daemon (`Cmd+Shift+Space` on macOS).
- [ ] Frameless, transparent, floating command HUD centered on active screen.
- [ ] Context capture via `MacOSAdapter` (active window title, selected text).
- [ ] Streaming response renderer, live tool activity ticker, and inline approval prompts.
- [ ] Verification gate: Native desktop launch, hotkey summon verification, and memory footprint audit.

### Phase 5: Personal Knowledge RAG & Controlled Browser Automation
- [ ] Document ingestion pipeline (markdown, code, text, PDF) with local vector embeddings.
- [ ] Hybrid retrieval (BM25 keyword search + vector cosine similarity).
- [ ] Playwright-based controlled browser tools (`browser.open`, `browser.search`, `browser.click`, `browser.type`).
- [ ] Screenshot & DOM element extraction with policy gating.
- [ ] Verification gate: Live local folder indexing and web scraping tests.

### Phase 6: Academic Research Evaluation Suite & Capstone Benchmarking
- [ ] Automated evaluation harness in `evals/`.
- [ ] Standardized benchmark task suite (software engineering, system admin, research synthesis).
- [ ] Formal ablation experiments:
  1. Baseline Conversational LLM
  2. RAG-Enhanced Assistant
  3. Memory + RAG System
  4. Full Agentic NEXUS Operating Layer
- [ ] Metrics computation: Task Success Rate, Planning Accuracy, Latency, Cost ($), Safety Violation Rate.
- [ ] Final Capstone Report generation and evaluation artifact exports.
