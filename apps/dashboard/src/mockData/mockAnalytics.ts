export interface BenchmarkAblation {
  configuration: string;
  task_success_rate: number; // %
  planning_accuracy: number; // %
  avg_latency_sec: number;
  safety_violations: number;
  cost_per_task: number; // $
}

export const mockAblations: BenchmarkAblation[] = [
  {
    configuration: "1. Baseline Conversational LLM",
    task_success_rate: 34.2,
    planning_accuracy: 41.0,
    avg_latency_sec: 2.1,
    safety_violations: 14,
    cost_per_task: 0.012,
  },
  {
    configuration: "2. RAG-Enhanced Assistant",
    task_success_rate: 58.6,
    planning_accuracy: 62.4,
    avg_latency_sec: 4.5,
    safety_violations: 8,
    cost_per_task: 0.028,
  },
  {
    configuration: "3. Memory + RAG System",
    task_success_rate: 76.1,
    planning_accuracy: 79.5,
    avg_latency_sec: 5.8,
    safety_violations: 5,
    cost_per_task: 0.045,
  },
  {
    configuration: "4. Agentic NEXUS Operating Layer",
    task_success_rate: 93.4,
    planning_accuracy: 96.1,
    avg_latency_sec: 8.2,
    safety_violations: 0, // Zero tolerance / Policy Engine gated
    cost_per_task: 0.062,
  },
];
