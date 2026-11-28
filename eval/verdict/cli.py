"""Single-command human-labelled verdict evaluation and tuning."""

import argparse
import json
from pathlib import Path

from .harness import run_evaluation


def main() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(prog="verdict-eval")
    parser.add_argument(
        "--dataset", type=Path, default=repository_root / "eval/verdict/labeled_ideas.jsonl"
    )
    parser.add_argument("--config-dir", type=Path, default=repository_root / "config")
    parser.add_argument(
        "--output",
        type=Path,
        default=repository_root / "eval/results/verdict_tuning.json",
    )
    parser.add_argument(
        "--finetune-data",
        type=Path,
        nargs="+",
        default=[
            repository_root / "jobs/finetune/data/train.jsonl",
            repository_root / "jobs/finetune/data/eval_checked.jsonl",
        ],
    )
    parser.add_argument(
        "--trace-dir",
        type=Path,
        default=repository_root / "data/traces",
        help="M13 JSONL trace directory used by behavioral checks",
    )
    parser.add_argument(
        "--write-config",
        action="store_true",
        help="Replace config/weights.yaml and config/thresholds.yaml with training-tuned values",
    )
    args = parser.parse_args()

    report = run_evaluation(
        args.dataset,
        args.config_dir,
        args.output,
        args.finetune_data,
        args.trace_dir,
        write_production_config=args.write_config,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
