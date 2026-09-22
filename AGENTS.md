# AGENTS.md — NEXUS Engineering Rules & Development Constitution

This document establishes the binding operational rules for all AI and human engineers working on the **NEXUS Agentic AI Operating System**.

These rules apply to autonomous agents, sub-agents, coding assistants, and human contributors.

---

# 1. Mission

NEXUS is an **Agentic AI Operating System**, not merely an AI chatbot.

NEXUS provides two primary interaction surfaces:

1. **NEXUS Dashboard** — full visibility, configuration, task management, memory, permissions, tools, activity, and system administration.
2. **NEXUS Ambient Layer** — fast contextual interaction through a summonable interface inspired by systems such as Spotlight, Raycast, and Siri.

Both surfaces must ultimately interact with the same underlying agentic execution infrastructure.

The system must prioritize:

* user control
* safety
* observability
* reversibility
* modularity
* provider independence
* measurable engineering quality

---

# 2. Non-Negotiable Product Principles

NEXUS MUST NOT become:

1. A ChatGPT clone or prompt-to-LLM wrapper.
2. Merely a web dashboard containing mock data.
3. A fake computer-control demo relying on hardcoded scripts.
4. A loose collection of disconnected AI features.
5. An AI agent with unrestricted operating-system authority.
6. A system that silently performs sensitive, destructive, financial, communication, or external actions.
7. A system where policy controls can be bypassed by alternate execution paths.

NEXUS MUST be:

### 2.1 Modular

Maintain strict system boundaries.

Use decoupled packages and adapters.

Core capabilities must be replaceable without rewriting the entire system.

---

### 2.2 Observable

Agent execution must be observable through:

* structured logs
* distributed tracing
* task events
* token usage
* latency
* model/provider metadata
* tool execution metadata
* policy decisions
* errors
* user approvals
* execution outcomes

Sensitive information must not be logged unnecessarily.

---

### 2.3 Testable

Business logic must have unit tests.

Important subsystem boundaries must have integration tests.

Critical end-to-end user flows must have E2E coverage.

Agent behavior should be tested using deterministic fixtures, mocked providers where appropriate, and real-provider evaluation where required.

---

### 2.4 Secure by Design

Use the principle of least privilege.

Every external action must pass through an explicit policy boundary.

No subsystem may silently escalate its privileges.

---

### 2.5 Permission-Aware

Actions must have explicit risk classifications:

* LOW
* MEDIUM
* HIGH
* CRITICAL

Permission decisions must consider:

* action type
* target resource
* current session
* user grants
* authentication state
* policy configuration
* contextual risk

Permission caching must have explicit scope and expiration.

Never treat a cached permission as permanent authorization.

---

### 2.6 Auditable

Record important agentic operations in an append-only audit system.

Audit records should capture, where applicable:

* user intent
* normalized request
* relevant context references
* plan
* selected tools
* policy verdict
* permission decision
* approval event
* execution result
* errors
* rollback/snapshot references

Never store secrets merely for the sake of auditability.

Audit records must be tamper-resistant.

---

### 2.7 Reversible

Mutating operations must have an appropriate recovery strategy.

For operations capable of changing user files or system state:

1. capture the required pre-execution state
2. register rollback/undo metadata
3. execute the operation
4. record the result
5. expose recovery where technically possible

Not every operation requires a full snapshot.

Snapshot requirements must be determined by the mutation's risk and reversibility.

---

### 2.8 Model-Provider Agnostic

The AI Gateway must provide common abstractions for:

* OpenAI
* Anthropic
* Gemini
* Local/Ollama
* future providers

Agent logic must never depend directly on provider-specific SDK behavior when a common abstraction exists.

Provider-specific capabilities must live behind adapters.

Never hardcode:

* API keys
* model credentials
* provider secrets

Model selection must come from configuration.

---

### 2.9 Tool-Provider Agnostic

Tools must be registered through a standardized tool registry.

Every tool must define:

* unique identifier
* description
* input schema
* output schema
* permissions
* risk level
* execution adapter
* timeout
* error behavior
* reversibility characteristics

JSON Schema or equivalent strongly typed contracts must be used.

---

### 2.10 Academic & Production Grade

NEXUS must support both:

**Engineering evaluation**

and

**real-world deployment.**

Research-oriented experimentation must be reproducible.

Where appropriate, provide:

* evaluation datasets
* experiment configurations
* baseline comparisons
* ablation experiments
* latency measurements
* cost measurements
* success-rate measurements
* failure analysis

Do not claim research conclusions without measurable evidence.

