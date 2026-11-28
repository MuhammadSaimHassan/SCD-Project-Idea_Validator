"""FastAPI entrypoint for M12 Critic and Guardrails."""

from fastapi import FastAPI, HTTPException

from shared.schemas import CheckRequest, CheckResponse

from .guardrails import InputRailViolation, check_claims, validate_user_input

app = FastAPI(title="M12 Critic and Guardrails", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "critic"}


@app.get("/ready")
def ready() -> dict[str, str]:
    return {"status": "ready", "service": "critic"}


@app.get("/metrics")
def metrics() -> dict[str, int]:
    return {"blocked_injections": 0, "claims_checked": 0}


@app.post("/check", response_model=CheckResponse)
def check(payload: CheckRequest) -> CheckResponse:
    try:
        validate_user_input(" ".join(claim.text for claim in payload.claims))
    except InputRailViolation as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return check_claims(payload)
