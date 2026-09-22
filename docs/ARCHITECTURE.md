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

---

## 8. Knowledge Graph & Relational Traversal Architecture

```
Ingested Documents / Memories / User Entities
   │
   ├── [Relation Extractor]
   │     ├── Document Entity Detection (Concepts, Technologies, Markdown Headers)
   │     ├── Automatic Relation Linking (contains, references, uses, depends_on)
   │     └── Memory Entity Binding (Semantic facts, Procedural tools)
   │
   ├── [Relational Graph Storage]
   │     ├── KnowledgeNodeModel: (id, user_id, label, node_type, properties, document_id, memory_id)
   │     └── KnowledgeEdgeModel: (id, user_id, source_node_id, target_node_id, relation_type, weight, properties)
   │
   ├── [Dual-Dialect Recursive Traversal Engine]
   │     ├── Cycle Prevention: Path string tracking (`~cte.c.path.like('%,node,%')`)
   │     ├── Depth Bounded: Explicit depth ceiling (`depth <= 3`)
   │     ├── Bidirectional Traversal: Incoming + Outgoing edge resolution
   │     ├── Neighborhood Subgraphs: k-hop expansion around center entity
   │     └── Shortest Path Traversal: Path reconstruction with minimal edge weight
   │
   ├── [Hybrid Graph-RAG Retrieval]
   │     ├── Vector Semantic Retrieval (Document chunks & memories)
   │     ├── Entity Token Matching & Graph Expansion
   │     ├── Relational Triples Extraction: [Subject] --(relation)--> [Object]
   │     └── Synthesis Context Enrichment with Structured Knowledge Triples
   │
   └── [Interactive SVG Graph Cockpit]
         ├── Smooth Euler Force Simulation (Damped velocity & alpha cooling)
         ├── Clean Animation Frame Cancellation (`cancelAnimationFrame`)
         ├── Type-Themed Nodes & Directed Relation Arrows
         └── Click-to-Inspect Drawer with 1-Click 2-Hop Neighborhood Expansion
```

---

## 9. Agent Orchestrator, Specialized Agents & Planning Architecture

```
User Goal / Autonomous Task Request
   │
   ├── [Orchestrator Agent] (Central Supervisor & Coordinator)
   │     ├── Ingests OS context, user preferences, and goal statement
   │     └── Delegates goal decomposition to PlanningAgent
   │
   ├── [Planning Agent] (Goal Decomposition & Recovery Replanner)
   │     ├── Structured Output Decomposer via ModelGateway: AgentPlan -> list[PlanStep]
   │     ├── Assigns specialized agents: "orchestrator", "planning", "research", "document"
   │     ├── Determines tool dependencies & DAG step order
   │     └── Failure Recovery: Generates localized recovery steps inheriting upstream dependencies
   │
   ├── [Relational Plan Storage]
   │     ├── ExecutionPlanModel: (id, task_id, user_id, goal, status, current_step_index, replan_count, max_replans)
   │     └── PlanStepModel: (id, plan_id, index, description, assigned_agent, dependencies, status, retries, result)
   │
   ├── [Step Scheduling & Execution Engine]
   │     ├── Explicit Dependency Resolution: Only proceeds if all dependency step IDs are 'completed'
   │     │     └── Downstream Skipping: Automatically marks steps 'skipped' if dependencies fail
   │     ├── Session & Transaction Hygiene: Commits/refreshes before and after external agent I/O boundaries
   │     ├── Dual-Point Cancellation: Checks task cancellation immediately BEFORE and AFTER step execution
   │     └── Retry Loop & Bounded Replan: Retries up to max_retries, replans up to max_replans (capped at 3)
   │
   ├── [Specialized Domain Agents]
   │     ├── ResearchAgent: Hybrid Vector + Knowledge Graph retrieval via RAGQueryEngine
   │     ├── DocumentAgent: Ingested document catalog and chunk metadata analysis
   │     └── OrchestratorAgent: Final structured synthesis of multi-step results
   │
   └── [Autonomous Execution Studio & Dashboard]
         ├── Live Agent Roster with status and capability badges
         ├── Autonomous Goal Execution Studio with real-time step checklist & message feed
         └── Dedicated Plan tab on /tasks showing structured execution steps
```

---

## 10. Policy Engine, Capability Registry & Trust Model Architecture

