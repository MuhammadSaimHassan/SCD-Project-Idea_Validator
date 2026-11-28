"""Four parallel M9 Validation Scorers combining KB features with M10 judgment."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Protocol

import httpx
import yaml
from pydantic import BaseModel, ConfigDict, Field

from services.scorer.src.model import FeatureRubricBackend, ScoringEngine
from shared.schemas import (
    DimensionName,
    DimensionScore,
    EvidenceItem,
    ScoreRequest,
    StudentProfile,
)


class ScoreClient(Protocol):
    """Protocol for calling M10 POST /score."""

    def score(self, req: ScoreRequest) -> DimensionScore:
        ...


class HttpScoreClient:
    """Calls remote M10 Scoring Model server over HTTP."""

    def __init__(self, scorer_url: str, timeout: float = 15.0) -> None:
        self._base = scorer_url.rstrip("/")
        self._timeout = timeout

    def score(self, req: ScoreRequest) -> DimensionScore:
        resp = httpx.post(
            f"{self._base}/score",
            json=req.model_dump(mode="json"),
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return DimensionScore.model_validate(resp.json())


class LocalScoreClient:
    """In-process M10 adapter for standalone local/test runs."""

    def __init__(self) -> None:
        self._engine = ScoringEngine(FeatureRubricBackend(), FeatureRubricBackend())

    def score(self, req: ScoreRequest) -> DimensionScore:
        return self._engine.score(req)


class ValidateScoresRequest(BaseModel):
    """Input payload for M9 parallel scoring."""

    model_config = ConfigDict(extra="forbid")

    idea_text: str = Field(..., min_length=3)
    profile: StudentProfile
    evidence: list[EvidenceItem] = Field(default_factory=list)
    estimated_build_hours: float = Field(default=60.0, ge=0.0)
    trend_growth: float = 0.1
    direct_competitor_count: int = Field(default=2, ge=0)
    gap_count: int = Field(default=2, ge=0)
    risk_blockers: list[str] = Field(default_factory=list)


def _compute_features(
    dim: DimensionName, req: ValidateScoresRequest
) -> dict[str, float | int | str | bool]:
    platforms = len({e.source for e in req.evidence})
    n_sources = len({e.card_id for e in req.evidence})
    avail_hours = (
        req.profile.hours_per_week * req.profile.weeks_available * req.profile.team_size
    )
    hours_ratio = round(req.estimated_build_hours / max(1.0, avail_hours), 3)

    idea_lower = req.idea_text.lower()
    skill_hits = sum(1 for sk in req.profile.skills if sk.lower() in idea_lower)
    skill_ratio = round(skill_hits / max(1, len(req.profile.skills)), 2)
    interest_hits = sum(1 for it in req.profile.interests if it.lower() in idea_lower)

    if dim == DimensionName.DEMAND_PAIN:
        return {
            "n_sources": n_sources,
            "n_platforms": platforms,
            "complaint_count": len(req.evidence),
            "trend_growth": req.trend_growth,
        }
    if dim == DimensionName.COMPETITION:
        return {
            "direct_competitor_count": req.direct_competitor_count,
            "n_sources": n_sources,
        }
    if dim == DimensionName.DIFFERENTIATION:
        return {
            "gap_count": req.gap_count,
            "n_sources": n_sources,
        }
    if dim == DimensionName.FEASIBILITY:
        return {
            "estimated_build_hours": req.estimated_build_hours,
            "available_hours": avail_hours,
            "hours_ratio": hours_ratio,
            "skill_match_ratio": skill_ratio,
        }
    if dim == DimensionName.RISK:
        return {
            "blocker_count": len(req.risk_blockers),
            "n_platforms": platforms,
        }
    return {
        "interest_overlap_count": interest_hits,
        "goal": req.profile.goal.value,
    }


def _rubric_info(rubrics_dir: Path, dim: DimensionName) -> tuple[str, str]:
    path = rubrics_dir / f"{dim.value}.yaml"
    if not path.exists():
        return f"{dim.value}@v1", f"Scale 0-5 rubric for {dim.value}"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return f"{dim.value}@v1", f"Scale 0-5 rubric for {dim.value}"
    return str(data.get("rubric_version", f"{dim.value}@v1")), str(data.get("anchors", {}))


def run_four_parallel_scorers(
    req: ValidateScoresRequest,
    scorer: ScoreClient,
    rubrics_dir: Path,
) -> list[DimensionScore]:
    """Run the 4 validation scorers in parallel to produce all 6 DimensionScores."""

    def score_dim(dim: DimensionName) -> DimensionScore:
        r_ver, r_text = _rubric_info(rubrics_dir, dim)
        feats = _compute_features(dim, req)
        return scorer.score(
            ScoreRequest(
                dimension=dim,
                rubric_version=r_ver,
                rubric_text=r_text,
                idea_text=req.idea_text,
                evidence=req.evidence,
                features=feats,
            )
        )

    def _demand_agent() -> list[DimensionScore]:
        return [score_dim(DimensionName.DEMAND_PAIN)]

    def _competition_diff_agent() -> list[DimensionScore]:
        return [
            score_dim(DimensionName.COMPETITION),
            score_dim(DimensionName.DIFFERENTIATION),
        ]

    def _feasibility_learning_agent() -> list[DimensionScore]:
        return [
            score_dim(DimensionName.FEASIBILITY),
            score_dim(DimensionName.LEARNING),
        ]

    def _risk_agent() -> list[DimensionScore]:
        return [score_dim(DimensionName.RISK)]

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [
            pool.submit(_demand_agent),
            pool.submit(_competition_diff_agent),
            pool.submit(_feasibility_learning_agent),
            pool.submit(_risk_agent),
        ]
        combined: list[DimensionScore] = []
        for fut in futures:
            combined.extend(fut.result())

    by_dim = {item.dimension: item for item in combined}
    return [by_dim[dim] for dim in DimensionName]
