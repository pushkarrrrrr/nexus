import type { ApprovalRequest } from "@nexus/types";

export const mockApprovals: ApprovalRequest[] = [
  {
    approval_id: "appr_908a1c",
    session_id: "sess_01H9A1K4001",
    step_id: "step_2",
    agent_name: "CodingAgent",
    tool_name: "filesystem.modify",
    action_type: "MODIFY",
    risk_level: "MEDIUM",
    reason: "Refactor auth middleware to extract and validate Bearer tokens from incoming Authorization headers.",
    created_at: "2026-09-18T18:31:00Z",
    diff_preview: {
      file_path: "services/api/nexus_api/middleware.py",
      original_content_hash: "3a8f19...b2",
      new_content_hash: "9c4e22...f1",
      lines_added: 4,
      lines_removed: 2,
      unified_diff: `--- a/services/api/nexus_api/middleware.py
+++ b/services/api/nexus_api/middleware.py
@@ -18,6 +18,8 @@ class LoggingAndTraceMiddleware(BaseHTTPMiddleware):
-        auth_header = None
-        token = None
+        auth_header = request.headers.get("Authorization")
+        token = auth_header.split(" ")[1] if auth_header and "Bearer " in auth_header else None
+        structlog.contextvars.bind_contextvars(user_token_present=bool(token))
         response = await call_next(request)`,
    },
  },
  {
    approval_id: "appr_701b2f",
    session_id: "sess_01H9A1K4001",
    step_id: "step_4",
    agent_name: "SystemOperatorAgent",
    tool_name: "terminal.execute",
    action_type: "EXECUTE",
    risk_level: "HIGH",
    reason: "Execute git commit and push changes to remote tracking branch 'main'.",
    command_args: {
      command: "git add . && git commit -m 'feat: bearer auth implementation' && git push origin main",
      cwd: "/Users/apple/coding/nexus",
      timeout_seconds: 30,
    },
    created_at: "2026-09-18T18:32:15Z",
  },
];