```
Agent Action Request (Tool Invocations / Shell Executions / Filesystem Ops)
   │
   ├── [Canonical Path Normalization]
   │     └── Resolves target path (`Path.resolve()`) to eliminate traversal vectors (`../`)
   │
   ├── [Capability Registry]
   │     ├── Static & Dynamic Catalog of System Capabilities
   │     └── Categorized by Action Type (READ, WRITE, MODIFY, DELETE, EXECUTE, EXTERNAL_ACTION)
   │     └── Baseline Risk Tiers (LOW, MEDIUM, HIGH, CRITICAL)
   │
   ├── [Policy Evaluation Pipeline]
   │     ├── Active User Permission Check (Resource pattern glob/fnmatch evaluation)
   │     ├── Atomic TOCTOU Grant Consumption: Consumes single-use grants inside isolated transaction
   │     ├── Risk Assessment: Automatically requires human-in-the-loop (HITL) approval for non-exempt actions
   │     └── Evaluation Verdict: ALLOWED | REQUIRES_APPROVAL | BLOCKED
   │
   ├── [Human-in-the-Loop Approval & Permission Scopes]
   │     ├── ApprovalRequestModel: (id, user_id, capability_name, affected_resources, risk_level, status, diff_preview)
   │     ├── Granular Scopes: ONE_TIME | SESSION (TTL-bound) | STANDING (strictly LOW-risk READ operations)
   │     └── Inline Expiration Validation: Evaluates timestamp at resolution time to prevent stale approvals
   │
   └── [Immutable Append-Only Audit Ledger]
         ├── Tamper-Resistant Ledger: Intercepts updates/deletions at SQLAlchemy ORM layer
         ├── Comprehensive Event Trail: Policy checks, approvals, revocations, and rollback actions
         └── Multi-dimensional Query Filtering: Filter by actor, tool, risk tier, status, or date
```

---

## 11. Reversible Actions, Side-Effect Journaling & Diff Approval Architecture

```
Mutating Action Pipeline (Phase 10)
   │
   ├── [Explicit Reversibility Labeling & Classification]
   │     ├── Reversible Actions: FILE_CREATE, FILE_MODIFY, FILE_DELETE, FILE_MOVE
   │     └── Non-Reversible Operations: COMMAND_EXECUTE, EXTERNAL_MUTATION, NETWORK_REQUEST
   │
   ├── [Pre-Execution State Capture & Filesystem Safeguards]
   │     ├── Safeguard 1: State Drift Detection
   │     │     └── Computes current target SHA-256 before rollback; aborts with HTTP 409 Conflict if drift detected
   │     ├── Safeguard 2: Size Limit & Binary Handling
   │     │     └── Enforces 1MB inline content cap (MAX_INLINE_SIZE); captures metadata/hashes for binary/oversized files
   │     └── Safeguard 3: Safe Directory Hierarchy Recreation
   │           └── Recursively recreates missing parent directories (`mkdir(parents=True, exist_ok=True)`) on restore
   │
   ├── [Unified Git-Style Diff Generation]
   │     ├── Git-style patch generation (`difflib.unified_diff`) showing exact lines added (+) and removed (-)
   │     └── Surfaced in human-in-the-loop approval modal before execution confirmation
   │
   ├── [Action Snapshot Storage (`action_snapshots`)]
   │     ├── Fields: id, user_id, task_id, step_id, capability_name, action_type, is_reversible
   │     ├── States: before_state (JSON), after_state (JSON), diff_patch (text), status (CAPTURED -> APPLIED -> REVERTED)
   │     └── Full Tenant Isolation: Query & rollback scoped strictly by authenticated user ID
   │
   ├── [Rollback Mechanics & Revert Execution]
   │     ├── `POST /api/v1/reversal/snapshots/{id}/revert`
   │     ├── Reverses mutations: deletes created files, restores modified files, recreates deleted hierarchies
   │     ├── Drift override: Supports explicit `force=True` parameter to bypass intermediate modification conflicts
   │     └── Append-Only Audit Logging: Registers `ACTION_REVERTED` event in immutable ledger
   │
   └── [Diff Approval & Rollback Cockpit UX]
         ├── Approvals Cockpit: Live diff preview and reversibility badge (`Reversible [Undo supported]` vs `Non-Reversible`)
         └── Audit Cockpit: Reversible Snapshots tab with interactive Revert Modal and one-click rollback trigger
```

---

## 12. Tool System, Controlled Computer Actions & OS Adapter Architecture

