import { useState } from "react";
import { api } from "./api";
import { AuthProfileView } from "./components/AuthProfileView";
import { HistoryCompareView } from "./components/HistoryCompareView";
import { LiveRunPanel } from "./components/LiveRunPanel";
import { VerdictCard } from "./components/VerdictCard";
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

type Tab = "profile" | "discover" | "validate" | "history";

export default function App() {
  const [tab, setTab] = useState<Tab>("profile");
  const [session, setSession] = useState<AuthSession | null>(null);
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [nicheWish, setNicheWish] = useState("devtools");
  const [discoverApproval, setDiscoverApproval] = useState(false);

  const [ideaTitle, setIdeaTitle] = useState("");
  const [ideaText, setIdeaText] = useState("");
  const [buildHours, setBuildHours] = useState("60");
  const [needsClarify, setNeedsClarify] = useState(false);
  const [thinEvidence, setThinEvidence] = useState(false);

  const [activeRun, setActiveRun] = useState<RunStatus | null>(null);
  const [activeVerdict, setActiveVerdict] = useState<Verdict | null>(null);
  const [discovered, setDiscovered] = useState<Array<{ title: string; verdict: Verdict }>>([]);
  const [ideas, setIdeas] = useState<IdeaSummary[]>([]);
  const [selectedVersions, setSelectedVersions] = useState<IdeaVersionEntry[]>([]);
  const [comparison, setComparison] = useState<CompareIdeasResult | null>(null);

  const handleAuth = async (mode: "login" | "register", email: string, password: string) => {
    setError(null);
    try {
      const auth =
        mode === "register"
          ? await api.register(email, password)
          : await api.login(email, password);
      setSession(auth);
      try {
        const existing = await api.getProfile(auth.access_token);
        setProfile(existing);
      } catch {
        setProfile(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    }
  };

  const handleSaveProfile = async (payload: {
    skills: string[];
    hours_per_week: number;
    weeks_available: number;
    team_size: number;
    compute: ComputeTier;
    goal: GoalType;
    interests: string[];
  }) => {
    if (!session) return;
    setError(null);
    try {
      const saved = await api.saveProfile(session.access_token, payload);
      setProfile(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save profile");
    }
  };

  const syncRunOutcome = (run: RunStatus) => {
    setActiveRun(run);
    if (run.result?.verdict) {
      setActiveVerdict(run.result.verdict);
    }
    if (run.result?.ideas) {
      setDiscovered(run.result.ideas);
    }
  };

  const handleDiscover = async () => {
    if (!session) return;
    setError(null);
    try {
      const accepted = await api.startDiscover(session.access_token, {
        niche_wish: nicheWish,
        max_ideas: 3,
        require_deep_search_approval: discoverApproval,
      });
      const run = await api.getRun(session.access_token, accepted.run_id);
      syncRunOutcome(run);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Discover failed");
    }
  };

  const handleValidate = async () => {
    if (!session) return;
    setError(null);
    try {
      const accepted = await api.startValidate(session.access_token, {
        title: ideaTitle,
        idea_text: ideaText,
        estimated_build_hours: Number(buildHours),
        needs_clarification: needsClarify,
        simulate_thin_evidence: thinEvidence,
      });
      const run = await api.getRun(session.access_token, accepted.run_id);
      syncRunOutcome(run);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Validate failed");
    }
  };

  const handleAnswerRun = async (runId: string, answer: string) => {
    if (!session) return;
    setError(null);
    try {
      const updated = await api.answerRun(session.access_token, runId, answer);
      syncRunOutcome(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit answer");
    }
  };

  const handleApproveRun = async (runId: string, approved: boolean) => {
    if (!session) return;
    setError(null);
    try {
      const updated = await api.approveRun(session.access_token, runId, approved);
      syncRunOutcome(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approval failed");
    }
  };

  const handleChallenge = async (ideaId: string, dimension: DimensionKey, claim: string) => {
    if (!session) return;
    setError(null);
    try {
      const next = await api.challengeIdea(session.access_token, ideaId, dimension, claim);
      setActiveVerdict(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Challenge failed");
    }
  };

  const handleWhatIf = async (
    ideaId: string,
    override: Partial<Record<DimensionKey, number>>
  ) => {
    if (!session) return;
    setError(null);
    try {
      const next = await api.applyWhatIf(session.access_token, ideaId, override);
      setActiveVerdict(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "What-if failed");
    }
  };

  const refreshIdeas = async () => {
    if (!session) return;
    setError(null);
    try {
      const list = await api.listIdeas(session.access_token);
      setIdeas(list);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load history");
    }
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <h1 style={{ margin: 0, fontSize: "1.35rem" }}>Idea Generator with Go / No-Go</h1>
          <span className="muted">Deterministic Verdict Engine &amp; Evidence RAG</span>
        </div>
        <nav className="nav-tabs" aria-label="Primary Navigation">
          <button
            type="button"
            className={tab === "profile" ? "tab-btn active" : "tab-btn"}
            onClick={() => setTab("profile")}
          >
            Profile
          </button>
          <button
            type="button"
            className={tab === "discover" ? "tab-btn active" : "tab-btn"}
            disabled={!session || !profile}
            onClick={() => setTab("discover")}
          >
            Discover
          </button>
          <button
            type="button"
            className={tab === "validate" ? "tab-btn active" : "tab-btn"}
            disabled={!session || !profile}
            onClick={() => setTab("validate")}
          >
            Validate
          </button>
          <button
            type="button"
            className={tab === "history" ? "tab-btn active" : "tab-btn"}
            disabled={!session}
            onClick={() => {
              setTab("history");
              void refreshIdeas();
            }}
          >
            History &amp; Compare
          </button>
        </nav>
      </header>

      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}

      {tab === "profile" && (
        <AuthProfileView
          isAuthenticated={Boolean(session)}
          userEmail={session?.email || ""}
          profile={profile}
          onAuth={handleAuth}
          onSaveProfile={handleSaveProfile}
        />
      )}

      {tab === "discover" && (
        <section className="card" aria-label="Discover Ideas">
          <h2>Discover Ideas in a Niche</h2>
          <label>
            Niche or topic wish
            <input
              value={nicheWish}
              onChange={(e) => setNicheWish(e.target.value)}
              placeholder="devtools, edtech, healthcare..."
            />
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input
              type="checkbox"
              style={{ width: "auto" }}
              checked={discoverApproval}
              onChange={(e) => setDiscoverApproval(e.target.checked)}
            />
            Simulate over-budget deep search (approval prompt)
          </label>
          <button type="button" className="primary" onClick={() => void handleDiscover()}>
            Run Discover
          </button>
        </section>
      )}

      {tab === "validate" && (
        <section className="card" aria-label="Validate Idea">
          <h2>Validate Your Idea</h2>
          <label>
            Idea Title
            <input
              value={ideaTitle}
              onChange={(e) => setIdeaTitle(e.target.value)}
              placeholder="CI Log Triage Assistant"
            />
          </label>
          <label>
            Idea Description
            <textarea
              rows={3}
              value={ideaText}
              onChange={(e) => setIdeaText(e.target.value)}
              placeholder="Describe problem, target user, and key workflow..."
            />
          </label>
          <label>
            Estimated Build Hours
            <input
              type="number"
              min={1}
              value={buildHours}
              onChange={(e) => setBuildHours(e.target.value)}
            />
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input
              type="checkbox"
              style={{ width: "auto" }}
              checked={needsClarify}
              onChange={(e) => setNeedsClarify(e.target.checked)}
            />
            Ask clarifying question if target segment is ambiguous
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input
              type="checkbox"
              style={{ width: "auto" }}
              checked={thinEvidence}
              onChange={(e) => setThinEvidence(e.target.checked)}
            />
            Simulate thin evidence (INSUFFICIENT_EVIDENCE)
          </label>
          <button type="button" className="primary" onClick={() => void handleValidate()}>
            Validate Idea
          </button>
        </section>
      )}

      {tab === "history" && (
        <HistoryCompareView
          ideas={ideas}
          selectedVersions={selectedVersions}
          comparison={comparison}
          onRefresh={refreshIdeas}
          onSelectVersions={async (ideaId) => {
            if (!session) return;
            const vers = await api.getIdeaVersions(session.access_token, ideaId);
            setSelectedVersions(vers);
          }}
          onCompare={async (left, right) => {
            if (!session) return;
            const res = await api.compareIdeas(session.access_token, left, right);
            setComparison(res);
          }}
        />
      )}

      {activeRun && (tab === "discover" || tab === "validate") && (
        <LiveRunPanel
          run={activeRun}
          onAnswer={handleAnswerRun}
          onApprove={handleApproveRun}
        />
      )}

      {tab === "discover" &&
        discovered.map((item) => (
          <VerdictCard
            key={item.verdict.idea_id}
            title={item.title}
            verdict={item.verdict}
            onChallenge={handleChallenge}
            onApplyWhatIf={handleWhatIf}
          />
        ))}

      {tab === "validate" && activeVerdict && (
        <VerdictCard
          title={ideaTitle || activeVerdict.idea_id}
          verdict={activeVerdict}
          onChallenge={handleChallenge}
          onApplyWhatIf={handleWhatIf}
        />
      )}
    </div>
  );
}
