"""CLI to compare the current knowledge snapshot with its previous version."""

import argparse
import json
from pathlib import Path

from services.analyst.src.analyzer import load_cards
from shared.schemas import Verdict, VerdictLabel

from .drift import build_drift_report


def _load_verdict_labels(path: Path | None) -> list[VerdictLabel] | None:
    if path is None:
        return None
    labels: list[VerdictLabel] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if line.strip():
                try:
                    labels.append(Verdict.model_validate_json(line).verdict)
                except ValueError as exc:
                    raise ValueError(f"Invalid verdict JSONL at {path}:{line_number}") from exc
    return labels


def main() -> None:
    parser = argparse.ArgumentParser(prog="agentops-drift")
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--previous-verdicts", type=Path)
    parser.add_argument("--current-verdicts", type=Path)
    parser.add_argument("--output", type=Path, default=Path("eval/results/drift_report.json"))
    args = parser.parse_args()
    if bool(args.previous_verdicts) != bool(args.current_verdicts):
        parser.error("Pass both verdict files or neither")

    report = build_drift_report(
        load_cards(args.previous),
        load_cards(args.current),
        _load_verdict_labels(args.previous_verdicts),
        _load_verdict_labels(args.current_verdicts),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
