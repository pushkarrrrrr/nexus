# NEXUS Security & Permission Model

This document specifies the threat model, trust boundaries, permission hierarchy, approval UX requirements, and audit/undo safety invariants for the **NEXUS Agentic AI Operating System**.

---

## 1. Threat Model & Security Objectives

### Primary Threat Vectors
1. **Prompt Injection / Indirect Injection**: Malicious web pages, user documents, or downloaded files attempting to hijack agent reasoning to execute unauthorized system commands.
2. **Autonomous Runaway Execution**: Recursive planning loops that consume system resources or perform unintended cascade file deletions.
3. **Privilege Escalation**: AI attempting to bypass policy constraints via shell sub-invocations (`bash -c`, `sh`, `sudo`, piping to `/dev/null`).
4. **Data Exfiltration**: Covert exfiltration of local sensitive files (ssh keys, `.env`, credentials) via external network requests or browser forms.

### Fundamental Security Invariants
- **No Direct Shell Access**: The LLM is never given a raw, unrestricted shell. All terminal operations pass through structured arguments and a strict safety parser.
- **Air-Gapped Policy Engine**: The Policy Engine is mathematically isolated from agent reasoning. The agent *requests* actions; only the policy engine *executes* them.
- **Mandatory Pre-Execution Snapshots**: No mutating filesystem operation may execute without first saving a rollback snapshot.
- **No Blanket Grants**: The user can never click "Allow everything" or grant blanket unrestricted root privileges.

---

## 2. Action Taxonomy & Risk Classification

### Action Types
- `READ`: Non-mutating data retrieval (file reading, directory listing, system status inspection).
- `WRITE`: Creation of new entities (new files, new directory structures, cache entries).
- `MODIFY`: Alteration of existing state (file edits, appending logs, altering local configurations).
- `DELETE`: Destruction of state (deleting files, dropping tables, pruning directories).
- `EXECUTE`: Subprocess execution (running compilers, test runners, git commands).
- `EXTERNAL_ACTION`: Network-bound side effects (sending webhooks, external API requests, browser navigation).

### Risk Matrix & Gating Rules

| Risk Level | Definition | Typical Capabilities | Default Gating Behavior |
|---|---|---|---|
| **LOW** | Non-destructive, read-only operations with no privacy or system integrity impact. | `filesystem.read`, `git status`, `ls`, searching indexed knowledge. | **Auto-Allowed** (logged to audit ledger). |
| **MEDIUM** | Mutating operations that are fully reversible and scoped to the user workspace. | `filesystem.write` (new file), `filesystem.modify` (code edit), running `pytest` or `npm test`. | **Approval Required or Session-Cached** with pre-execution snapshot. |
| **HIGH** | Irreversible, destructive, external, or security-sensitive actions. | `filesystem.delete`, executing unverified scripts, git branch deletion, sending outbound network requests. | **Strict HITL Approval Required** (Every single time; cannot be permanently cached). |
| **CRITICAL** | System-wide destructive actions, modifying root/OS files, or accessing credentials. | Modifying `/etc/`, accessing `~/.ssh` or `~/.aws`, running `sudo` or `rm -rf`. | **Blocked Outright** (System rejects with security violation event). |

---

## 3. Approval UX Specifications

Generic confirmations such as *"Allow NEXUS to perform this action?"* are **strictly forbidden**.

Every approval request displayed in the **Dashboard** or **Ambient Layer** must render an actionable card containing:

```
┌────────────────────────────────────────────────────────────────────────┐
│  ⚠️  APPROVAL REQUIRED: filesystem.modify                              │
├────────────────────────────────────────────────────────────────────────┤
│  Risk Level: [ MEDIUM ]           Tool: filesystem.modify              │
│  Agent: CodingAgent               Session: sess_01H...                 │
│                                                                        │
│  Reason:                                                               │
│  "Refactor auth middleware to validate Bearer tokens in headers."      │
│                                                                        │
│  Affected Files:                                                       │
│  - services/api/middleware/auth.py                                     │
│                                                                        │
│  Unified Diff:                                                         │
│  @@ -14,6 +14,8 @@ def verify_token(req):                             │
│  -    token = req.cookies.get("session")                               │
│  +    auth_header = req.headers.get("Authorization")                   │
│  +    token = auth_header.split(" ")[1] if auth_header else None       │
│                                                                        │
├────────────────────────────────────────────────────────────────────────┤
│  [ Approve Once ]   [ Approve for Session ]   [ Always Allow Read ]    │
│  [ Deny Action ]                                                       │
└────────────────────────────────────────────────────────────────────────┘
```

### Action Semantics
1. **`[Approve Once]`**: Grants execution authority for this single unique action ID only. Grant expires immediately upon completion.
2. **`[Approve for Session]`**: Caches the permission signature for the current `session_id` and exact tool/pattern (e.g. allow `filesystem.modify` within `/Users/apple/coding/nexus` for the next 60 minutes).
3. **`[Always Allow Read]`**: Only permitted for read-only capabilities (`filesystem.read` on specific directory).
4. **`[Deny Action]`**: Immediately cancels execution. Returns a structured `UserDeniedError` to the agent with optional user notes to prompt plan readjustment.

---

## 4. Reversible Actions & The Audit Engine

### Snapshot Engine
1. Before invoking any mutating tool (`filesystem.write`, `filesystem.modify`, `filesystem.delete`):
   - Check if target file exists.
   - If existing: read raw bytes, compute SHA-256 checksum, and store byte copy in `.nexus/snapshots/{snapshot_id}`.
   - If new file: register an undo operation that will remove the created file upon rollback.
2. Generate an `action_id` (UUID v7, time-ordered).
3. Record action metadata in the Audit Ledger.

### Rollback Execution
When the user triggers `[Undo]` on the Dashboard:
1. Lookup `action_id` in Audit Ledger.
2. Retrieve corresponding snapshot from snapshot store.
3. Verify current file hash against post-action hash (warn user if external edits occurred).
4. Atomically restore previous bytes or delete created file.
5. Log a corresponding `UNDO_EXECUTED` event in the Audit Ledger.

---

## 5. Sandboxed Terminal Constraints

The `terminal.execute` tool must adhere to strict containment rules:
1. **No Raw Shell Expansion**: Commands are parsed into structured arguments `[executable, arg1, arg2, ...]`.
2. **Path Containment**: Working directory (`cwd`) is constrained to approved project roots. Attempts to access root `/`, system folders, or hidden parent paths trigger a `CRITICAL` block.
3. **Execution Timeouts**: Every subprocess has a mandatory timeout (default: 30 seconds; max configurable: 300 seconds).
4. **Stdout / Stderr Streaming**: Real-time pipe capture to prevent memory exhaustion from infinite console output loops (capped at 50,000 lines).
