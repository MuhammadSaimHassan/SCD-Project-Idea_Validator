"""Command-line entrypoints for M3."""

import argparse
import json
from pathlib import Path

from services.agentops.src.budgets import BudgetApprovalRequired
from shared.schemas import StudentProfile

from .state_machine import Orchestrator


def main() -> None:
    parser = argparse.ArgumentParser(prog="orchestrator")
    subparsers = parser.add_subparsers(dest="workflow", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("idea")
    validate.add_argument("--profile", required=True)
    discover = subparsers.add_parser("discover")
    discover.add_argument("--profile", required=True)
    discover.add_argument("--max-ideas", type=int, default=5)
    args = parser.parse_args()

    config_dir = Path.cwd() / "config"
    snapshot = Path("data/snapshot/cards.jsonl")
    profile = StudentProfile.model_validate_json(Path(args.profile).read_text(encoding="utf-8-sig"))
    orchestrator = Orchestrator(config_dir=config_dir, snapshot_path=snapshot)
    try:
        if args.workflow == "validate":
            print(orchestrator.validate(args.idea, profile).model_dump_json(indent=2))
        else:
            print(json.dumps(orchestrator.discover(profile, args.max_ideas), indent=2))
    except BudgetApprovalRequired as exc:
        print(json.dumps({"status": "awaiting_approval", "message": str(exc)}))


if __name__ == "__main__":
    main()
