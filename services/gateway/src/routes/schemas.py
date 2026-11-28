"""Gateway API request/response schemas for M1 public endpoints."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from shared.schemas import ComputeTier, DimensionName, GoalType, Verdict


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class AuthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    email: str
    access_token: str
    token_type: str = "bearer"


class ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skills: list[str] = Field(default_factory=list)
    hours_per_week: float = Field(..., gt=0, le=168)
    weeks_available: float = Field(..., gt=0, le=104)
    team_size: int = Field(..., ge=1, le=20)
    compute: ComputeTier = ComputeTier.LAPTOP
    goal: GoalType
    interests: list[str] = Field(default_factory=list)


class DiscoverRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    niche_wish: str = Field(default="", max_length=500)
    max_ideas: int = Field(default=3, ge=1, le=10)
    require_deep_search_approval: bool = False


class ValidateRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=2, max_length=200)
    idea_text: str = Field(..., min_length=5, max_length=5000)
    needs_clarification: bool = False
    require_deep_search_approval: bool = False
    estimated_build_hours: float = Field(default=60.0, ge=1.0, le=2000.0)
    simulate_thin_evidence: bool = False


class AnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(..., min_length=1, max_length=1000)


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: bool
    reason: str = Field(default="", max_length=500)


class ChallengeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: DimensionName
    claim: str = Field(..., min_length=3, max_length=1000)


class ApplyWhatIfRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension_override: dict[DimensionName, float]


class RunAcceptedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    status: str
    workflow: str


class RunStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    workflow: str
    status: str
    events: list[dict[str, Any]]
    pending_question: dict[str, Any] | None = None
    pending_approval: dict[str, Any] | None = None
    result: dict[str, Any] | None = None


class IdeaSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idea_id: str
    title: str
    source: str
    latest_version: int
    latest_verdict: Verdict | None = None


class IdeaVersionEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    text: str
    verdict: Verdict | None = None


class CompareIdeasResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    left: IdeaSummaryResponse
    right: IdeaSummaryResponse
    dimension_deltas: dict[str, float]
