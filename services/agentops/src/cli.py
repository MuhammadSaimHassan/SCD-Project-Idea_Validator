"""AgenticOps trace replay command."""

import argparse
import json
from pathlib import Path

from .store import TraceStore, replay_recorded_results


def main() -> None:
    parser = argparse.ArgumentParser(prog="agentops")
    subparsers = parser.add_subparsers(dest="command", required=True)
    replay_parser = subparsers.add_parser("replay")
    replay_parser.add_argument("run_id")
    replay_parser.add_argument("--trace-dir", type=Path, default=Path("data/traces"))
    args = parser.parse_args()

    records = TraceStore(args.trace_dir).list_run(args.run_id)
    if not records:
        parser.error(f"No trace found for run {args.run_id}")
    print(json.dumps(replay_recorded_results(records), indent=2, default=str))


if __name__ == "__main__":
    main()
