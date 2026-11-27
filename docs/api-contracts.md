# API Contracts (M1-M13)

Every service exposes:
- `GET /health` -> `{"status": "ok", "service": "<name>"}` (process alive)
- `GET /ready` -> `{"status": "ready", "service": "<name>"}` (dependencies reachable)
- `GET /metrics` -> Prometheus text or JSON metrics

All payloads are validated against `shared/schemas/` (`schemas/*.schema.json`).

## Public Endpoints (M1 Gateway)

| Endpoint | Purpose |
|---|---|
| `POST /auth/register`, `POST /auth/login` | Create account and obtain auth token |
| `GET /profile`, `PUT /profile` | Read and update `StudentProfile` |
| `POST /discover`, `POST /validate` | Start Discover or Validate run; returns `run_id` |
| `GET /runs/{id}`, `GET /runs/{id}/events` | Run status/result and live SSE progress stream |
| `POST /runs/{id}/answer`, `POST /runs/{id}/approve` | Submit clarifying answer or approve/decline over-budget step |
| `POST /ideas/{id}/challenge`, `POST /ideas/{id}/whatif` | Challenge a claim or apply change -> new `idea_version` + `Verdict` |
| `GET /ideas`, `GET /ideas/{id}/versions`, `GET /compare` | History, versions, and side-by-side 6-dimension comparison |
| `GET /metrics` | Aggregated gateway & AgenticOps metrics |

## Internal Endpoints (Service-to-Service)

| Module | Endpoint | Request Schema | Response Schema |
|---|---|---|---|
| M5 Tool Layer | `POST /fetch` | `FetchRequest` | `FetchResponse` |
| M6 Knowledge Base | `POST /search` | `SearchRequest` | `SearchResponse` |
| M10 Scoring Model | `POST /score` | `ScoreRequest` | `DimensionScore` |
| M11 Verdict Engine | `POST /verdict`, `POST /whatif` | `VerdictRequest`, `WhatIfRequest` | `Verdict` |
| M12 Critic | `POST /check` | `CheckRequest` | `CheckResponse` |
| M13 AgenticOps | `POST /trace`, `GET /runs/{id}/trace` | `TraceRecord` | `list[TraceRecord]` |
