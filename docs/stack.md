# Technology Stack

| Layer | Choice | Reason |
|---|---|---|
| Backend Services | Python 3.11+ / FastAPI / Uvicorn | Fast async APIs, native Pydantic v2 schema validation, light footprint |
| Schemas & Validation | Pydantic v2 + exported JSON Schema | Single source of truth across M1-M13 (`shared/schemas/`) |
| Primary DB | PostgreSQL (Alembic migrations) | Relational data (`users`, `profiles`, `ideas`, `verdicts`, `cards`, `niches`) |
| Cache | Redis | Verdict & retrieval cache with TTL and `profile_version` + `rubric_version` keys |
| Vector Store | Qdrant | Lightweight local & containerized vector search with metadata filtering |
| Embeddings & Keyword | `sentence-transformers` (MiniLM) + `rank_bm25` | Fast CPU embeddings + exact keyword matching for hybrid search |
| Fine-Tuned Scorer (M10) | 1B-3B open model (QLoRA via PEFT/TRL or Unsloth on Colab) + GGUF CPU server | Cheap, consistent rubric scoring with hosted LLM fallback |
| Hosted Fallback LLM | Gemini Flash / free-tier hosted API | Fallback on invalid JSON, draft labeling, and agent reasoning |
| Frontend UI (M1) | React + Vite + Vitest | Component-testable UI with runtime `VITE_API_BASE_URL` |
| Observability (M13) | JSONL trace volume + `/metrics` (Prometheus-style) | Cost/verdict, latency, cache hits, fallbacks, approvals, blocked injections |
| CI/CD & Platform (M14) | GitHub Actions, Docker, Trivy, `k3d` (Kubernetes), Jenkins | PR gates, SHA-tagged multi-stage images, NetworkPolicy enforcement, nightly eval |
