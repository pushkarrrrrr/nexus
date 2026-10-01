# NEXUS: Agentic AI Operating System

<div align="center">

```
  _   _   ______  __   __  _    _    _____ 
 | \ | | |  ____| \ \ / / | |  | |  / ____|
 |  \| | | |__     \ V /  | |  | | | (___  
 | . ` | |  __|     > <   | |  | |  \___ \ 
 | |\  | | |____   / . \  | |__| |  ____) |
 |_| \_| |______| /_/ \_\  \____/  |_____/ 
```

**An autonomous, multi-agent operating system designed for verifiable control, safety, reversibility, and deep OS integration.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-000000.svg?logo=next.js&logoColor=white)](https://nextjs.org)
[![Tauri 1.5](https://img.shields.io/badge/Tauri-Desktop-24C8DB.svg?logo=tauri&logoColor=white)](https://tauri.app)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.4-3178C6.svg?logo=typescript&logoColor=white)](https://typescriptlang.org)
[![Tests Passing](https://img.shields.io/badge/Tests-194%20Passing-brightgreen.svg)]()
[![Ruff Formatted](https://img.shields.io/badge/Code%20Style-Ruff-black.svg)](https://github.com/astral-sh/ruff)

[Overview](#-overview) • [Interaction Surfaces](#-two-interaction-surfaces) • [Architecture](#-system-architecture) • [Core Subsystems](#-core-subsystems) • [Security & Policy](#-security--the-trust-model) • [Quickstart](#-quickstart) • [Project Structure](#-project-structure) • [Testing & Quality](#-testing--quality-gates)

</div>

---

## 🌟 Overview

**NEXUS** is not a simple chatbot or a prompt wrapper. It is a full-fledged **Agentic AI Operating System** that bridges high-level user intent with controlled, observable, and reversible computer execution.

Whether performing autonomous multi-step software engineering tasks, orchestrating external tools, monitoring system telemetry, or manipulating desktop applications, NEXUS guarantees that:
- **No execution path bypasses the Policy Engine.**
- **High-risk and mutating actions require explicit Human-in-the-Loop (HITL) approval.**
- **All filesystem mutations generate git-style unified diffs and pre-execution snapshots for 1-click rollback.**
- **Every decision, tool run, and token cost is permanently recorded in an append-only audit ledger.**

---

## 🖥️ Two Interaction Surfaces

NEXUS provides two complementary interfaces connected to the exact same underlying agentic engine:

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
                   │                  FASTAPI CORE ENGINE                   │
                   └────────────────────────────────────────────────────────┘
```

### 1. NEXUS Dashboard (`apps/dashboard`)
The deep analytical cockpit built on Next.js 14, Tailwind CSS, and Lucide icons:
* **Interactive Task DAG Visualizer**: Real-time rendering of task dependency graphs, execution status, and subtask trees.
* **Knowledge & Entity Graph Explorer**: Dynamic force-directed SVG graph displaying entity nodes, semantic relationships, and 2-hop neighborhood expansion.
* **Audit Ledger & Rollback Cockpit**: Immutable record of all system events with live unified diff previews and 1-click state reversion.
* **Proactive Watchers & Triggers Cockpit**: Live CPU, memory, and disk telemetry with custom threshold rules and anomaly feeds.
* **Integrations Hub**: Connectivity management for persistent browser sessions, GitHub API, Google Workspace, and native macOS Accessibility controls.
* **Memory Studio**: Inspector for Working, Conversational, Episodic, Semantic, and Procedural memory records.

### 2. NEXUS Ambient Layer (`apps/ambient`)
A native, lightweight desktop HUD powered by Tauri (Rust core) and Vite/React:
* **Global Shortcut Summon**: Toggle anywhere instantly using `Cmd/Ctrl + Shift + Space`.
* **Voice Orb & Audio Waveforms**: Interactive voice mode with animated particle visualizers and instant transcription dispatch.
* **Context Awareness**: Non-blocking extraction of active frontmost applications and opt-in text selection on macOS.
* **Inline HITL Approval Modals**: Immediate keyboard-accessible diff inspection (`Approve Once`, `Approve Session`, `Deny`) without switching context.
* **Floating Anomaly Pills**: Real-time notification badges for proactive threshold triggers and warnings.

