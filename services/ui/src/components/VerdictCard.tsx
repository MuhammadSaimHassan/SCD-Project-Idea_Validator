import { useState } from "react";
import type { DimensionKey, Verdict } from "../types";

interface VerdictCardProps {
  verdict: Verdict;
  title?: string;
  onChallenge?: (ideaId: string, dimension: DimensionKey, claim: string) => Promise<void>;
  onApplyWhatIf?: (
    ideaId: string,
    override: Partial<Record<DimensionKey, number>>
  ) => Promise<void>;
}

const DIMENSION_LABELS: Record<DimensionKey, string> = {
  demand_pain: "Demand & Pain",
  competition: "Competition",
  differentiation: "Differentiation",
  feasibility: "Feasibility",
  risk: "Risk",
  learning: "Learning & Portfolio",
};

export function VerdictCard({
  verdict,
  title,
  onChallenge,
  onApplyWhatIf,
}: VerdictCardProps) {
  const [challengeDim, setChallengeDim] = useState<DimensionKey | null>(null);
  const [challengeClaim, setChallengeClaim] = useState("");

  const gateEntries = [
    ["Evidence", verdict.gates.evidence, verdict.gates.failure_reasons.evidence],
    ["Feasibility", verdict.gates.feasibility, verdict.gates.failure_reasons.feasibility],
    ["Risk", verdict.gates.risk, verdict.gates.failure_reasons.risk],
    ["Duplicate", verdict.gates.duplicate, verdict.gates.failure_reasons.duplicate],
  ] as const;

  return (
    <article className="card" aria-label="Verdict Card">
      <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
        <div>
          <h3 style={{ margin: "0 0 6px" }}>
            {title || verdict.idea_id}{" "}
            <span className="muted">(Version {verdict.version})</span>
          </h3>
          <span className="muted">
            Engine: {verdict.versions.engine} | Rubrics: {verdict.versions.rubrics} | Weights:{" "}
            {verdict.versions.profile_weights}
          </span>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span className={`badge ${verdict.verdict}`}>{verdict.verdict}</span>
          <span className={`badge ${verdict.stability}`}>{verdict.stability}</span>
          <strong>
            {verdict.score.toFixed(1)} / 100
          </strong>
          <span className="muted">Conf: {(verdict.confidence * 100).toFixed(0)}%</span>
        </div>
      </div>

      {verdict.verdict === "INSUFFICIENT_EVIDENCE" && (
        <div className="warning-box" role="status">
          <strong>Insufficient Evidence — System Abstained Instead of Guessing</strong>
          <ul>
            {verdict.insufficient_reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      )}

      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, margin: "12px 0" }}>
        {gateEntries.map(([name, status, reason]) => (
          <span key={name} className={`badge ${status}`} title={reason || ""}>
            {name}: {status.toUpperCase()}
            {reason ? ` (${reason})` : ""}
          </span>
        ))}
      </div>

      <table>
        <thead>
          <tr>
            <th>Dimension</th>
            <th>Score</th>
            <th>Weight</th>
            <th>Evidence & Reason</th>
            {onChallenge && <th>Action</th>}
          </tr>
        </thead>
        <tbody>
          {verdict.scores.map((item) => (
            <tr key={item.dimension}>
              <td>
                <strong>{DIMENSION_LABELS[item.dimension]}</strong>
                <div className="muted">Conf {(item.confidence * 100).toFixed(0)}%</div>
              </td>
              <td>{item.score.toFixed(1)} / 5</td>
              <td>{verdict.weights[item.dimension]}%</td>
              <td>
                <div>{item.reason}</div>
                <div>
                  {item.evidence_ids.map((eid) => (
                    <span key={eid} className="evidence-chip">
                      {eid}
                    </span>
                  ))}
                </div>
              </td>
              {onChallenge && (
                <td>
                  <button
                    type="button"
                    onClick={() => {
                      setChallengeDim(item.dimension);
                      setChallengeClaim(`Challenge ${item.dimension} evidence`);
                    }}
                  >
                    Challenge
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>

      {challengeDim && onChallenge && (
        <div className="warning-box" style={{ marginTop: 12 }}>
          <strong>Challenge {DIMENSION_LABELS[challengeDim]}</strong>
          <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
            <input
              aria-label="Challenge claim"
              value={challengeClaim}
              onChange={(e) => setChallengeClaim(e.target.value)}
            />
            <button
              type="button"
              className="primary"
              onClick={() => {
                void onChallenge(verdict.idea_id, challengeDim, challengeClaim);
                setChallengeDim(null);
              }}
            >
              Run Critic Re-check
            </button>
            <button type="button" onClick={() => setChallengeDim(null)}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {verdict.sensitivity.runs > 0 && (
        <p className="muted" style={{ marginTop: 12 }}>
          Sensitivity: {verdict.sensitivity.flipped} / {verdict.sensitivity.runs} perturbations
          flipped verdict.{" "}
          {verdict.sensitivity.flip_triggers.length > 0 &&
            `Triggers: ${verdict.sensitivity.flip_triggers.join("; ")}`}
        </p>
      )}

      {verdict.what_would_make_go.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <strong>What would make this GO?</strong>
          <ul>
            {verdict.what_would_make_go.map((s) => (
              <li key={s.change} style={{ marginBottom: 6 }}>
                <span>
                  {s.change} -&gt; {s.new_score.toFixed(1)} ({s.new_verdict})
                </span>{" "}
                {onApplyWhatIf && s.dimension && s.target_score !== null && (
                  <button
                    type="button"
                    className="primary"
                    onClick={() =>
                      void onApplyWhatIf(verdict.idea_id, {
                        [s.dimension as DimensionKey]: s.target_score as number,
                      })
                    }
                  >
                    Apply Change (New Version)
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}
