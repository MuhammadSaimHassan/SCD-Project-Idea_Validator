"""Shared YAML config loader for weights, thresholds, and budgets."""

from pathlib import Path
from typing import Any

import yaml

from shared.schemas import DimensionName, GoalType


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in config file: {path}")
    return data


def load_weights(config_dir: Path) -> dict[GoalType, dict[DimensionName, float]]:
    """Load goal weight presets and verify each preset sums to 100."""
    raw = _load_yaml(config_dir / "weights.yaml")
    goals_raw = raw.get("goals", {})
    parsed: dict[GoalType, dict[DimensionName, float]] = {}
    for goal in GoalType:
        goal_map = goals_raw.get(goal.value)
        if not isinstance(goal_map, dict):
            raise ValueError(f"Missing weights preset for goal: {goal.value}")
        dim_weights = {dim: float(goal_map[dim.value]) for dim in DimensionName}
        total = sum(dim_weights.values())
        if abs(total - 100.0) > 1e-6:
            raise ValueError(f"Weights for {goal.value} must sum to 100, got {total}")
        parsed[goal] = dim_weights
    return parsed


def load_thresholds(config_dir: Path) -> dict[str, Any]:
    """Load verdict thresholds, gates, challenge, and sensitivity settings."""
    return _load_yaml(config_dir / "thresholds.yaml")


def load_budgets(config_dir: Path) -> dict[str, Any]:
    """Load AgenticOps per-run budget caps."""
    return _load_yaml(config_dir / "budgets.yaml")
