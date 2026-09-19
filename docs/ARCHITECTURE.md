# NEXUS System Architecture

This document defines the architectural boundaries, subsystems, data flow, trust model, and component lifecycles for the **NEXUS Agentic AI Operating System**.

---

## 1. High-Level System Architecture

```
                   ┌────────────────────────────────────────────────────────┐
                   │                     USER SURFACES                      │
                   ├────────────────────────────┬───────────────────────────┤
                   │      NEXUS Dashboard       │    NEXUS Ambient Layer    │
                   │   (Next.js Web / Port 3000)│ (Tauri Desktop Spotlight) │
                   └─────────────┬──────────────┴─────────────┬─────────────┘
                                 │                            │
                                 │ WebSocket / REST API       │
                                 ▼                            ▼
                   ┌────────────────────────────────────────────────────────┐
                   │                   SERVICES / API LAYER                 │
                   │               (FastAPI / Async Engine / Port 8000)     │
                   └──────┬──────────────────┬───────────────────┬──────────┘
                          │                  │                   │
                          ▼                  ▼                   ▼
                   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
                   │  AI GATEWAY  │   │ ORCHESTRATOR │   │ POLICY ENGINE│
                   │(Multi-Model) │   │ (DAG Engine) │   │ (HITL Gating)│
                   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
                          │                  │                   │
                          ▼                  ▼                   ▼
                   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
                   │ MEMORY LAYER │   │  KNOWLEDGE   │   │  TOOL LAYER  │
                   │(5 Taxonomies)│   │ (Hybrid RAG) │   │ (OS/Browser) │
                   └──────────────┘   └──────────────┘   └──────┬───────┘
                                                                │
                                                                ▼
                                                         ┌──────────────┐
                                                         │ AUDIT & UNDO │
                                                         │ (Snapshots)  │
                                                         └──────────────┘
```

---

## 2. System Subsystem Boundaries

| Subsystem | Boundary / Location | Responsibility | Inbound Interfaces | Outbound Interfaces |
|---|---|---|---|---|
| **Dashboard** | `apps/dashboard` | Full visual control center (Chat, DAG graphs, Memory/Knowledge inspectors, Audit ledger, Settings). | User interaction | REST API, WebSocket event bus |
| **Ambient Layer** | `apps/ambient` | Global hotkey overlay HUD (Raycast/Spotlight model, minimal latency, quick summon, inline approvals). | User hotkey & input | REST API, WebSocket event bus |
| **Core API** | `services/api` | Fast, stateless HTTP routing, WebSocket session management, authentication, and synchronous validation. | Client requests | Orchestrator, Database, Audit Ledger |
| **Worker** | `services/worker` | Async background execution for long-running DAG tasks, document chunking/indexing, and benchmark evals. | Redis/Postgres queue | Tool execution, Vector DB, Knowledge store |
| **AI Gateway** | `packages/shared/ai` | Model-provider abstraction layer (OpenAI, Anthropic, Gemini, Ollama/Local) with token & cost tracking. | Orchestrator, Agents | Provider HTTP APIs |
| **Memory** | `packages/shared/memory` | Stores and retrieves Working, Conversational, Episodic, Semantic, and Procedural memory classes. | Orchestrator, API | SQLite/Postgres storage |
| **Knowledge** | `packages/shared/knowledge` | Document parsing, text chunking, local vector embeddings, and hybrid semantic search. | Research Agent, API | pgvector / LanceDB store |
| **Orchestration** | `packages/shared/orchestrator`| Intent parsing, DAG task generation, sub-agent delegation, and observation evaluation. | API / Worker | Sub-agents, Memory, Policy Engine |
| **Policy Engine** | `packages/shared/policy` | Gating authority for every action; evaluates risk tier, checks grants cache, issues HITL approval locks. | Orchestrator, Agents | Approval event bus, Tool Layer |
| **Tool Layer** | `packages/shared/tools` | Sandboxed capability registry (`filesystem.*`, `terminal.*`, `browser.*`, `github.*`). | Policy Engine (authorized only)| OS Adapters, Browser, Network |
| **Computer Control**| `packages/shared/computer` | Platform-specific OS automation (`MacOSAdapter`, `LinuxAdapter`, `WindowsAdapter`). | Tool Layer | Native OS APIs, Shell, Accessibility |
| **Audit & Undo** | `packages/shared/audit` | Append-only event log, pre-execution file snapshotting, diff generation, and rollback handlers. | Policy Engine, Tool Layer | SQLite/Postgres ledger, Snapshot storage |

---

## 3. Data Flow & Communication Lifecycle

```
1. Client Submission:
   User submits request via Dashboard or Ambient overlay.

2. Transport:
   Request sent via WebSocket:
   {
     "event_type": "request.submit",
     "session_id": "sess_123",
     "payload": { "query": "Build and test the auth module" }
   }

3. Context & Intent Resolution:
   Orchestrator ingests OS context (active window, cwd) and queries Memory + Knowledge layers.

4. DAG Plan Synthesis:
   Planning Agent returns a structured DAG:
   Step 1: Read files (Risk: LOW)
   Step 2: Modify code (Risk: MEDIUM, Reversible)
   Step 3: Run pytest (Risk: MEDIUM)

5. Policy Gating:
   PolicyEngine inspects each step before dispatch:
   - If action is SAFE/LOW: Auto-authorized.
   - If action is SENSITIVE/MEDIUM/HIGH: Generates an ApprovalRequest with diff preview,
     pushes to WebSocket, and blocks execution until user approves via Dashboard or Ambient HUD.

6. Controlled Execution & Snapshotting:
   - Tool Layer takes snapshot of target files.
   - Executes authorized operation via ComputerControlAdapter.
   - Captures stdout, stderr, and exit code.

7. Audit Recording:
   - Writes immutable event row to the Audit Ledger with execution metrics.
   - Registers rollback action in the Undo Registry.

8. Streaming & Feedback:
   - Results, updated DAG states, and final responses are streamed back to both clients.
```