---

## 🏛️ System Architecture

NEXUS enforces strict system boundaries across its monorepo:

```
User Request (Dashboard / Ambient HUD / Voice)
      │
      ▼
Intent & Context Analysis
      │
      ▼
Memory & Knowledge Retrieval (5 Taxonomies + Hybrid Graph-RAG)
      │
      ▼
Task Planning (Structured DAG Synthesis via PlanningAgent)
      │
      ▼
Agent & Tool Selection (Orchestrator, Research, Document, Computer)
      │
      ▼
Policy Evaluation (LOW, MEDIUM, HIGH, CRITICAL Risk Tiers)
      │
      ▼
Permission Verification ──► [HITL Approval Required?] ──► User Approval Modal (Diff Preview)
      │                                                               │
      ▼ (Authorized)                                                 ▼ (Approved)
Controlled Execution & Snapshots
  ├── ComputerControlAdapter (Sandboxed terminal, file operations)
  ├── Playwright Browser Engine (Persistent sessions, SSRF isolation)
  └── Native macOS JXA / CoreGraphics Accessibility Engine
      │
      ▼
Result Observation & Dynamic Replanning (Self-Correction & DAG Patching)
      │
      ▼
State Snapshot & Immutable Audit Ledger
      │
      ▼
Real-Time Stream via WebSockets (Dashboard DAG + Ambient HUD)
```

---

## ⚡ Core Subsystems

### 1. Multi-Provider AI Gateway (`packages/shared/nexus_shared/ai`)
* **Unified Abstraction**: Seamless interchangeability across **OpenAI** (`gpt-4o`, `o1`), **Anthropic** (`claude-3-5-sonnet`), **Google Gemini** (`gemini-1.5-pro`, `gemini-2.0-flash`), and local **Ollama** models.
* **Structured Output Guarantee**: Native Pydantic v2 schema enforcement with JSON mode validation and automatic retries.
* **Token & Cost Ledger**: Real-time per-step input/output token metering with provider pricing calculation.

### 2. Autonomous Task Planning & Self-Correction (`packages/shared/nexus_shared/agents`)
* **Specialized Domain Agents**:
  * `OrchestratorAgent`: Supervisor decomposing high-level user goals into structured dependency graphs.
  * `PlanningAgent`: DAG task synthesis, dependency resolution, and dynamic replanning.
  * `ResearchAgent`: Hybrid retrieval combining vector similarity with relational graph traversal.
  * `DocumentAgent`: Multi-format parsing (PDF, Markdown, CSV, JSON, TXT) and positional chunking.
  * `ComputerAgent`: Sandboxed OS execution and desktop automation.
* **Autonomous Error Recovery & DAG Patching**:
  * `ErrorClassifier`: Classifies step failures into deterministic error classes (`TIMEOUT`, `SYNTAX_ERROR`, `COMMAND_NOT_FOUND`, `PERMISSION_DENIED`, etc.).
  * `SelfCorrectionReflector`: Diagnoses root causes and generates targeted recovery step proposals.
  * `DAGPatcher`: Dynamically splices recovery steps into active plans while preserving upstream dependency links.
  * **Bounded Replanning**: Strictly capped replan attempts to prevent runaway execution loops.

### 3. Memory & Personal Knowledge Base (`packages/shared/nexus_shared/memory`)
* **5-Class Memory Taxonomy**:
  1. **Working Memory**: Task-scoped volatile execution scratchpad.
  2. **Conversational Memory**: Sliding-window dialogue context.
  3. **Episodic Memory**: Task outcome retrospectives and lessons learned.
  4. **Semantic Memory**: Permanent facts, identity traits, and user preferences.
  5. **Procedural Memory**: Reusable tool recipes and user-specific workflows.
* **Dual-Mode Vector Store**: Native PostgreSQL `pgvector` for production deployments, with automatic zero-configuration SQLite normalized cosine dot-product fallback for local development.

### 4. Knowledge Graph & Relational Traversal (`packages/shared/nexus_shared/knowledge`)
* Relational node and edge modeling with typed entities and directed connections (`contains`, `uses`, `depends_on`, `references`).
* Dual-dialect recursive CTE traversal with cycle detection and depth boundaries (`depth <= 3`).
* Interactive SVG force-directed Euler physics simulation with real-time neighborhood inspection.

