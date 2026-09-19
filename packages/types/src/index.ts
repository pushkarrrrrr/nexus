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
  | 'observing'
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
  started_at?: string;
  completed_at?: string;
}

export interface TaskDAG {
  dag_id: string;
  session_id: string;
  goal: string;
  nodes: DAGNode[];
  status: TaskStatus;
  user_id?: string;
  execution_metadata?: Record<string, unknown>;
  created_at: string;
  completed_at?: string;
}

// WebSocket Event Envelopes
export interface NexusClientEvent {
  event_type: 'request.submit' | 'approval.respond' | 'task.cancel' | 'undo.trigger' | 'task.transition';
  session_id: string;
  timestamp: string;
  payload: Record<string, unknown>;
}

export interface NexusServerEvent {
  event_type: 
    | 'token.stream' 
    | 'dag.updated' 
    | 'task.state_changed'
    | 'step.state_changed'
    | 'task.cancelled'
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

// Identity & User Context Contracts

export interface ModelPreferences {
  default_provider: string;
  fast_model: string;
  reasoning_model: string;
  temperature: number;
}

export interface PermissionPreferences {
  auto_grant_low_risk: boolean;
  require_hitl_high_risk: boolean;
  session_grant_ttl_minutes: number;
}

export interface PrivacySettings {
  store_audit_payloads: boolean;
  telemetry_enabled: boolean;
  allow_external_rag: boolean;
}

export interface UserPreferences {
  timezone: string;
  model_preferences: ModelPreferences;
  permission_preferences: PermissionPreferences;
  privacy_settings: PrivacySettings;
}

export interface UserProfile {
  id: string;
  email: string;
  full_name?: string | null;
  is_active: boolean;
  created_at: string;
  preferences?: UserPreferences | null;
}

export interface UserRegisterRequest {
  email: string;
  password: string;
  full_name?: string;
}

export interface UserLoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserProfile;
}

export interface UpdatePreferencesRequest {
  timezone?: string;
  model_preferences?: Partial<ModelPreferences>;
  permission_preferences?: Partial<PermissionPreferences>;
  privacy_settings?: Partial<PrivacySettings>;
}

// Phase 4: Core Task, Goal, Timeline & Session Contracts

export type GoalStatus = 'active' | 'paused' | 'completed' | 'archived';

export interface GoalMilestone {
  id: string;
  title: string;
  completed: boolean;
  completed_at?: string;
}

export interface Goal {
  id: string;
  user_id: string;
  session_id?: string;
  title: string;
  description?: string;
  status: GoalStatus;
  category: string;
  progress: number;
  milestones: GoalMilestone[];
  created_at: string;
  updated_at: string;
}

export interface GoalCreateRequest {
  title: string;
  description?: string;
  category?: string;
  session_id?: string;
  milestones?: GoalMilestone[];
}

export interface GoalUpdateRequest {
  title?: string;
  description?: string;
  status?: GoalStatus;
  category?: string;
  progress?: number;
  milestones?: GoalMilestone[];
}

export interface TaskEvent {
  id: string;
  dag_id: string;
  node_id?: string;
  event_type: string;
  from_state?: string;
  to_state?: string;
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface TaskTimelineResponse {
  dag_id: string;
  events: TaskEvent[];
  total_events: number;
}

export interface SessionRecord {
  session_id: string;
  user_id: string;
  title: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

// =====================================================================
// Phase 5: AI Gateway & Structured Agent Contracts
// =====================================================================

export type LLMProviderType = 'openai' | 'anthropic' | 'gemini' | 'ollama' | 'mock';

export interface ModelUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
  latency_ms: number;
}

export interface CompletionRequest {
  prompt: string;
  system_prompt?: string;
  model?: string;
  temperature?: number;
  max_tokens?: number;
  stop_sequences?: string[];
  provider?: LLMProviderType;
  timeout_sec?: number;
}

export interface CompletionResponse {
  content: string;
  model: string;
  provider: string;
  usage: ModelUsage;
  finish_reason: string;
}

export interface EmbeddingRequest {
  texts: string[];
  model?: string;
  provider?: LLMProviderType;
}

export interface EmbeddingResponse {
  embeddings: number[][];
  model: string;
  provider: string;
  total_tokens: number;
}

export interface AgentIntent {
  goal: string;
  primary_intent: string;
  domain: string;
  entities: string[];
  risk_level: RiskLevel;
  confidence: number;
  requires_tools: boolean;
}

export interface PlanStep {
  id: string;
  name: string;
  agent: string;
  tool?: string;
  input: Record<string, unknown>;
  dependencies: string[];
  risk_level: RiskLevel;
}

export interface AgentPlan {
  goal: string;
  rationale: string;
  estimated_complexity: string;
  steps: PlanStep[];
}

export interface AgentToolCall {
  tool_name: string;
  arguments: Record<string, unknown>;
  rationale: string;
  expected_output?: string;
  reversibility: boolean;
  risk_level: RiskLevel;
}

export interface AgentToolResult {
  tool_name: string;
  success: boolean;
  data?: Record<string, unknown>;
  error?: string;
  duration_ms: number;
}

export interface AgentFinalResponse {
  answer: string;
  summary?: string;
  artifacts: string[];
  follow_up_suggestions: string[];
}

export interface PromptTemplate {
  template_id: string;
  version: string;
  description: string;
  system_prompt: string;
  user_template: string;
  input_variables: string[];
  created_at: string;
}

export interface GatewayTelemetry {
  total_requests: number;
  successful_requests?: number;
  failed_requests?: number;
  total_prompt_tokens?: number;
  total_completion_tokens?: number;
  total_tokens: number;
  total_estimated_cost_usd?: number;
  total_cost_usd: number;
  average_latency_ms: number;
  active_providers: string[];
  error_count: number;
  retry_count: number;
  retries_count?: number;
  fallback_count: number;
  fallbacks_triggered?: number;
  errors_by_type?: Record<string, number>;
  requests_by_model?: Record<string, number>;
  requests_by_provider?: Record<string, number>;
}



