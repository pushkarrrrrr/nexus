# AGENTS.md — NEXUS Engineering Rules & Development Constitution

This document establishes the binding operational rules for all AI and human engineers working on the **NEXUS Agentic AI Operating System**.

---

## 1. Non-Negotiable Product Principles

NEXUS must **NOT** be:
1. A ChatGPT clone or prompt-to-LLM wrapper.
2. Merely a web dashboard with mock data.
3. A fake computer-control demo relying on hardcoded scripts.
4. A loose collection of disconnected AI features.
5. An application where an AI agent has unrestricted operating system authority.
6. An application that silently performs sensitive, destructive, or external actions.

NEXUS **MUST** be:
1. **Modular**: Strict system boundaries, decoupled micro-packages, and swappable adapters.
2. **Observable**: Full distributed tracing, structured logging, token/latency metrics, and event streaming.
3. **Testable**: Unit tests alongside all business logic; integration tests for every tool and agent pipeline.
4. **Secure by Design**: Principle of least privilege; explicit policy gating on every action.
5. **Permission-Aware**: Granular risk tiers (LOW, MEDIUM, HIGH, CRITICAL) and session-aware permission caching.
6. **Auditable**: Immutable append-only audit ledger recording every intent, input, policy verdict, and output.
7. **Reversible**: Automated pre-execution state snapshots and registered undo handlers for all mutating file/system operations.
8. **Model-Provider Agnostic**: Unified AI Gateway supporting OpenAI, Anthropic, Gemini, and Local/Ollama via common abstractions.
9. **Tool-Provider Agnostic**: Standardized registry with strict JSON Schema input/output definitions.
10. **Academic & Production Grade**: Built with clean research methodology, formal ablation test harnesses, and real-world deployment viability.

---

## 2. Core Execution Pipeline

Every agentic request must strictly follow this unbypassable pipeline:
```
User Request (Dashboard / Ambient)
  ├──► Intent & Context Analysis
  ├──► Memory & Knowledge Retrieval (Working, Episodic, Semantic/RAG)
  ├──► Task Planning (Topological DAG Synthesis)
  ├──► Agent & Tool Selection
  ├──► Policy Evaluation (Action Type + Risk Level Classification)
  ├──► Permission Check (Grants Cache)
  ├──► Human-in-the-Loop (HITL) Approval (if required; diff-based preview)
  ├──► Controlled Execution (ComputerControlAdapter / Sandboxed Runners)
  ├──► Result Observation
  ├──► Task State & DAG Update
  ├──► Memory & Audit Ledger Update (Snapshots + Undo Handlers)
  └──► User Response (Streamed tokens + Activity Feed)
```
**RULE**: Never bypass the Policy Engine, Tool Registry, or Audit Ledger for convenience.

---

## 3. Engineering & Development Rules

### Architecture & Boundaries
- Maintain strict boundary separation across `apps/`, `services/`, `packages/`, and `infra/`.
- Do not import service-internal code directly into frontends; communicate exclusively via typed REST/WebSocket schemas defined in `packages/types`.
- Never hardcode model names, API keys, or provider-specific parameters in agent logic. Use configuration profiles from `packages/config`.

### Code Quality & Safety
- **No Silent Error Swallowing**: Always catch specific exceptions, log structured error context, and report failure reasons up to the Orchestrator.
- **Strict Typing**: Python must pass `mypy` / `pyright` checks with complete Pydantic v2 schemas; TypeScript must pass `tsc --noEmit` with `strict: true`.
- **Zero Fake Implementations**: Do not return mock strings or placeholder fixtures in production paths. If a subsystem is not yet implemented, return an explicit `NotImplementedError` or typed pending status.
- **Sanitized Shell Access**: Never expose raw unvalidated `bash -c` strings to LLMs. All terminal tools must pass through strict command parsing, cwd verification, and the `PolicyEngine`.
- **Pre-execution Snapshotting**: Any tool mutating files or system state must take a content snapshot before execution and register an idempotent rollback handler with the Audit Engine.

### Secrets & Environment
- Never commit `.env` files, API keys, certificates, or tokens.
- All configuration keys must be declared in `.env.example` with clear documentation.

---

## 4. Phase Completion Gate

At the conclusion of **EVERY** phase, before proceeding:
1. Run linting (`ruff check`, `eslint`).
2. Run type checking (`mypy`, `tsc --noEmit`).
3. Run unit and integration tests (`pytest`, `npm test`).
4. Build all affected applications.
5. Verify UI in the browser or desktop runtime where applicable.
6. Update `docs/STATUS.md` with:
   - Completed features and artifacts
   - Known limitations and trade-offs
   - Prerequisites for the subsequent phase
7. Update `docs/ARCHITECTURE.md` if any interface, schema, or system topology has evolved.
8. **DO NOT START THE NEXT PHASE AUTOMATICALLY**. Explicitly stop, present the phase deliverables to the user, and await review and approval.