### 5. Reversible Actions & Side-Effect Journaling (`packages/shared/nexus_shared/reversal`)
* **Pre-Execution Snapshots**: File captures taken prior to any mutating tool operation (`FILE_CREATE`, `FILE_MODIFY`, `FILE_DELETE`, `FILE_MOVE`).
* **Git-Style Unified Diffs**: Diffs generated and displayed in HITL approval modals before execution.
* **State Drift Detection**: Target files checked against pre-execution SHA-256 hashes prior to rollback; conflicts halt reversion unless overridden with `force=true`.
* **1-Click Rollback**: Reverses mutations cleanly, recreates directory trees, and records rollback actions in the audit ledger.

### 6. Proactive Watchers & Event Triggers (`packages/shared/nexus_shared/proactive`)
* **SystemWatcher**: Zero external binary dependencies—collects native CPU load averages, macOS `sysctl` / POSIX `sysconf` memory statistics, and disk capacity.
* **TriggerEvaluator**: Evaluates numeric thresholds (`CPU > 90%`), recurring intervals, and filesystem change rules with cooldown throttling.
* **RemediationCoordinator**: Enforces policy invariants: low-risk observations execute automatically, while high-risk mutating remedies require immediate user approval.

### 7. Controlled OS & Browser Automation (`packages/shared/nexus_shared/computer`)
* **Subprocess Sandboxing**: CWD validation blocking protected paths (`/`, `/etc`, `/System`, `~/.ssh`, `~/.gnupg`), command allowlisting, execution timeouts, and 100 KB output stream buffer caps.
* **Persistent Browser Sessions**: Playwright-driven Chromium engine retaining authenticated logins (`~/.nexus/browser_profiles`) with strict SSRF defense (blocking loopback, RFC 1918 addresses, and AWS/GCP metadata endpoints).
* **Native macOS Control**: Pure Python `ctypes` bindings for macOS TCC Accessibility checks (`AXIsProcessTrusted`), JXA UI element traversal, and Quartz `CGEvent` synthesis.

---

## 🔒 Security & The Trust Model

NEXUS is built under the non-negotiable constitution defined in [`AGENTS.md`](./AGENTS.md):

| Risk Level | Policy Verification | Examples | Approval Requirement |
|---|---|---|---|
| **LOW** | Read-only inspection, calculations, knowledge queries | `filesystem.read`, `watcher.get_system_metrics`, `github.list_issues` | Auto-authorized (or session-cached) |
| **MEDIUM** | Non-destructive modifications, testing, local scripts | `terminal.execute` (safe commands), `filesystem.write` (temp paths) | Session grant or standard prompt |
| **HIGH** | Mutating workspace files, browser actions, desktop interaction | `filesystem.modify`, `browser.click`, `macos.click_element`, `remediation.execute_fix` | **Mandatory HITL Approval with Diff** |
| **CRITICAL** | Irreversible changes, credentials, destructive OS operations | Dropping databases, security elevation, external financial actions | **Mandatory Direct Confirmation; Never Cached** |

Every action passes through:
```
LLM Request ──► Pydantic Validation ──► Policy Evaluation ──► Snapshot Capture ──► Execution ──► Audit Ledger
```

---

## 🚀 Quickstart

### Prerequisites
* **Python**: 3.11 or higher
* **Node.js**: v18 or v20+ (with `npm`)
* **Rust & Cargo**: (Optional, required only for compiling the native Tauri desktop HUD)
* **PostgreSQL & Redis**: (Optional, SQLite and in-process queues are used by default)

### 1. Clone the Repository
```bash
git clone https://github.com/pushkarrrrrr/nexus.git
cd nexus
```

### 2. Python Backend Setup
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies in editable mode
pip install -e ".[dev]"
```

### 3. Frontend & Monorepo Setup
```bash
# Install workspace dependencies
npm install
```

### 4. Configure Environment
```bash
cp .env.example .env
```
Open `.env` and set your preferred AI provider API key:
```ini
DEFAULT_AI_PROVIDER=gemini # or openai, anthropic, ollama
GEMINI_API_KEY=your_gemini_api_key_here
# OPENAI_API_KEY=your_openai_api_key_here
# ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

