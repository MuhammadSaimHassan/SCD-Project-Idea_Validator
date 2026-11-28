"""HTTP client helper for services that emit M13 trace records."""

import httpx

from shared.schemas import TraceRecord


def emit_trace(agentops_url: str, record: TraceRecord, timeout: float = 3.0) -> None:
    if not agentops_url:
        return
    response = httpx.post(
        f"{agentops_url.rstrip('/')}/trace",
        json=record.model_dump(mode="json"),
        timeout=timeout,
    )
    response.raise_for_status()
