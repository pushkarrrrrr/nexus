export interface AgentProfile {
  id: string;
  name: string;
  role: string;
  description: string;
  assigned_model: string;
  status: "idle" | "executing" | "planning" | "offline";
  allowed_tools: string[];
  system_prompt_preview: string;
}

export const mockAgents: AgentProfile[] = [
  {
    id: "agent_orchestrator",
    name: "OrchestratorAgent",
    role: "Master Planning & Task Dispatcher",
    description: "Analyzes user requests, synthesizes topological DAG plans, routes tasks to specialized workers, and verifies step outcomes.",
    assigned_model: "claude-3-5-sonnet / gpt-4o",
    status: "executing",
    allowed_tools: ["system.plan", "memory.retrieve", "dag.synthesize"],
    system_prompt_preview: "You are the NEXUS Orchestrator. You decompose high-level user intent into clean, non-cyclic DAG plans.",
  },
  {
    id: "agent_coding",
    name: "CodingAgent",
    role: "Software Engineering & Refactoring",
    description: "Reads codebases, proposes structured AST/unified diff patches, and validates syntax and lint rules.",
    assigned_model: "claude-3-5-sonnet",
    status: "idle",
    allowed_tools: ["filesystem.read", "filesystem.modify", "filesystem.write", "terminal.execute"],
    system_prompt_preview: "You are the NEXUS Coding Agent. You emit precise unified diffs and never guess file contents.",
  },
  {
    id: "agent_system",
    name: "SystemOperatorAgent",
    role: "Local OS & Shell Execution",
    description: "Executes verified terminal commands, runs build/test scripts, and inspects process state under strict policy supervision.",
    assigned_model: "gpt-4o-mini / ollama-llama3",
    status: "idle",
    allowed_tools: ["terminal.execute", "filesystem.read", "system.status"],
    system_prompt_preview: "You are the NEXUS System Operator. You run sandboxed terminal commands and report exact exit codes.",
  },
  {
    id: "agent_research",
    name: "ResearchAgent",
    role: "Document & Web Knowledge Synthesis",
    description: "Performs hybrid semantic search over personal vector indexes, navigates the web, and synthesizes citations.",
    assigned_model: "gemini-1.5-pro",
    status: "idle",
    allowed_tools: ["browser.search", "browser.open", "knowledge.query"],
    system_prompt_preview: "You are the NEXUS Research Agent. You synthesize factual information and strictly ground answers in retrieved chunks.",
  },
  {
    id: "agent_document",
    name: "DocumentAgent",
    role: "Report & Documentation Generator",
    description: "Creates technical markdown documentation, architectural diagrams, and summarizes task execution results.",
    assigned_model: "gpt-4o-mini",
    status: "idle",
    allowed_tools: ["filesystem.write", "filesystem.read"],
    system_prompt_preview: "You are the NEXUS Document Agent. You write clear, concise, GitHub Flavored Markdown reports.",
  },
  {
    id: "agent_computer",
    name: "ComputerAgent",
    role: "MacOS Desktop Automation",
    description: "Controls macOS native accessibility, manages active windows, and captures contextual window titles via MacOSAdapter.",
    assigned_model: "claude-3-5-sonnet",
    status: "idle",
    allowed_tools: ["computer.active_window", "computer.selected_text"],
    system_prompt_preview: "You are the NEXUS Computer Agent. You interface with macOS native APIs through the MacOSAdapter.",
  },
];