---

## 4. Trust Boundaries & Security Enclaves

```
[ UNTRUSTED ZONE ]
  User Raw Input / Untrusted Web Data / Third-Party File Contents
         │
         ▼  (Input Sanitization & Schema Validation)
[ REASONING ZONE ]
  LLM Prompts / Orchestrator / Sub-Agent Scratchpads
         │
         ▼  (Strict Tool Request via JSON Schema)
[ GOVERNANCE ZONE ] ◄── MANDATORY AIR-GAP
  Policy Engine / Risk Classifier / Human-in-the-Loop Approval Modal
         │
         ▼  (Explicit Signature of Approval)
[ EXECUTION ZONE ]
  ComputerControlAdapter / OS Subprocess / Playwright Browser
         │
         ▼  (State Diff Capture)
[ LEDGER ZONE ]
  Append-Only Audit Log / Immutable Snapshot Vault
```

1. **Untrusted Zone to Reasoning Zone**: Raw web content and files are treated as untrusted data; prompt injection defenses isolate system prompts from user documents.
2. **Reasoning Zone to Governance Zone**: Agents have **zero** direct access to system handles. They can only emit declarative tool invocation requests.
3. **Governance Zone to Execution Zone**: The Policy Engine holds exclusive execution keys. No tool runs without explicit policy clearance or cryptographic session grant.
4. **Execution Zone to Ledger Zone**: Every mutation must be preceded by a filesystem snapshot and followed by an immutable ledger entry.

---

## 5. Component Lifecycles

### A. Agent Lifecycle
```
Created (Scoped Context & Tools)
  ──► Prompt Synthesis (Injected Memory + Rules)
  ──► LLM Inference
  ──► Structured Output Validation
  ──► Yield Tool Request / Final Answer
  ──► Terminated / Cleaned
```

### B. Tool Execution Lifecycle
```
Declared in Registry (Name, Input/Output Schema, Risk Level)
  ──► Dispatched by Agent
  ──► Policy Evaluation (Classified into Risk Tier)
  ──► Pre-execution Snapshot (if mutating)
  ──► Approval Resolution (Auto-allow or HITL modal)
  ──► Native Execution (Sandboxed subprocess / Adapter)
  ──► Post-execution Verification (Exit code, output validation)
  ──► Audit Ledger Committed
  ──► Result Returned to Agent
```

### C. Permission & Approval Lifecycle
```
Action Identified
  ──► Checked against Session Grants Cache
        ├── Match Found: Auto-execute
        └── No Match: Emit ApprovalRequest(Action, Reason, Diff, Risk)
              ├── User Approves Once: Execute single action; expire grant immediately
              ├── User Approves for Session: Cache grant for session_id; execute
              ├── User Approves Always (Read-Only): Persist permanent rule; execute
              └── User Denies: Abort action; inform Agent with user denial explanation
```

---

## 6. Dashboard & Ambient Surface Relationship

The **Dashboard** and **Ambient Layer** are two complementary interfaces to the **exact same** NEXUS Core:

- **State Parity**: A task initiated in the Ambient HUD is instantly visible in real-time on the Dashboard's DAG view.
- **Approval Multiplexing**: When an approval is required, the prompt appears simultaneously in the active Ambient HUD and the Dashboard notification center. An approval from either surface immediately unlocks execution.
- **Role Differentiation**:
  - *Ambient Layer*: Ephemeral, low-friction, high-velocity summon for in-flow queries, quick context actions, and prompt approvals.
  - *Dashboard*: Deep analytical cockpit for reviewing complex DAGs, multi-file diff inspections, memory graph editing, audit log rollbacks, and system configurations.

---

## 7. Memory, Knowledge & Personal RAG Architecture

```
User Context / Conversational Turn / Documents
   │
   ├── [Memory Extractor] (Noise filter, heuristic classification)
   │     ├── Working Memory (Task-scoped, active execution context)
   │     ├── Conversation Memory (Short-term context, recent interaction turns)
   │     ├── Episodic Memory (Events, task outcomes, retrospective lessons)
   │     ├── Semantic Memory (Permanent facts, preferences, user declarations)
   │     └── Procedural Memory (Reusable workflows, user coding habits)
   │
   ├── [Document Ingestion Pipeline] (BackgroundTasks / Async Worker)
   │     ├── Multi-Format Parser (PDF with PyPDF, Markdown, TXT, CSV, JSON)
   │     ├── Token / Character-Aware Chunking (Overlap + Positional metadata)
   │     └── SHA-256 Deduplication & Idempotent Upsert
   │
   ├── [Dual-Mode Vector Store]
   │     ├── VectorType Custom TypeDecorator (Dialect-aware)
   │     │     ├── PostgreSQL: pgvector.sqlalchemy.Vector(settings.EMBEDDING_DIMENSION)
   │     │     └── SQLite: sa.JSON with in-memory normalized cosine dot product
   │     └── Batch Embedding Generation via AI Gateway
   │
   └── [RAG Synthesis Engine]
         ├── Multi-Source Semantic Retrieval (Top-K Knowledge + Top-K Memories)
         ├── Threshold Filtering (Relevance Score Cutoff)
         ├── Context Grounding & Strict Source Attribution
         └── Synthesis via ModelGateway with Grounded Citations
```
