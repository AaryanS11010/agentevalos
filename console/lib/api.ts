const ORCHESTRATOR_URL = process.env.NEXT_PUBLIC_ORCHESTRATOR_URL ?? "http://localhost:8001";
const EVAL_ENGINE_URL = process.env.NEXT_PUBLIC_EVAL_ENGINE_URL ?? "http://localhost:8002";

export type AgentRun = {
  id: string;
  status: string;
  industry: string;
  output: Record<string, unknown> | null;
};

export type LeaderboardEntry = {
  model_name: string;
  dataset_ref: string;
  primary_metric_name: string;
  primary_metric_value: number;
  calibration_error: number | null;
  fairness_gap: number | null;
  impact_score: number;
  evaluated_at: string;
};

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`Request failed: ${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const api = {
  listRuns: (): Promise<AgentRun[]> =>
    fetch(`${ORCHESTRATOR_URL}/runs`, { cache: "no-store" }).then(json<AgentRun[]>),

  getRun: (id: string): Promise<AgentRun> =>
    fetch(`${ORCHESTRATOR_URL}/runs/${id}`, { cache: "no-store" }).then(json<AgentRun>),

  createRun: (industry: string): Promise<AgentRun> =>
    fetch(`${ORCHESTRATOR_URL}/runs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ industry, agent_name: "tabular-model-benchmark" }),
    }).then(json<AgentRun>),

  getLeaderboard: (industry: string): Promise<{ industry: string; entries: LeaderboardEntry[] }> =>
    fetch(`${EVAL_ENGINE_URL}/benchmarks/industry/${industry}/leaderboard`, {
      cache: "no-store",
    }).then(json<{ industry: string; entries: LeaderboardEntry[] }>),
};
