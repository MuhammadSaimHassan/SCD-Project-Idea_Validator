import { getApiBaseUrl } from "./config";
import type {
  AuthSession,
  CompareIdeasResult,
  ComputeTier,
  DimensionKey,
  GoalType,
  IdeaSummary,
  IdeaVersionEntry,
  RunStatus,
  StudentProfile,
  Verdict,
} from "./types";

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string
): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const resp = await fetch(`${getApiBaseUrl()}${path}`, {
    ...options,
    headers,
  });
  if (!resp.ok) {
    const errBody = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(errBody.detail || `Request failed (${resp.status})`);
  }
  return (await resp.json()) as T;
}

export const api = {
  register(email: string, password: string): Promise<AuthSession> {
    return request<AuthSession>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },

  login(email: string, password: string): Promise<AuthSession> {
    return request<AuthSession>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },

  getProfile(token: string): Promise<StudentProfile> {
    return request<StudentProfile>("/profile", {}, token);
  },

  saveProfile(
    token: string,
    payload: {
      skills: string[];
      hours_per_week: number;
      weeks_available: number;
      team_size: number;
      compute: ComputeTier;
      goal: GoalType;
      interests: string[];
    }
  ): Promise<StudentProfile> {
    return request<StudentProfile>(
      "/profile",
      { method: "PUT", body: JSON.stringify(payload) },
      token
    );
  },

  startDiscover(
    token: string,
    payload: { niche_wish: string; max_ideas: number; require_deep_search_approval?: boolean }
  ): Promise<{ run_id: string; status: string; workflow: string }> {
    return request(
      "/discover",
      { method: "POST", body: JSON.stringify(payload) },
      token
    );
  },

  startValidate(
    token: string,
    payload: {
      title: string;
      idea_text: string;
      estimated_build_hours: number;
      needs_clarification?: boolean;
      require_deep_search_approval?: boolean;
      simulate_thin_evidence?: boolean;
    }
  ): Promise<{ run_id: string; status: string; workflow: string }> {
    return request(
      "/validate",
      { method: "POST", body: JSON.stringify(payload) },
      token
    );
  },

  getRun(token: string, runId: string): Promise<RunStatus> {
    return request<RunStatus>(`/runs/${runId}`, {}, token);
  },

  answerRun(token: string, runId: string, answer: string): Promise<RunStatus> {
    return request<RunStatus>(
      `/runs/${runId}/answer`,
      { method: "POST", body: JSON.stringify({ answer }) },
      token
    );
  },

  approveRun(
    token: string,
    runId: string,
    approved: boolean,
    reason = ""
  ): Promise<RunStatus> {
    return request<RunStatus>(
      `/runs/${runId}/approve`,
      { method: "POST", body: JSON.stringify({ approved, reason }) },
      token
    );
  },

  challengeIdea(
    token: string,
    ideaId: string,
    dimension: DimensionKey,
    claim: string
  ): Promise<Verdict> {
    return request<Verdict>(
      `/ideas/${ideaId}/challenge`,
      { method: "POST", body: JSON.stringify({ dimension, claim }) },
      token
    );
  },

  applyWhatIf(
    token: string,
    ideaId: string,
    dimension_override: Partial<Record<DimensionKey, number>>
  ): Promise<Verdict> {
    return request<Verdict>(
      `/ideas/${ideaId}/whatif`,
      { method: "POST", body: JSON.stringify({ dimension_override }) },
      token
    );
  },

  listIdeas(token: string): Promise<IdeaSummary[]> {
    return request<IdeaSummary[]>("/ideas", {}, token);
  },

  getIdeaVersions(token: string, ideaId: string): Promise<IdeaVersionEntry[]> {
    return request<IdeaVersionEntry[]>(`/ideas/${ideaId}/versions`, {}, token);
  },

  compareIdeas(token: string, left: string, right: string): Promise<CompareIdeasResult> {
    return request<CompareIdeasResult>(
      `/compare?left=${encodeURIComponent(left)}&right=${encodeURIComponent(right)}`,
      {},
      token
    );
  },
};
