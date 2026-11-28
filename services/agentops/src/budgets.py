"""Atomic per-run budget accounting for tokens, pages, steps, and cost."""

from dataclasses import dataclass
from typing import Any


class BudgetLimitExceeded(RuntimeError):
    """Raised when an operation would exceed a hard per-run limit."""


class BudgetApprovalRequired(RuntimeError):
    """Raised when an operation crosses the configured approval threshold."""


@dataclass(frozen=True)
class BudgetUsage:
    tokens: int = 0
    pages_fetched: int = 0
    steps: int = 0
    cost_usd: float = 0.0


class BudgetTracker:
    def __init__(self, config: dict[str, Any]) -> None:
        self._limits = dict(config)
        self._usage = BudgetUsage()

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "BudgetTracker":
        per_run = config.get("per_run")
        if not isinstance(per_run, dict):
            raise ValueError("budgets.yaml must contain a per_run mapping")
        return cls(per_run)

    @property
    def usage(self) -> BudgetUsage:
        return self._usage

    def consume(
        self,
        *,
        tokens: int = 0,
        pages_fetched: int = 0,
        steps: int = 0,
        cost_usd: float = 0.0,
        approved: bool = False,
    ) -> BudgetUsage:
        if min(tokens, pages_fetched, steps) < 0 or cost_usd < 0:
            raise ValueError("Budget usage increments must be non-negative")

        proposed = BudgetUsage(
            tokens=self._usage.tokens + tokens,
            pages_fetched=self._usage.pages_fetched + pages_fetched,
            steps=self._usage.steps + steps,
            cost_usd=round(self._usage.cost_usd + cost_usd, 8),
        )
        hard_limits = (
            ("tokens", proposed.tokens, int(self._limits["max_tokens"])),
            (
                "pages_fetched",
                proposed.pages_fetched,
                int(self._limits["max_pages_fetched"]),
            ),
            ("steps", proposed.steps, int(self._limits["max_steps"])),
            ("cost_usd", proposed.cost_usd, float(self._limits["max_cost_usd"])),
        )
        exceeded = [
            f"{name}={value} > {limit}" for name, value, limit in hard_limits if value > limit
        ]
        if exceeded:
            raise BudgetLimitExceeded("Run stopped at hard budget: " + ", ".join(exceeded))

        approval_limit = float(self._limits["require_approval_over_usd"])
        if proposed.cost_usd > approval_limit and not approved:
            raise BudgetApprovalRequired(
                f"Approval required: projected run cost ${proposed.cost_usd:.4f} "
                f"exceeds ${approval_limit:.4f}"
            )

        self._usage = proposed
        return self._usage