---

# 3. Core Agent Execution Pipeline

Every agentic request MUST pass through the following conceptual pipeline:

```text
User Request
    │
    ├── Dashboard
    └── Ambient Layer
            │
            ▼
Intent & Context Analysis
            │
            ▼
Memory & Knowledge Retrieval
    ├── Working Memory
    ├── Episodic Memory
    └── Semantic / RAG
            │
            ▼
Task Planning
    └── DAG / dependency synthesis
            │
            ▼
Agent & Tool Selection
            │
            ▼
Policy Evaluation
    └── Action + Risk Classification
            │
            ▼
Permission Check
    └── Session Grant / Explicit Grant
            │
            ▼
Human-in-the-Loop Approval
    └── Required for configured risk classes
            │
            ▼
Controlled Execution
    ├── ComputerControlAdapter
    ├── Sandboxed Runners
    └── External Service Adapters
            │
            ▼
Result Observation
            │
            ▼
Task / DAG State Update
            │
            ▼
Memory + Audit Update
    ├── State Snapshot
    ├── Undo Metadata
    └── Execution Record
            │
            ▼
User Response
    ├── Streamed response
    └── Activity feed
```

## Absolute Rule

No execution path may bypass:

* Policy Engine
* Tool Registry
* Permission System
* Audit System

unless that path is explicitly designated as a non-agentic internal operation.

Internal maintenance operations must still follow the security model appropriate to their privilege level.

---

# 4. Risk Classification

Every executable tool must declare a risk level.

## LOW

Examples:

* read public information
* inspect project files
* calculate values
* search indexed knowledge

Usually no explicit approval required.

---

## MEDIUM

Examples:

* create files
* modify non-critical project files
* install a dependency
* perform external API requests

May require session approval depending on configuration.

---

## HIGH

Examples:

* modifying important user files
* sending external messages
* modifying production resources
* executing privileged operations
* changing security-sensitive configuration

Require explicit user approval unless the user has explicitly configured an appropriate persistent grant.

---

## CRITICAL

Examples:

* destructive system operations
* deleting important data
* financial transactions
* irreversible external actions
* privilege escalation
* security-sensitive operations

Require explicit confirmation immediately before execution.

CRITICAL actions must never rely solely on an old cached permission.

---

# 5. Engineering Architecture

Maintain strict separation across:

```text
apps/
services/
packages/
infra/
```

A recommended topology is:

```text
apps/
├── web/
└── ambient/

services/
├── orchestrator/
├── ai-gateway/
├── memory/
├── policy/
├── tools/
├── audit/
├── execution/
└── observability/

packages/
├── types/
├── config/
├── schemas/
├── ui/
├── logger/
└── sdk/

infra/
├── database/
├── queues/
├── observability/
└── deployment/
```

This is a target architecture.

Do NOT reorganize the existing repository merely to match this structure.

Migration toward this topology must occur incrementally and only when justified.

---

# 6. Boundary Rules

Frontend applications MUST NOT import service-internal implementation code.

Communication between applications and services must use explicit contracts such as:

* typed REST
* WebSocket
* event streams
* approved RPC mechanisms

Shared contracts belong in:

```text
packages/types
packages/schemas
```

Never expose private service internals through shared packages.

---

# 7. Configuration

Provider and environment configuration must be centralized.

Use:

```text
packages/config
```

and environment variables.

Never hardcode:

* API keys
* access tokens
* database passwords
* model credentials
* private certificates

Model/provider selection must be configurable.

Provider-specific configuration must not leak into generic agent logic.

---

# 8. Code Quality

## 8.1 Error Handling

No silent error swallowing.

Never use:

```python
try:
    ...
except:
    pass
```

or equivalent patterns.

Errors must:

1. be caught at the correct boundary
2. contain useful structured context
3. be logged appropriately
4. propagate to the responsible subsystem
5. produce a safe user-facing response when appropriate

Never expose secrets or internal stack traces to end users.

---

## 8.2 Strict Typing

Python:

* Pydantic v2
* mypy or pyright
* explicit types

TypeScript:

```text
strict: true
```

and:

```text
tsc --noEmit
```

must pass for affected applications.

Avoid `any`.

If an exception is unavoidable, document the reason.

---

# 9. No Fake Production Implementations

Production execution paths must never pretend that an unfinished subsystem works.

Forbidden:

```text
"Success! Task completed."
```

when the task was not actually executed.

Forbidden:

```text
return "mock response"
```

in a production execution path.

When a subsystem is incomplete, use an explicit typed state such as:

