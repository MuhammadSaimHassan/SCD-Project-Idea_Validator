# Idea Generator with Go / No-Go (CS4032 SCD Semester Project)

An interactive multi-agent system that helps students **discover** project/startup ideas from public data and **validate** them with a deterministic Go / No-Go Verdict Engine backed by evidence citations, RAG, a fine-tuned scoring model, AgenticOps, CI/CD, and Kubernetes.

## Repository Layout

- `shared/schemas/` — Canonical Pydantic v2 models & exported JSON Schemas (`schemas/`)
- `config/` — Weights (`weights.yaml`), thresholds/gates (`thresholds.yaml`), and AgenticOps budgets (`budgets.yaml`)
- `services/` — Independent deployable FastAPI modules (`gateway`, `ui`, `orchestrator`, `scouts`, `tools`, `kb`, `analyst`, `ideation`, `validators`, `scorer`, `verdict`, `critic`, `agentops`)
- `jobs/` — Offline/Cron jobs (`ingestion`, `finetune`, `evaluation`)
- `rubrics/` — Versioned scoring rubrics per dimension
- `eval/` — Retrieval quality gate (`eval/retrieval/`) and verdict tuning sets (`eval/verdict/`)
- `k8s/` — Kubernetes manifests for namespace `idea-validator`
- `docs/` — Stack, API contracts, design decision records (`docs/decisions/`), AI-usage log, and contribution table

## Quickstart (Local Development)

1. Copy environment variables:
   ```bash
   cp .env.example .env
   ```
2. Install development dependencies (Python 3.11+):
   ```bash
   pip install -r requirements-dev.txt
   ```
3. Run the starter services locally:
   ```bash
   uvicorn services.verdict.src.main:app --host 0.0.0.0 --port 8011 --reload
   uvicorn services.gateway.src.main:app --host 0.0.0.0 --port 8000 --reload
   ```
4. Verify health & readiness endpoints:
   ```bash
   curl http://localhost:8011/health
   curl http://localhost:8011/ready
   curl http://localhost:8000/health
   curl http://localhost:8000/ready
   ```
5. Run checks and tests:
   ```bash
   ruff check .
   mypy shared services
   pytest
   ```
