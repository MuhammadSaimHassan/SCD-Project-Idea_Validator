# ADR-003: Use append-only JSONL traces with explicit budget gates

- **Status:** Accepted
- **Context:** Discover and Validate must be auditable, replayable, and bounded
  without adding a heavyweight telemetry database to the local development
  stack.
- **Options:**
  1. Keep traces in process memory only.
  2. Persist JSONL records by run and replay recorded tool outputs without
     contacting external systems.
  3. Introduce a hosted tracing platform and remote replay service.
- **Decision:** M13 persists validated `TraceRecord` objects in append-only
  `data/traces/<run_id>.jsonl` files. The replay endpoint and CLI rebuild the
  recorded sequence from those results and do not re-execute tools. Budgets
  reject actions that exceed hard limits and raise an approval-required result
  above the configured approval threshold. M5 enforces its per-run page limit.
- **Why:** Local JSONL is inspectable, portable to a mounted volume, and
  sufficient for deterministic course-project replay. It keeps collected
  inputs, outputs, cost, token counts, latency, errors, and cache status tied to
  a single run id.
- **Trade-offs:** This implementation is single-node storage; it has no
  retention policy, cross-replica coordination, or hosted dashboard. These are
  deployment concerns for Docker/Kubernetes and should not be inferred from
  local test results.
- **Validation:** `pytest services/agentops services/orchestrator` covers
  append/read, replay, metrics, hard limits, and approval stops. M5 tests cover
  per-run page limits.
- **AI use:** AI assisted with implementation and ADR drafting; project
  members should review the design and confirm operational limits before
  deployment.
