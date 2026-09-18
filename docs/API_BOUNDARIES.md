# NEXUS API Boundaries & Protocol Specification

This document defines the REST API endpoints and WebSocket event envelopes used by the **NEXUS Dashboard** and **NEXUS Ambient Layer** to communicate with `services/api`.

---

## 1. REST API Endpoints

### A. Health & System Status
- `GET /health`
  - Response: `{"status": "ok", "version": "0.1.0", "active_agents": 4, "database": "connected"}`
- `GET /api/v1/system/status`
  - Returns current OS context (macOS version, active window, cwd, memory usage).

### B. Sessions
- `GET /api/v1/sessions`
  - Returns paginated list of sessions.
- `POST /api/v1/sessions`
  - Request: `{"surface": "dashboard" | "ambient", "title": Optional[str], "os_context": Optional[dict]}`
  - Response: `Session` object.
- `GET /api/v1/sessions/{session_id}`
  - Returns session details, active DAG, and message history.

### C. Task DAGs & Planning
- `POST /api/v1/sessions/{session_id}/tasks`
  - Submits a user prompt to be planned into a DAG.
  - Request: `{"prompt": str, "context": Optional[dict]}`
  - Response: `TaskDAG` object with initial nodes.
- `GET /api/v1/sessions/{session_id}/dags/{dag_id}`
  - Returns DAG state and execution status for each node.
- `POST /api/v1/dags/{dag_id}/cancel`
  - Signals in-flight cancellation to the orchestrator.

### D. Human-in-the-Loop Approvals
- `GET /api/v1/approvals/pending`
  - Returns all pending `ApprovalRequest` objects across sessions.
- `POST /api/v1/approvals/{approval_id}/respond`
  - Request: `{"decision": "approve_once" | "approve_session" | "always_allow_read" | "deny", "feedback_notes": Optional[str]}`
  - Response: `{"status": "accepted", "approval_id": str}`

### E. Audit Ledger & Rollbacks
- `GET /api/v1/audit`
  - Paginated list of `AuditEvent` records with filtering by `risk_level`, `tool_name`, or `session_id`.
- `GET /api/v1/audit/{event_id}`
  - Detailed view of a single audit event, including inputs, outputs, diff previews, and snapshot metadata.
- `POST /api/v1/audit/{event_id}/undo`
  - Executes rollback of the mutating operation using its recorded file snapshot.
  - Response: `{"status": "undone", "event_id": str, "restored_path": str}`

### F. Memory Management
- `GET /api/v1/memories`
  - Query memories filtered by `memory_class` (`working`, `conversational`, `episodic`, `semantic`, `procedural`).
- `POST /api/v1/memories`
  - User adds manual preference or semantic knowledge.
- `PATCH /api/v1/memories/{memory_id}`
  - Edit or toggle `enabled` state of a memory item.
- `DELETE /api/v1/memories/{memory_id}`
  - Permanently removes memory item.

---

## 2. Real-Time WebSocket Protocol

- **Endpoint**: `ws://localhost:8000/ws/nexus?client_surface={dashboard|ambient}&session_id={session_id}`

### A. Client-to-Server Messages
All messages must follow the `NexusClientEvent` envelope:
```json
{
  "event_type": "request.submit",
  "session_id": "sess_01H...",
  "timestamp": "2026-09-18T18:30:00Z",
  "payload": {
    "prompt": "Refactor auth middleware to Bearer tokens",
    "context": {
      "cwd": "/Users/apple/coding/nexus",
      "active_app": "com.apple.Terminal"
    }
  }
}
```

Available `event_type` values:
- `request.submit`: Dispatches new user natural language goal.
- `approval.respond`: Transmits user decision on an active approval request.
- `task.cancel`: Aborts current task DAG execution.
- `undo.trigger`: Triggers rollback on a specific action ID.

### B. Server-to-Client Messages
All messages follow the `NexusServerEvent` envelope:
```json
{
  "event_type": "approval.required",
  "session_id": "sess_01H...",
  "timestamp": "2026-09-18T18:30:02Z",
  "payload": {
    "approval_id": "appr_987",
    "tool_name": "filesystem.modify",
    "risk_level": "MEDIUM",
    "reason": "Update token extraction in services/api/middleware/auth.py",
    "diff_preview": {
      "file_path": "services/api/middleware/auth.py",
      "unified_diff": "--- a/auth.py\n+++ b/auth.py\n@@ -10,3 +10,4 @@\n- token = None\n+ token = get_bearer()",
      "lines_added": 1,
      "lines_removed": 1
    }
  }
}
```

Available `event_type` values:
- `token.stream`: Reasoning token chunks streamed from LLM.
- `dag.updated`: Full or incremental DAG state update (node statuses, results).
- `tool.started`: Notification that a tool execution has commenced.
- `tool.completed`: Tool finished with exit code and timing.
- `approval.required`: HITL approval prompt broadcast to both Dashboard and Ambient HUD.
- `audit.recorded`: New entry appended to the immutable security ledger.
- `task.finished`: Goal successfully achieved or terminated.
- `error`: Structured exception notification with recovery guidance.
