import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App from "../App";
import { AuthProfileView } from "../components/AuthProfileView";
import { HistoryCompareView } from "../components/HistoryCompareView";
import { LiveRunPanel } from "../components/LiveRunPanel";
import { VerdictCard } from "../components/VerdictCard";
import type { Verdict } from "../types";

const SAMPLE_VERDICT: Verdict = {
  idea_id: "idea_5",
  version: 1,
  run_id: "run_90",
  verdict: "GO",
  stability: "BORDERLINE",
  score: 70.5,
  confidence: 0.74,
  gates: {
    evidence: "pass",
    feasibility: "pass",
    risk: "pass",
    duplicate: "pass",
    failure_reasons: {},
  },
  weights: {
    demand_pain: 15,
    competition: 15,
    differentiation: 15,
    feasibility: 25,
    risk: 10,
    learning: 20,
  },
  thresholds: { T_go: 70, T_no: 50, floor: 1.5 },
  scores: [
    {
      dimension: "demand_pain",
      score: 3.5,
      confidence: 0.8,
      evidence_ids: ["card_8f21#c2"],
      features: { n_sources: 4 },
      reason: "Recurring pain cited in card_8f21#c2",
      rubric_version: "demand_pain@v1",
      model: "scorer-lora@v1",
    },
    {
      dimension: "competition",
      score: 2.0,
      confidence: 0.7,
      evidence_ids: ["card_10#c0"],
      features: { n_sources: 3 },
      reason: "Several adjacent tools exist",
      rubric_version: "competition@v1",
      model: "scorer-lora@v1",
    },
    {
      dimension: "differentiation",
      score: 3.0,
      confidence: 0.75,
      evidence_ids: ["card_11#c0"],
      features: {},
      reason: "Clear local-first wedge",
      rubric_version: "differentiation@v1",
      model: "scorer-lora@v1",
    },
    {
      dimension: "feasibility",
      score: 4.0,
      confidence: 0.85,
      evidence_ids: ["card_12#c0"],
      features: {},
      reason: "Fits student hours",
      rubric_version: "feasibility@v1",
      model: "scorer-lora@v1",
    },
    {
      dimension: "risk",
      score: 3.5,
      confidence: 0.8,
      evidence_ids: ["card_13#c0"],
      features: {},
      reason: "Official APIs only",
      rubric_version: "risk@v1",
      model: "scorer-lora@v1",
    },
    {
      dimension: "learning",
      score: 4.5,
      confidence: 0.9,
      evidence_ids: ["card_14#c0"],
      features: {},
      reason: "Strong portfolio value",
      rubric_version: "learning@v1",
      model: "scorer-lora@v1",
    },
  ],
  weakest_dimension: "competition",
  what_would_make_go: [
    {
      change: "Raise competition from 2.0 to 3.0 (stable GO)",
      dimension: "competition",
      target_score: 3.0,
      new_score: 73.5,
      new_verdict: "GO",
    },
  ],
  sensitivity: {
    runs: 14,
    flipped: 1,
    flip_triggers: ["weight(feasibility -20%): GO->PIVOT (69.9)"],
  },
  versions: {
    engine: "m11@v1",
    rubrics: "r1",
    profile_weights: "w1",
  },
  insufficient_reasons: [],
};