```
Agent Execution Request (e.g. PlanningStep with required_tools)
   │
   ├── [Tool Registry (`packages/shared/nexus_shared/tools/`)]
   │     ├── Central Tool Registry (`ToolRegistry` singleton)
   │     ├── Schema Reflection: Generates OpenAI-compatible function calling schemas (`get_schemas_for_llm()`)
   │     └── Registered Standard Tools:
   │           ├── Filesystem: `filesystem.read`, `filesystem.write`, `filesystem.modify`, `filesystem.delete`, `filesystem.list_dir`
   │           ├── Terminal: `terminal.execute` (allowlist-restricted subprocess runner)
   │           └── Applications: `applications.open`, `browser.open_url`
   │
   ├── [Unbypassable Tool Execution Pipeline (`BaseTool.execute()`)]
   │     ├── 1. Input Schema Validation (Pydantic v2 strict models)
   │     ├── 2. Policy Evaluation (PolicyEngine check on required capability & normalized target)
   │     │        └── If REQUIRES_APPROVAL: halts tool, registers ApprovalRequest, captures pre-snapshot diff
   │     ├── 3. Pre-execution State Capture (SnapshotManager for reversible operations)
   │     ├── 4. Controlled OS Execution (ComputerControlAdapter implementation)
   │     ├── 5. Post-execution Snapshot Finalization (after-state recording & diff patch generation)
   │     └── 6. Audit Logging (Immutable audit event recorded with duration & output metadata)
   │
   ├── [3 Mandatory Computer Action Safeguards]
   │     ├── Safeguard 1: Workspace / CWD Path Validation
   │     │     └── `is_protected_directory()` validates and normalizes `cwd`; denies execution if targeting
   │     │         `/`, `/etc`, `/var`, `/System`, `/private`, `/bin`, `/sbin`, `~/.ssh`, or `~/.gnupg`
   │     ├── Safeguard 2: Stdout/Stderr Buffer Caps
   │     │     └── Strict 100 KB buffer limit (`MAX_COMMAND_OUTPUT_BYTES = 100 * 1024`); truncates output
   │     │         and appends `\n[Output truncated at 100 KB]` to eliminate memory exhaustion & log bloat
   │     └── Safeguard 3: Resumable Step Metadata for Approvals
   │           └── When a tool halts with `REQUIRES_APPROVAL`, target tool name, arguments, and `approval_id`
   │               are cleanly serialized into `PlanStepModel.result_payload` and the step is paused in
   │               `awaiting_approval` state, resuming execution immediately upon approval resolution
   │
   ├── [OS Control Abstraction Layer (`packages/shared/nexus_shared/computer/`)]
   │     ├── `ComputerControlAdapter` ABC: Uniform interface for all OS-level actions
   │     ├── `MacOSAdapter`: Concrete implementation for macOS environments
   │     │     ├── Applications: `/usr/bin/open -a <app_name>` with sanitized name validation
   │     │     ├── Web Browser: `/usr/bin/open <url>` with strict HTTP/HTTPS scheme enforcement
   │     │     ├── Filesystem: Sandboxed, async file read/write/move/delete/list via aiofiles & pathlib
   │     │     └── Subprocess: Asynchronous process execution with timeouts and output stream capping
   │     └── `WindowsAdapter` & `LinuxAdapter`: Stubs raising typed `NotImplementedError`
   │
   ├── [ComputerAgent Integration]
   │     ├── Domain agent specialized for tool invocation and OS interactions
   │     ├── Dispatches plan steps through `ToolRegistry` with user database session
   │     └── Automatically propagates approval pauses to the Orchestrator DAG state machine
   │
   ├── [Backend REST API (`/api/v1/tools`)]
   │     ├── `GET /api/v1/tools`: List all registered tools with capability requirements & risk tiers
   │     ├── `GET /api/v1/tools/{name}`: Detailed tool manifest and parameter schemas
   │     └── `POST /api/v1/tools/{name}/execute`: Execute tool with authenticated user session & policy check
   │
    └── [Dashboard Tool Explorer (`/tools`)]
          ├── Live searchable catalog of available system tools
          ├── Capability badges, risk tiers, and reversibility indicators
          └── Interactive parameter inspection drawer with JSON Schema property documentation
```

---

## 13. Ambient Desktop Layer & Native HUD Architecture (Phase 12)

```
Native macOS Host Environment
   │
   ├── [Native Tauri Rust Core (`apps/ambient/src-tauri/`)]
   │     ├── Global Shortcut Manager: `CommandOrControl+Shift+Space` global toggle
   │     ├── Frameless, transparent floating capsule window centered in upper-third of screen
   │     ├── Non-Blocking Native Context Invocations:
   │     │     ├── `get_frontmost_app()`: Active app name + window title via AppleScript with 500ms timeout
   │     │     └── `get_selected_text()`: Explicit opt-in selection capture with privacy boundary
   │     └── Granular Escape & Dismissal Behavior:
   │           ├── Idle / Result: Immediately hides HUD window
   │           ├── Approval: Treats Escape as an explicit action denial with fallback
   │           └── Executing: Hides HUD window while background execution continues uninterrupted
   │
   ├── [Ambient HUD Frontend (`apps/ambient/src/`)]
   │     ├── CommandCapsule: Raycast/Spotlight inspired unified natural-language search & prompt bar
   │     ├── ContextPill: Displays active app name, window title, and selection state with attach toggle
   │     ├── Dynamic State Views:
   │     │     ├── PlanningView: Real-time checklist of DAG steps decomposed by PlanningAgent
   │     │     ├── ToolActivityPulse: Glowing pulse indicator of running tool execution
   │     │     ├── InlineApprovalModal: Inline diff preview with keyboard-accessible [Approve Once] / [Deny]
   │     │     └── ResultView: Formatted markdown output, copy action (Cmd+Enter), follow-up prompt
   │     └── Webview Transparency & Styling Invariants:
   │           └── Strict transparent background on html, body, and #root with soft shadow padding
   │
   ├── [Real-Time Streaming Bridge]
   │     ├── WebSocket: Live connection to `/ws/nexus?client_surface=ambient`
   │     ├── REST API: Task dispatch tagged with `X-Client-Surface: ambient` header
   │     └── Full Synchronization: Actions stream to central Task DAG and immutable Audit Ledger
   │
   └── [System Status & Surface Discovery (`/api/v1/system/status`)]
         └── Reports `phase: "phase_12_ambient_desktop"` and `supported_surfaces: ["dashboard", "ambient"]`
```
