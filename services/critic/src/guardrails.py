"""M12 claim checking and input guardrails."""

import re

from services.tools.src.sanitiser import INJECTION_PATTERNS, sanitise_text
from shared.schemas import CheckClaimResult, CheckRequest, CheckResponse, EvidenceItem

MAX_USER_LENGTH = 4000
STOP_WORDS = {"a", "an", "and", "for", "from", "in", "of", "on", "the", "to", "with"}


class InputRailViolation(ValueError):
    """Raised when input violates the M12 input rail."""


def validate_user_input(text: str) -> None:
    if len(text) > MAX_USER_LENGTH:
        raise InputRailViolation(f"Input exceeds {MAX_USER_LENGTH} characters")
    if not text.strip():
        raise InputRailViolation("Input must not be empty")
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            raise InputRailViolation("Obvious prompt-injection attempt blocked")


def approval_required(estimated_cost_usd: float, require_over_usd: float = 0.10) -> bool:
    return estimated_cost_usd > require_over_usd


def _evidence_overlap(claim: str, evidence: EvidenceItem) -> float:
    claim_words = {
        word
        for word in re.findall(r"[a-z0-9]+", claim.lower())
        if len(word) > 2 and word not in STOP_WORDS
    }
    if not claim_words:
        return 0.0
    evidence_words = set(re.findall(r"[a-z0-9]+", evidence.quote.lower()))
    return len(claim_words & evidence_words) / len(claim_words)


def check_claims(payload: CheckRequest) -> CheckResponse:
    evidence_by_id = {item.evidence_id: item for item in payload.evidence}
    results: list[CheckClaimResult] = []

    for claim in payload.claims:
        if not claim.evidence_ids:
            results.append(
                CheckClaimResult(
                    claim_id=claim.claim_id,
                    supported=False,
                    reason="No evidence IDs supplied",
                )
            )
            continue

        matched = [evidence_by_id[id_] for id_ in claim.evidence_ids if id_ in evidence_by_id]
        missing = [id_ for id_ in claim.evidence_ids if id_ not in evidence_by_id]
        if missing:
            results.append(
                CheckClaimResult(
                    claim_id=claim.claim_id,
                    supported=False,
                    reason=f"Unknown evidence IDs: {', '.join(missing)}",
                )
            )
            continue

        cleaned_claim, _ = sanitise_text(claim.text)
        cleaned_quote = " ".join(item.quote for item in matched)
        sanitised_quote, _ = sanitise_text(cleaned_quote)
        matched_quote_evidence = matched[0].model_copy(update={"quote": sanitised_quote})
        overlap = max(
            _evidence_overlap(cleaned_claim, matched_quote_evidence),
            *(_evidence_overlap(cleaned_claim, item) for item in matched),
        )
        supported = overlap >= 0.15
        results.append(
            CheckClaimResult(
                claim_id=claim.claim_id,
                supported=supported,
                reason=(
                    "Claim has corroborating evidence text"
                    if supported
                    else "Claim is not supported by the supplied evidence text"
                ),
            )
        )

    return CheckResponse(results=results, all_supported=all(r.supported for r in results))
