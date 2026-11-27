export type ComputeTier = "laptop" | "free_gpu" | "paid";
export type GoalType = "startup" | "portfolio" | "course_project";
export type VerdictLabel = "GO" | "PIVOT" | "NO-GO" | "INSUFFICIENT_EVIDENCE";
export type StabilityLabel = "STABLE" | "BORDERLINE";
export type DimensionKey =
  | "demand_pain"
  | "competition"
  | "differentiation"
  | "feasibility"
  | "risk"
  | "learning";

export interface AuthSession {
  user_id: string;
  email: string;
  access_token: string;
}

export interface StudentProfile {
  user_id: string;
  skills: string[];
  hours_per_week: number;
  weeks_available: number;
  team_size: number;
  compute: ComputeTier;
  goal: GoalType;
  interests: string[];
  profile_version: number;
}

export interface DimensionScore {
  dimension: DimensionKey;
  score: number;
  confidence: number;
  evidence_ids: string[];
  features: Record<string, string | number | boolean>;
  reason: string;
  rubric_version: string;
  model: string;
  abstained?: boolean;
}

export interface GatesResult {
  evidence: "pass" | "fail";
  feasibility: "pass" | "fail";
  risk: "pass" | "fail";
  duplicate: "pass" | "fail";
  failure_reasons: Record<string, string>;
}

export interface WhatIfSuggestion {
  change: string;
  dimension: DimensionKey | null;
  target_score: number | null;
  new_score: number;
  new_verdict: VerdictLabel;
}

export interface Verdict {
  idea_id: string;
  version: number;
  run_id: string;
  verdict: VerdictLabel;
  stability: StabilityLabel;
  score: number;
  confidence: number;
  gates: GatesResult;
  weights: Record<DimensionKey, number>;
  thresholds: Record<string, number>;
  scores: DimensionScore[];
  weakest_dimension: DimensionKey | null;
  what_would_make_go: WhatIfSuggestion[];
  sensitivity: {
    runs: number;
    flipped: number;
    flip_triggers: string[];
  };
  versions: {
    engine: string;
    rubrics: string;
    profile_weights: string;
  };
  insufficient_reasons: string[];
}

export interface RunEvent {
  step: number;
  agent: string;
  tool: string;
  spend_usd: number;
  message: string;
  cache_hit?: boolean;
  ts: string;
}

export interface RunStatus {
  run_id: string;
  workflow: "discover" | "validate";
  status: string;
  events: RunEvent[];
  pending_question: { question: string; field: string } | null;
  pending_approval: { action: string; estimated_cost_usd: number; message: string } | null;
  result: {
    verdict?: Verdict;
    cache_hit?: boolean;
    ideas?: Array<{ title: string; verdict: Verdict }>;
    message?: string;
  } | null;
}

export interface IdeaSummary {
  idea_id: string;
  title: string;
  source: string;
  latest_version: number;
  latest_verdict: Verdict | null;
}

export interface IdeaVersionEntry {
  version: number;
  text: string;
  verdict: Verdict | null;
}

export interface CompareIdeasResult {
  left: IdeaSummary;
  right: IdeaSummary;
  dimension_deltas: Record<DimensionKey, number>;
}
