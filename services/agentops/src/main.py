"""FastAPI entrypoint for M13 AgenticOps."""

import os
from html import escape
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse

from shared.schemas import TraceRecord

from .registry import registry_snapshot
from .store import TraceStore, metrics_snapshot, replay_recorded_results

app = FastAPI(title="M13 AgenticOps", version="0.1.0")
trace_store = TraceStore(Path(os.getenv("AGENTOPS_TRACE_DIR", "data/traces")))
repository_root = Path(__file__).resolve().parents[3]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "agentops"}


@app.get("/ready")
def ready() -> dict[str, str]:
    return {"status": "ready", "service": "agentops"}


@app.post("/trace", response_model=TraceRecord)
def write_trace(record: TraceRecord) -> TraceRecord:
    try:
        trace_store.append(record)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=f"Could not persist trace: {exc}") from exc
    return record


@app.get("/runs/{run_id}/trace", response_model=list[TraceRecord])
def get_trace(run_id: str) -> list[TraceRecord]:
    try:
        return trace_store.list_run(run_id)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/runs/{run_id}/replay")
def replay_run(run_id: str) -> dict[str, Any]:
    try:
        records = trace_store.list_run(run_id)
        if not records:
            raise HTTPException(status_code=404, detail=f"No trace found for run {run_id}")
        return {"run_id": run_id, "steps": replay_recorded_results(records)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/dashboard")
def dashboard() -> HTMLResponse:
    snapshot = metrics_snapshot(trace_store.list_all())
    metric_names = (
        "runs_total",
        "trace_records_total",
        "tokens_total",
        "cost_usd_total",
        "cost_per_verdict_usd",
        "cache_hits_total",
        "fallbacks_total",
        "approvals_total",
        "blocked_injections_total",
        "budget_stops_total",
    )
    rows = "".join(
        f"<tr><th>{escape(name.replace('_', ' ').title())}</th>"
        f"<td>{escape(str(snapshot[name]))}</td></tr>"
        for name in metric_names
    )
    agent_rows = "".join(
        f"<tr><th>{escape(agent)}</th><td>{escape(str(values['latency_ms_average']))} ms</td></tr>"
        for agent, values in snapshot["latency_by_agent"].items()
    )
    html = (
        "<!doctype html><html lang='en'><meta charset='utf-8'>"
        "<title>AgenticOps dashboard</title>"
        "<style>body{font:16px system-ui;margin:2rem;background:#111827;color:#e5e7eb}"
        "table{border-collapse:collapse;min-width:30rem;margin-bottom:2rem}"
        "th,td{text-align:left;padding:.6rem 1rem;border-bottom:1px solid #374151}"
        "th{color:#93c5fd}</style><h1>AgenticOps dashboard</h1>"
        "<h2>Run metrics</h2><table>"
        f"{rows}</table><h2>Average latency by agent</h2><table>"
        f"<tr><th>Agent</th><th>Latency</th></tr>{agent_rows}</table></html>"
    )
    return HTMLResponse(html)


@app.get("/dashboard/data")
def dashboard_data() -> dict[str, Any]:
    return metrics_snapshot(trace_store.list_all())


@app.get("/registry")
def registry() -> dict[str, list[dict[str, Any]]]:
    try:
        return registry_snapshot(repository_root)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=f"Could not load registry: {exc}") from exc


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> str:
    snapshot = metrics_snapshot(trace_store.list_all())
    agent_latency_metrics = []
    for agent, values in snapshot["latency_by_agent"].items():
        escaped_agent = agent.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
        agent_latency_metrics.append(
            f'agentops_agent_latency_ms_average{{agent="{escaped_agent}"}} '
            f"{values['latency_ms_average']}"
        )
    return (
        "\n".join(
            (
                "# HELP agentops_trace_records_total Number of persisted trace records.",
                "# TYPE agentops_trace_records_total counter",
                f"agentops_trace_records_total {snapshot['trace_records_total']}",
                "# HELP agentops_runs_total Number of runs with traces.",
                "# TYPE agentops_runs_total counter",
                f"agentops_runs_total {snapshot['runs_total']}",
                "# HELP agentops_tokens_total Total recorded input and output tokens.",
                "# TYPE agentops_tokens_total counter",
                f"agentops_tokens_total {snapshot['tokens_total']}",
                "# HELP agentops_cost_usd_total Total recorded model and tool cost.",
                "# TYPE agentops_cost_usd_total counter",
                f"agentops_cost_usd_total {snapshot['cost_usd_total']}",
                "# HELP agentops_cost_per_verdict_usd Average run cost for runs with a verdict.",
                "# TYPE agentops_cost_per_verdict_usd gauge",
                f"agentops_cost_per_verdict_usd {snapshot['cost_per_verdict_usd']}",
                "# HELP agentops_latency_ms_total Total recorded latency in milliseconds.",
                "# TYPE agentops_latency_ms_total counter",
                f"agentops_latency_ms_total {snapshot['latency_ms_total']}",
                "# HELP agentops_cache_hits_total Recorded cache hits.",
                "# TYPE agentops_cache_hits_total counter",
                f"agentops_cache_hits_total {snapshot['cache_hits_total']}",
                "# HELP agentops_fallbacks_total Recorded fallback actions.",
                "# TYPE agentops_fallbacks_total counter",
                f"agentops_fallbacks_total {snapshot['fallbacks_total']}",
                "# HELP agentops_approvals_total Recorded approvals.",
                "# TYPE agentops_approvals_total counter",
                f"agentops_approvals_total {snapshot['approvals_total']}",
                "# HELP agentops_budget_stops_total Runs stopped by a configured budget.",
                "# TYPE agentops_budget_stops_total counter",
                f"agentops_budget_stops_total {snapshot['budget_stops_total']}",
                "# HELP agentops_errors_total Recorded errors.",
                "# TYPE agentops_errors_total counter",
                f"agentops_errors_total {snapshot['errors_total']}",
                "# HELP agentops_blocked_injections_total Blocked injection attempts.",
                "# TYPE agentops_blocked_injections_total counter",
                f"agentops_blocked_injections_total {snapshot['blocked_injections_total']}",
                *agent_latency_metrics,
            )
        )
        + "\n"
    )