### 5. Initialize Database Migrations
```bash
alembic -c infra/database/alembic.ini upgrade head
```

### 6. Launch NEXUS
Start the full stack with the all-in-one development script:
```bash
./scripts/dev.sh
```

Or start individual services manually:
```bash
# FastAPI Core Engine (Port 8000)
uvicorn services.api.nexus_api.main:app --host 0.0.0.0 --port 8000 --reload

# Next.js Web Dashboard (Port 3000)
npm run dev:dashboard

# Ambient HUD Webview (Port 5173)
npm run dev:ambient

# Ambient Desktop Native HUD (Tauri)
npm run dev:tauri
```

Once running:
* **Web Dashboard**: [http://localhost:3000](http://localhost:3000)
* **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **API Health Check**: [http://localhost:8000/health](http://localhost:8000/health)
* **Ambient Shell**: [http://localhost:5173](http://localhost:5173)

---

## 📂 Project Structure

```text
nexus/
├── apps/
│   ├── dashboard/             # Next.js 14 Web Cockpit (DAG, Knowledge, Triggers, Audit)
│   └── ambient/               # Tauri 1.5 + React Desktop HUD (Spotlight / Raycast model)
│       └── src-tauri/         # Native Rust core (Global shortcut, macOS windowing)
│
├── services/
│   ├── api/                   # FastAPI async core, WebSocket bus, REST routers
│   │   ├── nexus_api/         # Application entrypoints, auth, middleware
│   │   └── tests/             # Comprehensive pytest test suite (194+ tests)
│   └── worker/                # Background async task queue processor
│
├── packages/
│   ├── shared/                # Core domain implementations
│   │   └── nexus_shared/
│   │       ├── agents/        # Orchestrator, Planning, Research, Self-Correction
│   │       ├── ai/            # Multi-model AI Gateway & pricing calculators
│   │       ├── audit/         # Immutable append-only audit ledger
│   │       ├── computer/      # OS control adapters (MacOSAdapter, CWD guards)
│   │       ├── integrations/  # Playwright browser, GitHub, Google, macOS JXA
│   │       ├── knowledge/     # Document ingestion, chunking, Graph-RAG
│   │       ├── memory/        # 5-class memory taxonomy & vector retrieval
│   │       ├── policy/        # Policy Engine, Capability Registry, HITL locks
│   │       ├── proactive/     # SystemWatcher, TriggerEvaluator, Engine
│   │       ├── reversal/      # SnapshotManager, diff generation, rollback
│   │       └── tools/         # Standard sandboxed tool definitions & registry
│   ├── types/                 # Shared TypeScript types & Python Pydantic v2 schemas
│   └── config/                # Centralized environment settings
│
├── infra/
│   └── database/              # Alembic database migrations (dual PG / SQLite)
├── docs/                      # ARCHITECTURE.md, STATUS.md, Phase specs
├── scripts/                   # dev.sh, test.sh, lint.sh, migrate.sh
├── AGENTS.md                  # NEXUS Engineering Constitution & Invariants
├── package.json               # Monorepo workspaces definition
└── pyproject.toml             # Python packaging, ruff, mypy, pytest config
```

---

## 🧪 Testing & Quality Gates

NEXUS enforces uncompromising engineering rigor across every layer:

```bash
# Run the complete test suite (194 tests)
.venv/bin/pytest -v

# Run backend static type checking
.venv/bin/mypy services/api packages/shared packages/types packages/config

# Run frontend static type checking across all workspaces
npm run typecheck

# Code formatting & lint checks
.venv/bin/ruff check .
.venv/bin/ruff format --check .
npm run lint
```

---

## 📜 Development Constitution

All contributions to NEXUS must comply with the rules outlined in [`AGENTS.md`](./AGENTS.md):
1. **Never bypass policy checks or the audit ledger.**
2. **Never swallow errors silently.**
3. **No fake or mock production implementations.**
4. **Preserve tenant isolation across all database queries.**
5. **Always provide pre-execution snapshots and diffs for mutating filesystem actions.**

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
