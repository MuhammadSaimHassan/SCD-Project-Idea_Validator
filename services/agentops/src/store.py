"""Append-only JSONL trace storage and deterministic recorded-result replay."""

import re
import threading
from pathlib import Path
from typing import Any

from services.verdict.src.engine import evaluate_verdict
from shared.schemas import DimensionName, GoalType, TraceKind, TraceRecord, VerdictRequest

RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
VERDICT_REPLAY_KEYS = {
    "verdict_request",
    "weights",
    "thresholds",
    "weights_version",
    "rubrics_version",
}


class TraceStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, run_id: str) -> Path:
        if not RUN_ID_PATTERN.fullmatch(run_id):
            raise ValueError("run_id contains invalid characters")
        return self.directory / f"{run_id}.jsonl"

    def append(self, record: TraceRecord) -> None:
        path = self._path(record.run_id)
        with self._lock, path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(record.model_dump_json() + "\n")

    def list_run(self, run_id: str) -> list[TraceRecord]:
        path = self._path(run_id)
        if not path.exists():
            return []
        records: list[TraceRecord] = []
        with path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(TraceRecord.model_validate_json(line))
                except ValueError as exc:
                    raise ValueError(f"Invalid trace JSONL at {path}:{line_number}") from exc
        return records

    def list_all(self) -> list[TraceRecord]:
        records: list[TraceRecord] = []
        for path in sorted(self.directory.glob("*.jsonl")):
            records.extend(self.list_run(path.stem))
        return records


def replay_recorded_results(records: list[TraceRecord]) -> list[dict[str, Any]]:
    """Replay recorded tool results and rerun M11 from its captured input/config."""
    ordered = sorted(records, key=lambda record: record.step_id)
    if not ordered:
        return []
    run_ids = {record.run_id for record in ordered}
    if len(run_ids) != 1:
        raise ValueError("Replay input must contain records from exactly one run")

    replay: list[dict[str, Any]] = []
    for record in ordered:
        output = record.output
        rerun_result: dict[str, Any] | None = None
        matched_recorded_output: bool | None = None
        if (
            record.tool == "evaluate_verdict"
            and isinstance(record.input, dict)
            and VERDICT_REPLAY_KEYS.issubset(record.input)
        ):
            rerun_result = _replay_verdict(record.input)
            matched_recorded_output = rerun_result == record.output
            output = rerun_result
        replay.append(
            {
                "step_id": record.step_id,
                "agent": record.agent,
                "kind": record.kind.value,
                "tool": record.tool,
                "input": record.input,
                "output": output,
                "used_recorded_result": record.kind == TraceKind.TOOL_CALL,
                "reran_deterministic_verdict": rerun_result is not None,
                "matches_recorded_output": matched_recorded_output,
                "error": record.error,
            }
        )
    return replay


def _replay_verdict(payload: dict[str, Any]) -> dict[str, Any]:
    if not VERDICT_REPLAY_KEYS.issubset(payload):
        raise ValueError("Verdict replay record is missing its input/config snapshot")
    request = VerdictRequest.model_validate(payload["verdict_request"])
    weights = {
        GoalType(goal): {
            DimensionName(dimension): float(value)
            for dimension, value in goal_weights.items()
        }
        for goal, goal_weights in payload["weights"].items()
    }
    result = evaluate_verdict(
        request,
        weights_by_goal=weights,
        thresholds=payload["thresholds"],
        weights_version=str(payload["weights_version"]),
        rubrics_version=str(payload["rubrics_version"]),
    )
    return result.model_dump(mode="json")


def metrics_snapshot(records: list[TraceRecord]) -> dict[str, Any]:
    latency_by_agent: dict[str, dict[str, int | float]] = {}
    for record in records:
        aggregate = latency_by_agent.setdefault(record.agent, {"latency_ms": 0, "calls": 0})
        aggregate["latency_ms"] += record.latency_ms
        aggregate["calls"] += 1
    latency_by_agent = {
        agent: {
            "calls": values["calls"],
            "latency_ms_total": values["latency_ms"],
            "latency_ms_average": round(values["latency_ms"] / values["calls"], 2),
        }
        for agent, values in sorted(latency_by_agent.items())
    }
    verdict_runs = {
        record.run_id
        for record in records
        if record.agent == "verdict_engine" and record.tool == "evaluate_verdict"
    }
    cost_for_verdict_runs = sum(
        record.cost_usd for record in records if record.run_id in verdict_runs
    )
    fallback_count = sum(
        (record.model is not None and "fallback" in record.model.casefold())
        or (isinstance(record.output, dict) and bool(record.output.get("fallback")))
        for record in records
    )
    approvals = sum(
        record.tool in {"approval", "budget_approval"}
        or (isinstance(record.output, dict) and "approved" in record.output)
        for record in records
    )
    return {
        "trace_records_total": len(records),
        "runs_total": len({record.run_id for record in records}),
        "tokens_total": sum(record.tokens_in + record.tokens_out for record in records),
        "cost_usd_total": round(sum(record.cost_usd for record in records), 8),
        "cost_per_verdict_usd": round(
            cost_for_verdict_runs / len(verdict_runs) if verdict_runs else 0.0, 8
        ),
        "latency_ms_total": sum(record.latency_ms for record in records),
        "latency_by_agent": latency_by_agent,
        "cache_hits_total": sum(record.cache_hit for record in records),
        "fallbacks_total": fallback_count,
        "approvals_total": approvals,
        "errors_total": sum(record.error is not None for record in records),
        "budget_stops_total": sum(
            record.error is not None
            and ("budget" in record.error.casefold() or "approval" in record.error.casefold())
            for record in records
        ),
        "blocked_injections_total": sum(
            isinstance(record.output, dict) and bool(record.output.get("blocked_injection"))
            for record in records
        ),
    }