```text
PENDING
NOT_IMPLEMENTED
UNAVAILABLE
REQUIRES_CONFIGURATION
```

The UI must communicate the actual state honestly.

Development fixtures and mocks are permitted only when:

1. they are isolated from production paths
2. they are clearly labelled
3. they are used for tests or development
4. they cannot silently become production behavior

---

# 10. Shell and Computer Control

Never expose raw:

```text
bash -c
```

or equivalent unrestricted shell execution directly to an LLM.

All terminal execution must pass through:

```text
LLM
 ↓
Tool Schema
 ↓
Policy Engine
 ↓
Command Validation
 ↓
Working Directory Validation
 ↓
Sandbox / Execution Adapter
 ↓
Result
```

Commands must be validated.

Working directories must be restricted.

Environment variables must be controlled.

Execution timeouts must exist.

Output must be bounded.

Dangerous operations must require appropriate approval.

---

# 11. File-System Operations

Any agent operation that modifies user-controlled files must:

1. identify the target
2. determine risk
3. create an appropriate pre-execution recovery point
4. execute through the approved tool
5. record the result
6. provide recovery information where available

Never allow an agent to silently overwrite unrelated user changes.

Before modifying a file:

* inspect existing contents
* preserve unrelated changes
* modify the smallest necessary region

---

# 12. Secrets & Environment

Never commit:

```text
.env
.env.local
private keys
certificates
tokens
credentials
```

All required environment variables must be documented in:

```text
.env.example
```

with:

* variable name
* purpose
* required/optional status
* safe example value where possible

Never place real credentials in `.env.example`.

---

# 13. Database Rules

Before modifying the database:

1. inspect current schema
2. inspect migrations
3. understand relationships
4. identify affected data
5. determine rollback strategy

Never silently perform destructive migrations.

Production migrations must be explicitly reviewed.

Database operations initiated by agents must respect the same policy system as other mutating tools.

---

# 14. Observability

Agentic execution must generate structured telemetry where appropriate.

Track:

* request ID
* task ID
* execution ID
* agent ID
* tool ID
* model/provider
* latency
* token usage
* policy decision
* approval decision
* execution result
* error category

Never log:

* API keys
* authentication tokens
* passwords
* unnecessary personal data
* raw sensitive user content unless explicitly required and protected

---

# 15. Audit Ledger

The audit system must be append-only from the application's normal execution path.

Important events should include:

```text
REQUEST_CREATED
INTENT_ANALYZED
MEMORY_RETRIEVED
PLAN_CREATED
TOOL_SELECTED
POLICY_EVALUATED
PERMISSION_REQUESTED
PERMISSION_GRANTED
PERMISSION_DENIED
APPROVAL_REQUESTED
APPROVED
REJECTED
EXECUTION_STARTED
EXECUTION_COMPLETED
EXECUTION_FAILED
ROLLBACK_STARTED
ROLLBACK_COMPLETED
TASK_COMPLETED
TASK_FAILED
```

Audit records must reference relevant snapshots and execution IDs.

---

# 16. Memory Rules

NEXUS memory must distinguish between:

```text
Working Memory
Episodic Memory
Semantic Memory / RAG
```

Do not automatically promote every conversation message into persistent memory.

Persistent memory must have:

* provenance
* timestamp
* source
* confidence where applicable
* lifecycle policy
* deletion mechanism

Users must have meaningful control over persistent memory.

---

# 17. Agent Planning

Agent plans should be represented as structured task graphs where dependencies matter.

Prefer:

```text
Task A
 ├── Task B
 ├── Task C
 │     └── Task D
 └── Task E
```

over an opaque sequence of natural-language instructions.

Each executable task should have:

* ID
* description
* dependencies
* required tools
* risk
* status
* inputs
* outputs
* retry policy
* timeout

Do not execute tasks whose dependencies have not been satisfied.

---

# 18. Human-in-the-Loop

HITL approval requests must provide enough information for an informed decision.

Where appropriate, show:

* intended action
* target
* risk level
* relevant arguments
* expected effects
* affected files/resources
* proposed diff
* rollback availability

Never use vague approval prompts such as:

> "Allow agent to continue?"

when a more specific explanation is possible.

---

# 19. UI / UX

NEXUS should feel:

* intelligent
* calm
* fast
* contextual
* trustworthy
* technically sophisticated

Avoid turning NEXUS into a generic AI dashboard.

The ambient interface should prioritize:

* speed
* keyboard interaction
* contextual awareness
* minimal interruption

The dashboard should prioritize:

