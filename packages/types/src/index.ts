/**
 * NEXUS Cross-Boundary Data Contracts
 * Shared across Next.js Dashboard, Tauri Ambient Overlay, and API Services
 */

export type ActionType = 
  | 'READ' 
  | 'WRITE' 
  | 'MODIFY' 
  | 'DELETE' 
  | 'EXECUTE' 
  | 'EXTERNAL_ACTION';

export type RiskLevel = 
  | 'LOW' 
  | 'MEDIUM' 
  | 'HIGH' 
  | 'CRITICAL';

export type TaskStatus = 
  | 'pending' 
  | 'planning' 
  | 'awaiting_approval' 
  | 'executing' 
  | 'completed' 
  | 'failed' 
  | 'cancelled';

export type ApprovalDecisionType = 
  | 'approve_once' 
  | 'approve_session' 
  | 'always_allow_read' 
  | 'deny';

export type MemoryClass = 
  | 'working' 
  | 'conversational' 
  | 'episodic' 
  | 'semantic' 
  | 'procedural';

export interface ToolManifest {
  name: string;
  description: string;
  action_type: ActionType;
  risk_level: RiskLevel;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  reversibility: boolean;
  audit_required: boolean;
}

export interface FileDiffPreview {
  file_path: string;
  original_content_hash?: string;
  new_content_hash?: string;
  unified_diff: string;
  lines_added: number;
  lines_removed: number;
}

export interface ApprovalRequest {
  approval_id: string;
  session_id: string;
  step_id: string;
  agent_name: string;
  tool_name: string;
  action_type: ActionType;
  risk_level: RiskLevel;
  reason: string;
  command_args?: Record<string, unknown>;
  diff_preview?: FileDiffPreview;
  created_at: string;
  expires_at?: string;
}

export interface ApprovalResponse {
  approval_id: string;
  decision: ApprovalDecisionType;
  decided_at: string;
  feedback_notes?: string;
}

export interface AuditEvent {
  event_id: string;
  timestamp: string;
  session_id: string;
  step_id?: string;
  agent_name: string;
  tool_name: string;
  action_type: ActionType;
  risk_level: RiskLevel;
  inputs: Record<string, unknown>;
  outputs?: Record<string, unknown>;
  error?: string;
  policy_decision: 'auto_approved' | 'approved_by_user' | 'denied_by_user' | 'blocked_by_policy';
  approval_id?: string;
  snapshot_id?: string;
  execution_duration_ms: number;
  undo_registered: boolean;
  undone_at?: string;
}

export interface SnapshotRecord {
  snapshot_id: string;
  action_id: string;
  file_path: string;
  sha256_before: string;
  sha256_after?: string;
  snapshot_file_path: string;
  created_at: string;
  restored_at?: string;
}

export interface MemoryItem {
  id: string;
  memory_class: MemoryClass;
  title: string;
  content: string;
  source_turn_id?: string;
  confidence: number;
  enabled: boolean;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface DAGNode {
  id: string;
  name: string;
  agent: string;
  tool?: string;
  input?: Record<string, unknown>;
  dependencies: string[];
  status: TaskStatus;
  result?: Record<string, unknown>;
  error?: string;
}

export interface TaskDAG {
  dag_id: string;
  session_id: string;
  goal: string;
  nodes: DAGNode[];
  status: TaskStatus;
  created_at: string;
  completed_at?: string;
}

// WebSocket Event Envelopes
export interface NexusClientEvent {
  event_type: 'request.submit' | 'approval.respond' | 'task.cancel' | 'undo.trigger';
  session_id: string;
  timestamp: string;
  payload: Record<string, unknown>;
}

export interface NexusServerEvent {
  event_type: 
    | 'token.stream' 
    | 'dag.updated' 
    | 'tool.started' 
    | 'tool.completed' 
    | 'approval.required' 
    | 'audit.recorded' 
    | 'task.finished' 
    | 'error';
  session_id: string;
  timestamp: string;
  payload: Record<string, unknown>;
}
