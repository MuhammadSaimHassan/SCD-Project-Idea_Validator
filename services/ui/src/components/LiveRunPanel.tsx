import { useState } from "react";
import type { RunStatus } from "../types";

interface LiveRunPanelProps {
  run: RunStatus;
  onAnswer: (runId: string, answer: string) => Promise<void>;
  onApprove: (runId: string, approved: boolean) => Promise<void>;
}

export function LiveRunPanel({ run, onAnswer, onApprove }: LiveRunPanelProps) {
  const [answerText, setAnswerText] = useState("");
  const totalSpend = run.events.reduce((acc, ev) => acc + (ev.spend_usd || 0), 0);

  return (
    <section className="card" aria-label="Live Agent Progress">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3>
          Live Agents — Run <code>{run.run_id}</code> ({run.workflow})
        </h3>
        <span className="badge STABLE">
          {run.status} | Spend: ${totalSpend.toFixed(3)}
        </span>
      </div>

      <table>
        <thead>
          <tr>
            <th>Step</th>
            <th>Agent</th>
            <th>Tool</th>
            <th>Spend</th>
            <th>Details</th>
          </tr>
        </thead>
        <tbody>
          {run.events.map((ev) => (
            <tr key={`${ev.step}-${ev.agent}`}>
              <td>{ev.step}</td>
              <td>{ev.agent}</td>
              <td>
                <code>{ev.tool}</code>
              </td>
              <td>${ev.spend_usd.toFixed(3)}</td>
              <td>{ev.message}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {run.status === "awaiting_answer" && run.pending_question && (
        <div className="warning-box" style={{ marginTop: 12 }}>
          <strong>Clarifying Question (affects verdict):</strong>
          <p>{run.pending_question.question}</p>
          <div style={{ display: "flex", gap: 8 }}>
            <input
              aria-label="Clarifying answer"
              value={answerText}
              onChange={(e) => setAnswerText(e.target.value)}
              placeholder="Enter concise answer..."
            />
            <button
              type="button"
              className="primary"
              onClick={() => void onAnswer(run.run_id, answerText)}
            >
              Submit Answer
            </button>
          </div>
        </div>
      )}

      {run.status === "awaiting_approval" && run.pending_approval && (
        <div className="warning-box" style={{ marginTop: 12 }}>
          <strong>Budget Approval Required</strong>
          <p>{run.pending_approval.message}</p>
          <p className="muted">
            Action: <code>{run.pending_approval.action}</code> | Estimated cost: $
            {run.pending_approval.estimated_cost_usd.toFixed(2)}
          </p>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="button"
              className="primary"
              onClick={() => void onApprove(run.run_id, true)}
            >
              Approve Deep Search
            </button>
            <button
              type="button"
              className="danger"
              onClick={() => void onApprove(run.run_id, false)}
            >
              Decline & Stop
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
