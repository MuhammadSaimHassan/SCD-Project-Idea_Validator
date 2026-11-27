import { useState } from "react";
import type { CompareIdeasResult, DimensionKey, IdeaSummary, IdeaVersionEntry } from "../types";

interface HistoryCompareViewProps {
  ideas: IdeaSummary[];
  selectedVersions: IdeaVersionEntry[];
  comparison: CompareIdeasResult | null;
  onRefresh: () => Promise<void>;
  onSelectVersions: (ideaId: string) => Promise<void>;
  onCompare: (leftId: string, rightId: string) => Promise<void>;
}

const DIMENSIONS: DimensionKey[] = [
  "demand_pain",
  "competition",
  "differentiation",
  "feasibility",
  "risk",
  "learning",
];

export function HistoryCompareView({
  ideas,
  selectedVersions,
  comparison,
  onRefresh,
  onSelectVersions,
  onCompare,
}: HistoryCompareViewProps) {
  const [leftId, setLeftId] = useState(ideas[0]?.idea_id || "");
  const [rightId, setRightId] = useState(ideas[1]?.idea_id || ideas[0]?.idea_id || "");

  return (
    <section className="card" aria-label="History and Comparison">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>Past Ideas, Versions &amp; Comparison</h2>
        <button type="button" onClick={() => void onRefresh()}>
          Refresh List
        </button>
      </div>

      {ideas.length === 0 ? (
        <p className="muted">No saved ideas yet. Run Discover or Validate first.</p>
      ) : (
        <>
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Source</th>
                <th>Latest Version</th>
                <th>Verdict</th>
                <th>Score</th>
                <th>Versions</th>
              </tr>
            </thead>
            <tbody>
              {ideas.map((item) => (
                <tr key={item.idea_id}>
                  <td>{item.title}</td>
                  <td>{item.source}</td>
                  <td>v{item.latest_version}</td>
                  <td>
                    {item.latest_verdict ? (
                      <span className={`badge ${item.latest_verdict.verdict}`}>
                        {item.latest_verdict.verdict}
                      </span>
                    ) : (
                      "-"
                    )}
                  </td>
                  <td>{item.latest_verdict ? item.latest_verdict.score.toFixed(1) : "-"}</td>
                  <td>
                    <button type="button" onClick={() => void onSelectVersions(item.idea_id)}>
                      View Versions
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {selectedVersions.length > 0 && (
            <div className="card" style={{ marginTop: 14 }}>
              <h3>Version History</h3>
              <ul>
                {selectedVersions.map((v) => (
                  <li key={v.version}>
                    <strong>v{v.version}</strong>:{" "}
                    {v.verdict ? `${v.verdict.verdict} (${v.verdict.score.toFixed(1)})` : "Pending"}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {ideas.length >= 2 && (
            <div className="card" style={{ marginTop: 14 }}>
              <h3>Compare Two Ideas Across All 6 Dimensions</h3>
              <div className="grid-2">
                <label>
                  Left Idea
                  <select
                    value={leftId || ideas[0]?.idea_id}
                    onChange={(e) => setLeftId(e.target.value)}
                  >
                    {ideas.map((i) => (
                      <option key={i.idea_id} value={i.idea_id}>
                        {i.title}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Right Idea
                  <select
                    value={rightId || ideas[1]?.idea_id}
                    onChange={(e) => setRightId(e.target.value)}
                  >
                    {ideas.map((i) => (
                      <option key={i.idea_id} value={i.idea_id}>
                        {i.title}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <button
                type="button"
                className="primary"
                onClick={() =>
                  void onCompare(
                    leftId || ideas[0].idea_id,
                    rightId || ideas[1].idea_id
                  )
                }
              >
                Compare Ideas
              </button>
            </div>
          )}
        </>
      )}

      {comparison && (
        <div className="card" style={{ marginTop: 14 }} aria-label="Comparison Table">
          <h3>
            {comparison.left.title} vs {comparison.right.title}
          </h3>
          <table>
            <thead>
              <tr>
                <th>Dimension</th>
                <th>{comparison.left.title}</th>
                <th>{comparison.right.title}</th>
                <th>Delta</th>
              </tr>
            </thead>
            <tbody>
              {DIMENSIONS.map((dim) => {
                const lScore = comparison.left.latest_verdict?.scores.find(
                  (s) => s.dimension === dim
                )?.score;
                const rScore = comparison.right.latest_verdict?.scores.find(
                  (s) => s.dimension === dim
                )?.score;
                return (
                  <tr key={dim}>
                    <td>{dim}</td>
                    <td>{lScore?.toFixed(1) ?? "-"}</td>
                    <td>{rScore?.toFixed(1) ?? "-"}</td>
                    <td>{comparison.dimension_deltas[dim]?.toFixed(1) ?? "-"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
