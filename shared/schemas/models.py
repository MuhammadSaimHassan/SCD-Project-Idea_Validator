"""Core domain schemas matching Project_Guide.pdf Section 2."""

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ComputeTier(StrEnum):
    LAPTOP = "laptop"
    FREE_GPU = "free_gpu"
    PAID = "paid"


class GoalType(StrEnum):
    STARTUP = "startup"
    PORTFOLIO = "portfolio"
    COURSE_PROJECT = "course_project"


class DimensionName(StrEnum):
    DEMAND_PAIN = "demand_pain"
    COMPETITION = "competition"
    DIFFERENTIATION = "differentiation"
    FEASIBILITY = "feasibility"
    RISK = "risk"
    LEARNING = "learning"


class VerdictLabel(StrEnum):
    GO = "GO"
    PIVOT = "PIVOT"
    NO_GO = "NO-GO"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class StabilityLabel(StrEnum):
    STABLE = "STABLE"
    BORDERLINE = "BORDERLINE"


class GateStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"


class TraceKind(StrEnum):
    TOOL_CALL = "tool_call"
    LLM_CALL = "llm_call"
    DECISION = "decision"


class IdeaCard(BaseModel):
    """Normalized startup/product idea card stored in M6."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    summary: str
    problem: str
    customer: str
    niche_tags: list[str] = Field(default_factory=list)
    stage: str = "unknown"
    funding_usd: int | None = Field(default=None, ge=0)
    source: str = Field(..., min_length=1)
    url: str = Field(..., min_length=1)
    published_at: date | str | None = None
    fetched_at: date | datetime | str
    text: str = Field(..., min_length=1)


class StudentProfile(BaseModel):
    """Student profile stored in M2 and used for personalized feasibility/weights."""

    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(..., min_length=1)
    skills: list[str] = Field(default_factory=list)
    hours_per_week: float = Field(..., gt=0)
    weeks_available: float = Field(..., gt=0)
    team_size: int = Field(..., ge=1)
    compute: ComputeTier = ComputeTier.LAPTOP
    goal: GoalType
    interests: list[str] = Field(default_factory=list)
    profile_version: int = Field(default=1, ge=1)


class EvidenceItem(BaseModel):
    """Retrieved evidence snippet from M6 with traceable card citation."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(..., min_length=1, description="Format: <card_id>#c<chunk>")
    card_id: str = Field(..., min_length=1)
    quote: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)
    url: str = Field(..., min_length=1)
    retrieved_at: datetime | str


class DimensionScore(BaseModel):
    """Single dimension score emitted by M9 scorers using M10."""

    model_config = ConfigDict(extra="forbid")

    dimension: DimensionName
    score: float = Field(..., ge=0.0, le=5.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    features: dict[str, float | int | str | bool] = Field(default_factory=dict)
    reason: str
    rubric_version: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    abstained: bool = False


class GatesResult(BaseModel):
    """Hard gate evaluations performed before weighted scoring in M11."""

    model_config = ConfigDict(extra="forbid")

    evidence: GateStatus
    feasibility: GateStatus
    risk: GateStatus
    duplicate: GateStatus
    failure_reasons: dict[str, str] = Field(default_factory=dict)


class WhatIfSuggestion(BaseModel):
    """Smallest proposed change that changes a verdict toward GO."""

    model_config = ConfigDict(extra="forbid")

    change: str
    dimension: DimensionName | None = None
    target_score: float | None = Field(default=None, ge=0.0, le=5.0)
    new_score: float = Field(..., ge=0.0, le=100.0)
    new_verdict: VerdictLabel


class SensitivityResult(BaseModel):
    """Summary of weight +/-20% and least-confident score +/-1 perturbations."""

    model_config = ConfigDict(extra="forbid")

    runs: int = Field(..., ge=0)
    flipped: int = Field(..., ge=0)
    flip_triggers: list[str] = Field(default_factory=list)


class VerdictVersions(BaseModel):
    """Version stamp recorded on every verdict for reproducibility and cache keys."""

    model_config = ConfigDict(extra="forbid")

    engine: str
    rubrics: str
    profile_weights: str


class Verdict(BaseModel):
    """Deterministic verdict output from M11."""

    model_config = ConfigDict(extra="forbid")

    idea_id: str = Field(..., min_length=1)
    version: int = Field(..., ge=1)
    run_id: str = Field(..., min_length=1)
    verdict: VerdictLabel
    stability: StabilityLabel
    score: float = Field(..., ge=0.0, le=100.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    gates: GatesResult
    weights: dict[DimensionName, float]
    thresholds: dict[str, float]
    scores: list[DimensionScore]
    weakest_dimension: DimensionName | None = None
    what_would_make_go: list[WhatIfSuggestion] = Field(default_factory=list)
    sensitivity: SensitivityResult
    versions: VerdictVersions
    insufficient_reasons: list[str] = Field(default_factory=list)


class TraceRecord(BaseModel):
    """AgenticOps trace record written to M13 for every step."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(..., min_length=1)
    step_id: int = Field(..., ge=1)
    parent_step: int | None = Field(default=None, ge=1)
    agent: str = Field(..., min_length=1)
    kind: TraceKind
    tool: str | None = None
    input: Any = None
    output: Any = None
    tokens_in: int = Field(default=0, ge=0)
    tokens_out: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0.0)
    latency_ms: int = Field(default=0, ge=0)
    retries: int = Field(default=0, ge=0)
    model: str | None = None
    cache_hit: bool = False
    error: str | None = None
    ts: datetime | str
