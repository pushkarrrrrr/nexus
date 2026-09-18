# NEXUS Product Specification

## 1. Product Vision
**NEXUS** is an AI-native operating layer that allows users to interact with their personal computer through natural language. It maintains persistent multi-tiered memory, retrieves personal knowledge, plans complex multi-step tasks as Directed Acyclic Graphs (DAGs), and executes controlled actions via a sandboxed tool layer governed by an explicit permission and safety policy.

NEXUS bridges the gap between conversational AI and operating system capabilities without ever sacrificing security, transparency, or user control.

---

## 2. Target Personas
- **The Software Engineer**: Uses NEXUS to navigate unfamiliar codebases, run builds, execute test suites, apply complex refactoring diffs, and automate terminal workflows with zero fear of accidental destructive commands.
- **The Academic Researcher**: Uses NEXUS to index papers, synthesize notes, trace citations across local PDFs, and evaluate autonomous task planning pipelines against standard benchmarks.
- **The Power User**: Interacts via a global keyboard shortcut to triage notifications, manage local files, orchestrate browser searches, and inspect detailed audit trails of system interactions.

---

## 3. Scoping: MVP Scope vs. Future Capabilities

To prevent architectural drift and scope creep during the 4th-year capstone development cycle, functionality is strictly partitioned:

| Feature Area | In-Scope for Initial MVP | Deferred to Future Phases |
|---|---|---|
| **Client Surfaces** | - Next.js Web Dashboard (Chat, DAGs, Approvals, Audit)<br>- Tauri Desktop Overlay (Global Hotkey, Spotlight Bar, Quick Approvals) | - Mobile Companion App<br>- Voice/Audio Dictation & Wake Word<br>- System Tray Menus |
| **Orchestration** | - Multi-Agent DAG Planner<br>- ReAct Observe-Think-Act Loop<br>- Specialized Agents (Orchestrator, Coder, System, Research) | - Autonomous background self-prompting loops<br>- Dynamic code synthesis executing outside tools |
| **Tool Execution** | - `filesystem.*` (read, write, modify, delete with diffs)<br>- `terminal.*` (command allowlist, timeout guards, cwd limits)<br>- `browser.*` (Playwright headless navigation, extract text) | - Direct arbitrary mouse coordinate clicking<br>- Real-time computer vision screen navigation<br>- Unrestricted shell escape hatches |
| **Safety & Policy** | - 4-Tier Risk Matrix (LOW, MEDIUM, HIGH, CRITICAL)<br>- Diff-based visual approval modal<br>- Session-scoped permission caching<br>- Hardcoded forbidden dangerous commands (`rm -rf /`, etc.) | - Hardware token / WebAuthn approval gates<br>- Multi-user RBAC role hierarchies<br>- Financial / payment gateway interactions |
| **Audit & Undo** | - Local SQLite/Postgres append-only audit ledger<br>- Pre-execution file snapshots & SHA-256 tracking<br>- 1-click file mutation rollback | - Reversing external network API calls<br>- Full OS filesystem checkpoint restore (APFS snapshots) |
| **Memory & Knowledge** | - 5-Class Memory taxonomy (Working, Conversational, Episodic, Semantic, Procedural)<br>- Local vector search (Chroma / LanceDB) over user-selected folders | - Continuous background desktop video/audio indexing<br>- Distributed cloud vector indexing |
| **OS Support** | - macOS (Native POSIX + AppleScript/JXA integration) | - Windows & Linux full adapter parity |

---

## 4. User Journeys & Interaction Flows

### Flow A: In-Flow Ambient Task
1. User presses `Cmd+Shift+Space` over any application.
2. Floating glassmorphic command capsule emerges over active screen.
3. User types: *"Check for uncommitted git changes in this project and run the tests."*
4. Ambient HUD detects active directory context from the user's terminal/editor.
5. Orchestrator generates a 2-step plan: `terminal.execute("git status")` and `terminal.execute("pytest")`.
6. Policy classifies `git status` as LOW (auto-allowed) and `pytest` as MEDIUM (auto-allowed for read/test execution).
7. Ambient HUD displays live progress indicators and test results in place, then auto-collapses or stays pinned on user command.

### Flow B: Destructive Mutation with Diff Approval
1. User asks NEXUS to refactor an existing Python module.
2. Orchestrator routes task to `CodingAgent`.
3. Agent analyzes source files and prepares a modified file payload.
4. Policy Engine intercepts `filesystem.modify`, identifies risk as `MEDIUM/HIGH`, captures a snapshot of the original file, and generates a unified diff.
5. Approval Modal surfaces on the Dashboard and Ambient HUD:
   - File: `services/api/routes.py`
   - Unified Diff: Green (+ additions) / Red (- deletions)
   - Risk: MEDIUM
   - Reason: "Refactor database session dependency injection"
6. User clicks `[Approve Once]`.
7. Policy Engine executes the modification, logs the action in the Audit Ledger, and updates the task state.
8. If the user notices an issue later, they open the Audit Log on the Dashboard and click `[Undo]`, which immediately restores the pre-execution snapshot.

---

## 5. Non-Functional Requirements
- **Latency**: Ambient summon overlay renders in `< 100ms`. Tool policy checks evaluate in `< 10ms`.
- **Security**: Zero remote code execution vulnerabilities; strictly sandboxed terminal execution; no cleartext credentials stored.
- **Reliability**: All tasks are restartable and maintain consistent state in the local SQLite/Postgres database.
- **Portability**: Monorepo runnable with a single command (`npm run dev` / `docker compose up`).