* visibility
* control
* observability
* configuration
* history

---

# 20. Testing Strategy

Testing should exist at multiple levels:

```text
Unit
  ↓
Integration
  ↓
Agent / Tool Evaluation
  ↓
E2E
  ↓
Production Observability
```

Critical tools require integration tests.

Critical agent pipelines require evaluation tests.

Security boundaries require negative tests.

Permission systems require explicit allow/deny test cases.

Rollback functionality must be tested.

---

# 21. Phase Completion Gate

At the conclusion of every development phase:

## Required checks

Run the tools that are actually configured for the affected project.

Examples:

```text
ruff check
eslint
mypy
pyright
tsc --noEmit
pytest
npm test
build
```

Do NOT invent missing commands merely to satisfy this document.

If a required verification system does not yet exist:

1. identify it as a gap
2. document the gap
3. do not falsely claim the check passed

---

## Build

Build all affected applications.

---

## Runtime Verification

For user-facing changes:

* run the relevant application
* verify the affected flow
* check browser/desktop behavior
* inspect console errors
* inspect relevant network errors

---

## Documentation

Update:

```text
docs/STATUS.md
```

with:

* completed features
* generated artifacts
* known limitations
* trade-offs
* unresolved issues
* prerequisites for the next phase

Update:

```text
docs/ARCHITECTURE.md
```

when:

* interfaces change
* schemas change
* service boundaries change
* system topology changes
* major architectural decisions change

---

# 22. Phase Boundary

NEXUS development is divided into explicit phases.

At the conclusion of a phase:

1. complete implementation
2. run available verification
3. update documentation
4. produce a phase report
5. STOP

Do NOT automatically begin the next phase.

The user must review and explicitly approve the next phase.

---

# 23. Git Safety

Before significant changes:

```text
git status
git branch
```

must be inspected.

Never:

* reset unrelated user changes
* force-push
* delete branches
* rewrite history
* discard changes you did not create

without explicit approval.

Use focused commits when commits are requested.

---

# 24. Dependency Safety

Before adding a dependency:

1. inspect existing dependencies
2. determine whether existing functionality is sufficient
3. evaluate maintenance and security implications
4. confirm compatibility
5. install only when justified

Do not introduce dependencies merely for convenience.

Do not perform major dependency upgrades as part of unrelated feature work.

---

# 25. Agent Autonomy Boundaries

Agents may autonomously:

* inspect code
* analyze architecture
* edit approved project files
* run safe tests
* run builds
* inspect browser output
* fix ordinary development errors
* perform low-risk development operations

Agents must request user approval for:

* destructive operations
* production changes
* financial actions
* external communications
* privilege escalation
* deletion of important data
* irreversible operations
* major architectural migrations
* actions outside the defined project boundary

---

# 26. Constitution Protection

This file is protected.

AI agents MUST NOT modify:

```text
AGENTS.md
```

or security/policy rules merely to make another task easier.

Changes to this constitution require explicit human approval.

An agent must never weaken its own security, permission, audit, or approval requirements.

---

# 27. Change Discipline

Every non-trivial task follows:

```text
UNDERSTAND
    ↓
PLAN
    ↓
IMPLEMENT
    ↓
TEST
    ↓
VERIFY
    ↓
REPORT
```

Do not skip a stage without documenting why.

For trivial changes, planning may be implicit.

For architectural or security-sensitive changes, planning must be explicit.

---

# 28. Definition of Done

A task is complete only when:

* implementation exists
* relevant interfaces are integrated
* types pass
* relevant tests pass
* affected applications build
* runtime behavior is verified when applicable
* security considerations are addressed
* documentation is updated when necessary
* no unrelated functionality was damaged

Code that merely compiles is not considered complete.

---

# 29. Agent Final Report

At the end of every non-trivial task, provide:

## Summary

What changed.

## Files

Files created, modified, or deleted.

## Architecture

Relevant architectural impact.

## Verification

Tests, linting, type checking, builds and runtime/browser checks performed.

## Security

Relevant security considerations.

## Known Limitations

Anything incomplete or uncertain.

## Next Step

The next logical action, without automatically executing it.

---

# 30. Final Principle

NEXUS must never become powerful merely for the sake of being powerful.

The objective is:

```text
Capability
    +
Control
    +
Observability
    +
Security
    +
Reversibility
    =
Trustworthy Agentic System
```

When capability and safety conflict, preserve user control.

When speed and correctness conflict, preserve correctness.

When convenience and explicit authorization conflict, preserve authorization.

Build NEXUS incrementally, measurably, and transparently.
