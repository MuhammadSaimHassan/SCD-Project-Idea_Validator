"""Internal service-to-service API request and response schemas."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .models import (
    DimensionName,
    DimensionScore,
    EvidenceItem,
    StudentProfile,
)


class FetchRequest(BaseModel):
    """M5 POST /fetch request."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(..., min_length=1)
    url: str = Field(..., min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    run_id: str | None = None


class FetchResponse(BaseModel):
    """M5 POST /fetch response after allow-list, rate limit, cache, and sanitiser."""

    model_config = ConfigDict(extra="forbid")

    url: str
    source: str
    status_code: int
    content: str
    cache_hit: bool = False
    sanitized_injections: int = Field(default=0, ge=0)
    fetched_at: str


class SearchRequest(BaseModel):
    """M6 POST /search request."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)
    source_filter: list[str] | None = None
    niche_filter: list[str] | None = None
    date_from: str | None = None
    date_to: str | None = None


class SearchResponse(BaseModel):
    """M6 POST /search response."""

    model_config = ConfigDict(extra="forbid")

    query: str
    items: list[EvidenceItem]
    total_candidates: int = Field(default=0, ge=0)


class ScoreRequest(BaseModel):
    """M10 POST /score request."""

    model_config = ConfigDict(extra="forbid")

    dimension: DimensionName
    rubric_version: str = Field(..., min_length=1)
    rubric_text: str = Field(..., min_length=1)
    idea_text: str = Field(..., min_length=1)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    features: dict[str, float | int | str | bool] = Field(default_factory=dict)


class GateInputs(BaseModel):
    """Non-score facts needed by M11 hard gates."""

    model_config = ConfigDict(extra="forbid")

    n_sources: int = Field(..., ge=0)
    n_platforms: int = Field(..., ge=0)
    estimated_build_hours: float = Field(..., ge=0.0)
    risk_blockers: list[str] = Field(default_factory=list)
    duplicate_product_name: str | None = None


class VerdictRequest(BaseModel):
    """M11 POST /verdict request."""

    model_config = ConfigDict(extra="forbid")

    idea_id: str = Field(..., min_length=1)
    version: int = Field(default=1, ge=1)
    run_id: str = Field(..., min_length=1)
    profile: StudentProfile
    scores: list[DimensionScore]
    gate_inputs: GateInputs
    accepted_objections: dict[DimensionName, int] = Field(default_factory=dict)


class WhatIfRequest(BaseModel):
    """M11 POST /whatif request."""

    model_config = ConfigDict(extra="forbid")

    verdict_request: VerdictRequest
    dimension_override: dict[DimensionName, float] = Field(default_factory=dict)


class ClaimItem(BaseModel):
    """Single claim submitted to M12 POST /check."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)


class CheckRequest(BaseModel):
    """M12 POST /check request."""

    model_config = ConfigDict(extra="forbid")

    claims: list[ClaimItem]
    evidence: list[EvidenceItem]
    run_id: str | None = None


class CheckClaimResult(BaseModel):
    """Per-claim verification outcome from M12."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    supported: bool
    reason: str


class CheckResponse(BaseModel):
    """M12 POST /check response."""

    model_config = ConfigDict(extra="forbid")

    results: list[CheckClaimResult]
    all_supported: bool