describe("Idea Validator UI Components", () => {
  it("renders navigation and authentication screen initially", () => {
    render(<App />);
    expect(screen.getByText(/Idea Generator with Go \/ No-Go/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Create Account/i })).toBeInTheDocument();
  });

  it("submits student profile form (U1)", () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <AuthProfileView
        isAuthenticated={true}
        userEmail="student@nu.edu.pk"
        profile={{
          user_id: "u_1",
          skills: ["python", "react"],
          hours_per_week: 12,
          weeks_available: 10,
          team_size: 2,
          compute: "laptop",
          goal: "portfolio",
          interests: ["devtools"],
          profile_version: 2,
        }}
        onAuth={vi.fn()}
        onSaveProfile={onSave}
      />
    );
    expect(screen.getByText(/Profile v2/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Save Profile/i }));
    expect(onSave).toHaveBeenCalledTimes(1);
  });

  it("renders verdict card with gates, scores, evidence, challenge, and what-if (U6-U8)", () => {
    const onChallenge = vi.fn().mockResolvedValue(undefined);
    const onWhatIf = vi.fn().mockResolvedValue(undefined);
    render(
      <VerdictCard
        title="CI Log Triage"
        verdict={SAMPLE_VERDICT}
        onChallenge={onChallenge}
        onApplyWhatIf={onWhatIf}
      />
    );

    expect(screen.getByText("70.5 / 100")).toBeInTheDocument();
    expect(screen.getByText("BORDERLINE")).toBeInTheDocument();
    expect(screen.getByText("card_8f21#c2")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Apply Change/i }));
    expect(onWhatIf).toHaveBeenCalledWith("idea_5", { competition: 3.0 });

    const challengeButtons = screen.getAllByRole("button", { name: "Challenge" });
    fireEvent.click(challengeButtons[0]);
    fireEvent.click(screen.getByRole("button", { name: /Run Critic Re-check/i }));
    expect(onChallenge).toHaveBeenCalledTimes(1);
  });

  it("renders INSUFFICIENT_EVIDENCE explanation without guessing (U10)", () => {
    render(
      <VerdictCard
        verdict={{
          ...SAMPLE_VERDICT,
          verdict: "INSUFFICIENT_EVIDENCE",
          insufficient_reasons: ["Need >= 3 sources across >= 2 platforms"],
        }}
      />
    );
    expect(
      screen.getByText(/System Abstained Instead of Guessing/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Need >= 3 sources across >= 2 platforms/i)
    ).toBeInTheDocument();
  });

  it("renders live agent spend and approval prompt (U3, U4)", () => {
    const onApprove = vi.fn().mockResolvedValue(undefined);
    render(
      <LiveRunPanel
        run={{
          run_id: "run_1",
          workflow: "discover",
          status: "awaiting_approval",
          events: [
            {
              step: 1,
              agent: "budget_guard",
              tool: "deep_scout_check",
              spend_usd: 0.12,
              message: "Over budget",
              ts: "2026-11-28T00:00:00Z",
            },
          ],
          pending_question: null,
          pending_approval: {
            action: "deep_search",
            estimated_cost_usd: 0.12,
            message: "Approve extra external scouting?",
          },
          result: null,
        }}
        onAnswer={vi.fn()}
        onApprove={onApprove}
      />
    );

    expect(screen.getByText(/Spend: \$0.120/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Approve Deep Search/i }));
    expect(onApprove).toHaveBeenCalledWith("run_1", true);
  });

  it("renders 6-dimension comparison table (U9)", () => {
    render(
      <HistoryCompareView
        ideas={[
          {
            idea_id: "i1",
            title: "Alpha",
            source: "own",
            latest_version: 1,
            latest_verdict: SAMPLE_VERDICT,
          },
          {
            idea_id: "i2",
            title: "Beta",
            source: "generated",
            latest_version: 1,
            latest_verdict: { ...SAMPLE_VERDICT, idea_id: "i2", score: 65.0 },
          },
        ]}
        selectedVersions={[]}
        comparison={{
          left: {
            idea_id: "i1",
            title: "Alpha",
            source: "own",
            latest_version: 1,
            latest_verdict: SAMPLE_VERDICT,
          },
          right: {
            idea_id: "i2",
            title: "Beta",
            source: "generated",
            latest_version: 1,
            latest_verdict: SAMPLE_VERDICT,
          },
          dimension_deltas: {
            demand_pain: 0.5,
            competition: -0.5,
            differentiation: 0,
            feasibility: 1,
            risk: 0,
            learning: 0,
          },
        }}
        onRefresh={vi.fn()}
        onSelectVersions={vi.fn()}
        onCompare={vi.fn()}
      />
    );
    expect(screen.getByLabelText("Comparison Table")).toBeInTheDocument();
    expect(screen.getByText("demand_pain")).toBeInTheDocument();
  });
});
