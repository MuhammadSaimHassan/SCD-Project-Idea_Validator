"""M10 scoring logic with schema validation, 1x retry, and hosted fallback."""

import json
import logging
from typing import Any, Protocol

import httpx
from pydantic import ValidationError

from shared.schemas import DimensionScore, ScoreRequest

logger = logging.getLogger("scorer")


class ScorerBackend(Protocol):
    """Returns raw JSON string from a scoring model."""

    def generate_score_json(self, req: ScoreRequest) -> str:
        ...


class HttpModelBackend:
    """Calls an OpenAI-compatible local GGUF / Ollama / llama.cpp endpoint."""

    def __init__(self, endpoint_url: str, model_name: str, timeout: float = 15.0) -> None:
        self._url = endpoint_url.rstrip("/")
        self._model = model_name
        self._timeout = timeout

    def generate_score_json(self, req: ScoreRequest) -> str:
        ev_text = "\n".join(
            f"[{e.evidence_id}] ({e.source}) {e.quote}" for e in req.evidence[:6]
        )
        prompt = f"IDEA: {req.idea_text}\nFEATURES: {req.features}\nEVIDENCE:\n{ev_text}"
        resp = httpx.post(
            f"{self._url}/v1/chat/completions",
            json={
                "model": self._model,
                "temperature": 0.0,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            f"Score {req.dimension.value} using {req.rubric_version}. "
                            "Reply with JSON only."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=self._timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return str(data["choices"][0]["message"]["content"])


class FeatureRubricBackend:
    """Deterministic feature-backed scorer used locally or as offline hosted fallback."""

    def generate_score_json(self, req: ScoreRequest) -> str:
        if not req.evidence:
            return json.dumps(
                {
                    "score": 0.0,
                    "confidence": 0.0,
                    "evidence_ids": [],
                    "reason": "Abstained: no evidence items provided.",
                    "abstained": True,
                }
            )

        feats = req.features
        dim = req.dimension.value
        cited = [e.evidence_id for e in req.evidence[:3]]

        if dim == "demand_pain":
            n_src = float(feats.get("n_sources", len(req.evidence)))
            growth = float(feats.get("trend_growth", 0.0))
            raw_val = 1.5 + min(n_src, 5) * 0.55 + max(0.0, growth) * 2.0
            score = min(5.0, max(1.0, round(raw_val, 1)))
        elif dim == "competition":
            comp_cnt = float(feats.get("direct_competitor_count", 2))
            score = min(5.0, max(0.5, round(5.0 - comp_cnt * 0.6, 1)))
        elif dim == "differentiation":
            gaps = float(feats.get("gap_count", 2))
            score = min(5.0, max(1.0, round(2.0 + gaps * 0.7, 1)))
        elif dim == "feasibility":
            ratio = float(feats.get("hours_ratio", 0.7))
            skill_match = float(feats.get("skill_match_ratio", 0.8))
            raw_feas = (5.0 - max(0.0, ratio - 0.5) * 4.0) * (0.6 + 0.4 * skill_match)
            score = min(5.0, max(0.5, round(raw_feas, 1)))
        elif dim == "risk":
            blockers = float(feats.get("blocker_count", 0))
            score = 1.0 if blockers > 0 else 4.5
        else:  # learning
            overlap = float(feats.get("interest_overlap_count", 1))
            score = min(5.0, max(2.0, round(3.0 + overlap * 0.8, 1)))

        conf = min(0.95, round(0.55 + 0.08 * len(req.evidence), 2))
        return json.dumps(
            {
                "score": score,
                "confidence": conf,
                "evidence_ids": cited,
                "reason": f"Scored {dim} from computed features and cited {', '.join(cited)}.",
                "abstained": False,
            }
        )


class ScoringEngine:
    """Validates model output against DimensionScore; retries once, then falls back."""

    def __init__(
        self,
        primary: ScorerBackend,
        fallback: ScorerBackend,
        *,
        primary_model_name: str = "scorer-lora@v1",
        fallback_model_name: str = "hosted-fallback",
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._primary_name = primary_model_name
        self._fallback_name = fallback_model_name
        self.scores_total = 0
        self.retries_total = 0
        self.fallbacks_total = 0

    def _parse_and_validate(
        self, raw_json: str, req: ScoreRequest, model_label: str
    ) -> DimensionScore:
        payload: dict[str, Any] = json.loads(raw_json)
        if not isinstance(payload, dict):
            raise ValueError("Model output must be a JSON object")

        valid_ids = {e.evidence_id for e in req.evidence}
        cited = [str(eid) for eid in payload.get("evidence_ids", []) if str(eid) in valid_ids]
        abstained = (
            bool(payload.get("abstained", False))
            or (len(req.evidence) == 0)
            or (len(cited) == 0)
        )

        return DimensionScore(
            dimension=req.dimension,
            score=float(payload["score"]),
            confidence=0.0 if abstained else float(payload["confidence"]),
            evidence_ids=[] if abstained else cited,
            features=req.features,
            reason=str(payload.get("reason", "No reason provided")),
            rubric_version=req.rubric_version,
            model=model_label,
            abstained=abstained,
        )

    def score(self, req: ScoreRequest) -> DimensionScore:
        self.scores_total += 1
        # Enforce evidence rule upfront
        if not req.evidence:
            return DimensionScore(
                dimension=req.dimension,
                score=0.0,
                confidence=0.0,
                evidence_ids=[],
                features=req.features,
                reason="Abstained: no evidence items supplied to scorer.",
                rubric_version=req.rubric_version,
                model=self._primary_name,
                abstained=True,
            )

        # Primary attempt + 1 retry on invalid JSON or schema failure
        for attempt in range(2):
            try:
                raw = self._primary.generate_score_json(req)
                parsed = self._parse_and_validate(raw, req, self._primary_name)
                if parsed.abstained:
                    raise ValueError("Primary model failed to cite valid evidence_ids")
                return parsed
            except (
                json.JSONDecodeError,
                KeyError,
                TypeError,
                ValueError,
                ValidationError,
                httpx.HTTPError,
            ) as exc:
                logger.warning("primary_score_failed attempt=%d error=%s", attempt + 1, exc)
                if attempt == 0:
                    self.retries_total += 1

        # Fallback to hosted model
        self.fallbacks_total += 1
        logger.warning("falling_back_to_hosted dimension=%s", req.dimension.value)
        raw_fb = self._fallback.generate_score_json(req)
        return self._parse_and_validate(raw_fb, req, self._fallback_name)
