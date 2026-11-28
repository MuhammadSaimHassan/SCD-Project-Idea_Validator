"""FastAPI entrypoint for M12 Critic and Guardrails."""

import os
import uuid
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException

from services.agentops.src.client import emit_trace
from shared.schemas import CheckRequest, CheckResponse, TraceKind, TraceRecord

from .guardrails import InputRailViolation, check_claims, validate_user_input

app = FastAPI(title="M12 Critic and Guardrails", version="0.1.0")
agentops_url = os.getenv("AGENTOPS_URL", "")
blocked_injections = 0
claims_checked = 0


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "critic"}


@app.get("/ready")
def ready() -> dict[str, str]:
    return {"status": "ready", "service": "critic"}


@app.get("/metrics")
def metrics() -> dict[str, int]:
    return {
        "blocked_injections": blocked_injections,
        "claims_checked": claims_checked,
    }


@app.post("/check", response_model=CheckResponse)
def check(payload: CheckRequest) -> CheckResponse:
    global blocked_injections, claims_checked
    run_id = payload.run_id or f"critic_{uuid.uuid4().hex[:12]}"
    try:
        validate_user_input(" ".join(claim.text for claim in payload.claims))
    except InputRailViolation as exc:
        blocked_injections += 1
        emit_trace(
            agentops_url,
            TraceRecord(
                run_id=run_id,
                step_id=1,
                agent="critic",
                kind=TraceKind.DECISION,
                input=payload.model_dump(mode="json"),
                output={"blocked_injection": True},
                error=str(exc),
                ts=datetime.now(UTC),
            ),
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = check_claims(payload)
    claims_checked += len(response.results)
    emit_trace(
        agentops_url,
        TraceRecord(
            run_id=run_id,
            step_id=1,
            agent="critic",
            kind=TraceKind.DECISION,
            input=payload.model_dump(mode="json"),
            output=response.model_dump(mode="json"),
            ts=datetime.now(UTC),
        ),
    )
    return response
