# CS4032 SCD Project: Idea Generator with Go / No-Go
## Phase-Based Plan (Code first, then GitHub, Docker, Kubernetes, Jenkins)

Group of 2: **Member A** and **Member B** (replace with names). Both must commit code, review each other's work, and be able to explain the whole system.

---

## 0. How this plan works

**Order of work**

1. Phases 0 to 8: build and tune everything **locally** (plain Python processes, SQLite or local Postgres, no containers needed yet).
2. Phase 9: GitHub workflow (protected main, PRs, issues, merge conflict, GitHub Actions).
3. Phase 10: Docker (one image per module, docker-compose).
4. Phase 11: Kubernetes.
5. Phase 12: Jenkins.
6. Phase 13: Report, screenshots, submission.

**Suggested length:** about 8 weeks at 15 to 20 hours per person per week. Stretch or compress the phases to match your real deadline. Check the deadline on GCR and write it here: `DEADLINE: ____`. Work backwards and make sure Phase 13 gets at least 4 full days.

**Screenshot markers.** Every place you must capture evidence is marked with **📸 CHECKPOINT**. Save files into a `screenshots/` folder with the suggested name and write the one-line caption in `screenshots/captions.md` at the same moment, while you still remember what it shows. The full checklist is in Section 15.

### Three ground rules that make the "code first" order safe

These do not change your order. They only protect your marks.

1. **Create the GitHub repo today as a plain backup.** Private, add your partner and the marking people later. Push often. Do not set up protection or workflows yet. The contribution table must match the git history, so both of you must commit under your own names from the start.
2. **Use one feature branch per module, with conventional commits** (`feat(verdict): add duplicate gate`). Do not merge them into `main` yet. In Phase 9 you open a PR for each branch, so you get a real PR history with reviews instead of one giant upload at the end.
3. **Write code "container-ready" from the start** so Phase 10 takes hours, not days:
   - Every service reads all settings from environment variables (DB URL, API address, other services' URLs, API keys). Never hard-code `localhost`.
   - Every service exposes `GET /health` and `GET /ready` from the first commit.
   - Each module lives in its own folder with its own `requirements.txt`, under `services/<name>/src/`.
   - Keep a `.env.example` with names only, never secrets.
   - Python 3.12 is used in the guide's Dockerfile and you run 3.11 locally, so avoid 3.12-only syntax.

### Hardware warning (read this before Phase 10)

Your laptop is a Windows 10 machine with 8 GB RAM and a nearly full C: drive. Docker Desktop, a local Kubernetes cluster, Postgres, Redis, a vector store and about 10 services will not fit comfortably. Plan for this now:

- **Do not delete WSL until the project is submitted.** Docker Desktop normally needs WSL2 on Windows. Free space elsewhere first.
- **Use a lightweight cluster:** k3d (k3s in Docker) is a good fit. k3s includes a NetworkPolicy controller, but you must still prove it works with the test in Phase 11.
- **Group modules into fewer containers** to save RAM. The guide's own Kubernetes diagram groups scorers and generator into one `agents` deployment. A sensible grouping is below.
- **Train the model on Colab or Kaggle,** never locally. Serve a small quantized GGUF model (1B) on CPU, which needs roughly 1 to 2 GB RAM.
- **Fallback:** if the cluster still will not run on your laptop, run Phases 10 to 12 on your partner's machine, or a free-tier cloud VM. Decide this by Phase 8, not Phase 11.

**Suggested container grouping (at least 6 distinct images required):**

| Image | Modules inside |
|---|---|
| `gateway` | M1 API gateway (plus UI static files, or a separate `ui` image) |
| `orchestrator` | M3 |
| `tools` | M5 tool layer (the only one with internet egress) |
| `kb` | M6 search API (and M6i/M4 as CronJob entrypoints) |
| `agents` | M8 generator agents, M9 validators, M7 analyst |
| `verdict` | M11 verdict engine |
| `critic` | M12 critic and guardrails |
| `model` | M10 fine-tuned scoring model server |
| `agentops` | M13 traces, metrics, eval |
| `postgres`, `redis`, `vector-store` | official images |

---

## 1. Work split

| Area | Member A | Member B |
|---|---|---|
| Data side | M5, M4, M6i, M6, M7 | |
| Scoring side | | M10t, M10, M9 |
| Core logic | M11 verdict engine (pair-review with B) | M12 critic |
| Agents | M3 orchestrator | M8 generator agents |
| Product | M2 backend + cache | M1 gateway + UI |
| Ops | M13 tracing and budgets | M13 eval harness and dashboard |
| Platform | GitHub Actions, Docker | Kubernetes, Jenkins |

Swap anything you like, but keep it balanced. The contribution table must show similar effort and match the git log. Review each other's code every week.

---

## PHASE 0: Foundations and contracts (Days 1 to 4)

**Goal:** agree on everything that all modules share, before writing module code.

- [ ] Create the repo with the layout from the guide (`services/`, `jobs/`, `rubrics/`, `config/`, `eval/`, `docs/`, `k8s/`).
- [ ] Create the empty private GitHub repo and push the skeleton to `main` (backup only).
- [ ] Write a **shared schemas package** (Pydantic models): idea card, student profile, evidence item, dimension score, verdict, trace record. Add JSON Schema exports to `schemas/`.
- [ ] Write the **API contract** for every internal endpoint (M5 `/fetch`, M6 `/search`, M10 `/score`, M11 `/verdict` and `/whatif`, M12 `/check`, M13 `/trace`) as a short markdown or OpenAPI file.
- [ ] Write `config/weights.yaml`, `config/thresholds.yaml` (T_go 70, T_no 50, floor 1.5), `config/budgets.yaml`.
- [ ] Decide the stack and write it in `docs/stack.md`: FastAPI for services, Postgres + Redis, one vector store (Qdrant or Chroma), `sentence-transformers` for embeddings (a small model such as MiniLM), BM25 for keyword search, React or plain HTML for the UI, one hosted LLM with a free tier.
- [ ] Start the **AI-usage log** (`docs/ai-usage-log.md`) and keep adding to it every week. Do not leave it for the end.
- [ ] Start **decision record 1**: hybrid search (fill the numbers in Phase 2).
- [ ] Get API keys (GitHub, Product Hunt or Reddit if used). Put them in `.env`, which is git-ignored.

**Done when:** both of you can run a "hello" FastAPI service with `/health` and `/ready`, and the schemas import cleanly in both services.

---

## PHASE 1: Data collection and ingestion (Week 1 to 2)

**Modules:** M5 tool layer, M4 scouts, M6i ingestion.

### 1A. M5 Tool Layer (Member A)
- [ ] `POST /fetch` with connectors for at least 3 sources (Hacker News Firebase API, GitHub REST API, plus Product Hunt, Reddit or YC directory).
- [ ] Domain allow-list, per-domain rate limit, `robots.txt` check, clear User-Agent, cache, back-off on errors.
- [ ] **Sanitiser** that strips instructions aimed at models from fetched text (for example "ignore previous instructions"). Keep a list of test strings.
- [ ] Unit tests: blocked domain, rate limit hit, robots disallow, poisoned page cleaned.

### 1B. M4 Scouts (Member A or B)
- [ ] One scout per source, on-demand and schedulable (a CLI entrypoint with `--source hn`, ready to be a CronJob later).
- [ ] Per-source failure handling. A failing source must not crash the run.
- [ ] Scouts reach the internet **only through M5**. No direct `requests.get` to external sites anywhere else.

### 1C. M6i Ingestion jobs (Member B)
- [ ] Turn pages into **idea cards** (schema in guide 2.1): clean text, extract name, one-liner, problem, customer, niche tags, stage, source, URL, dates.
- [ ] Dedupe by URL and by near-duplicate text. The job must be **repeatable without creating duplicates** (test by running it twice).
- [ ] Chunk text **keeping the card id** on every chunk (`card_8f21#c2`), embed, write to the vector store.
- [ ] Write an `ingestion_runs` record (source, added, dropped).
- [ ] Target: **at least 1,500 cards from at least 3 sources.** Start collecting early, because rate limits make this slow. Run it in the background while you work on other things.
- [ ] **Save a snapshot** of the card data (`data/snapshot/cards.jsonl`) so you never depend on a website being up.

**Done when:** 1,500+ cards in the store from 3+ sources, ingestion is repeatable, snapshot saved.

> **📸 CHECKPOINT 1A (card counts):** terminal or notebook output showing card count per source and total (needed for the report's knowledge base section). Name: `kb_01_card_counts.png`.

---

## PHASE 2: Knowledge base search and niche analysis (Week 2 to 3)

**Modules:** M6 knowledge base, M7 niche and trend analyst.

### 2A. M6 Knowledge Base
- [ ] `POST /search` with **hybrid search** (vector + BM25 keyword) and **reranking** (reciprocal rank fusion or a small cross-encoder).
- [ ] Filters by date, source and niche. Return ranked **evidence items with ids**.
- [ ] Freshness and coverage tracking (last fetched per source, cards per niche).
- [ ] Write **at least 20 hand-written test queries** with the expected card ids in `eval/retrieval/queries.json`. Do not judge retrieval by eye.
- [ ] Measure recall@5 for vector only, keyword only, and hybrid. This table fills **decision record 1**.
- [ ] A pytest in `eval/retrieval/` that fails if recall drops below a stored baseline. This becomes the **retrieval quality gate** in GitHub Actions later.

### 2B. M7 Niche and Trend Analyst
- [ ] Cluster cards into **named niches** (embedding clustering, then name each cluster with the LLM or top terms).
- [ ] Build the **monthly time series** per niche (`niche_stats`: launches, mentions).
- [ ] Label niches **rising, flat or saturated** from the trend slope.
- [ ] Produce a **gaps list** (underserved problems, repeated complaints with no strong product). This feeds M8 and M9.
- [ ] Save a niche map chart for the report.

**Done when:** retrieval baseline is stored, hybrid beats single methods on your numbers, niches and gaps exist as data.

> **📸 CHECKPOINT 2A (retrieval result):** the table comparing vector, keyword and hybrid recall on the 20 queries. Name: `kb_02_retrieval_results.png`. Caption example: "Hybrid search with reranking raises recall@5 from X to Y on 20 hand-written queries."
>
> **📸 CHECKPOINT 2B (optional but useful):** niche map or trend chart. Name: `kb_03_niche_map.png`.

---

## PHASE 3: Rubrics and the Verdict Engine (Week 3 to 4)

**Modules:** M11 verdict engine, rubric files. Do this early because it is pure code with no model, so it is the safest marks.

### 3A. Rubrics
- [ ] One versioned file per dimension in `rubrics/`: `demand_pain`, `competition`, `differentiation`, `feasibility`, `risk`, `learning`. Each has an anchor for every score 0 to 5, listed features, output schema, and at least one worked example per level.
- [ ] Rubric version string (`demand_pain@v1`) that every score will record.

### 3B. M11 Verdict Engine (plain code, **no LLM**)
- [ ] Gates in order: **evidence** (3+ sources on 2+ platforms, else INSUFFICIENT EVIDENCE), **feasibility** (effort fits hours, NO-GO with hours gap), **risk** (blocker named), **duplicate** (unless Differentiation is 3 or more).
- [ ] Weighted score 0 to 100 from the goal's weight preset (weights sum to 100).
- [ ] Confidence = 0.7 x mean confidence + 0.3 x min(1, sources/5). Below 0.5 gives INSUFFICIENT EVIDENCE.
- [ ] GO / PIVOT / NO-GO with thresholds and floor. PIVOT names the weakest dimension.
- [ ] **Challenge adjustment:** each accepted objection lowers the score by 0.5 (max 1.0) and confidence by 0.1.
- [ ] **Sensitivity:** each weight moved +/-20% (difference shared proportionally) and the least confident score moved by 1. Any flip gives BORDERLINE and shows what flips it.
- [ ] **What would make this GO:** find the smallest change that changes the verdict.
- [ ] `POST /verdict` and `POST /whatif`. All rules read from the config files (later a ConfigMap).
- [ ] Deterministic: same input gives the same output.
- [ ] **Unit tests for every gate, threshold edge, sensitivity check and what-if.** Reproduce the worked example from the description (70.5 GO, about 69.9 PIVOT under weight change, 73.5 after raising Competition) as a test.

**Done when:** all tests pass and the worked example is reproduced exactly.

> **📸 CHECKPOINT 3 (verdict engine tests):** green pytest output for the verdict engine including the worked example. Name: `verdict_01_unit_tests.png`. It will also be your local fallback evidence if a CI screenshot goes wrong later.

---

## PHASE 4: Fine-tuned scoring model and validators (Week 4 to 5)

**Modules:** M10t fine-tuning pipeline, M10 scoring model, M9 validation agents.

### 4A. Dataset (M10t)
- [ ] Build **at least 300** (idea, evidence, dimension) examples from the knowledge base, covering all six dimensions and all score levels.
- [ ] Draft labels with a hosted model using your rubric. **Hand-check at least 60** and mark them as checked. These are the evaluation set.
- [ ] **Split by idea, not by row** (about 80/20). Never use ideas from your later labelled verdict set (Phase 8).
- [ ] Format: one JSON object per line in the chat-messages format from guide 6.1.

### 4B. Training (Colab or Kaggle)
- [ ] LoRA or QLoRA on a 1B to 3B open model with PEFT + TRL or Unsloth. Start with a few epochs and watch validation loss.
- [ ] Record rank, learning rate, epochs and batch size in the repo.
- [ ] Merge the adapter, optionally quantise to GGUF. **Do not commit weights to git.** Upload as a release asset or registry artifact and document the download command.

### 4C. M10 scoring server
- [ ] `POST /score` (rubric, idea, evidence in, dimension score JSON out), plus `/health` and `/ready`.
- [ ] Validate output against the schema. **Invalid: retry once, then fall back to the hosted model and log the fallback.**
- [ ] Evaluate **base vs fine-tuned vs hosted** on the hand-checked examples: mean absolute error, share within 1 point, valid-JSON rate, share of real evidence ids, latency, cost per score.
- [ ] Find **one example where fine-tuning did not help** and write why.

### 4D. M9 validation agents (four scorers in parallel)
- [ ] Demand and Pain, Competition and Differentiation, Feasibility for this student, Risk. Each has its own rubric, tools and output schema.
- [ ] Each score combines **computed features** (numbers from the KB, such as `n_sources`, `trend_growth`) with model judgment.
- [ ] **No evidence ids means the scorer abstains.**
- [ ] The Learning dimension is scored from profile goals and skills (assign it to a scorer, for example Feasibility).

**Done when:** a command line call scores a sample idea across all six dimensions with evidence ids, and the comparison table exists.

> **📸 CHECKPOINT 4A (fine-tuning comparison):** the table of base vs fine-tuned vs hosted. Name: `ft_01_comparison_table.png`.
>
> **📸 CHECKPOINT 4B (training curves):** training and validation loss plot from Colab. Name: `ft_02_training_loss.png`.
>
> **📸 CHECKPOINT 4C (failure case):** the example where fine-tuning did not help, with your short explanation. Name: `ft_03_failure_case.png`.

---

## PHASE 5: Agents, critic and orchestrator (Week 5 to 6)

**Modules:** M8 idea generator, M12 critic and guardrails, M3 orchestrator.

### 5A. M12 Critic and Guardrails (Member B)
- [ ] `POST /check`: claims with evidence ids in, supported or not out, per claim.
- [ ] **Injection defence:** fetched text is data and is never obeyed. Test with poisoned pages.
- [ ] **Input rail** on user input (length, forbidden content, obvious injection attempts).
- [ ] **Approval gate** when an action goes over budget.

### 5B. M8 Idea Generator agents
- [ ] **Ideator** proposes ideas citing gap evidence and respecting the student's hours and skills.
- [ ] **Gap Analyst** adds complaints and missing features from the KB.
- [ ] **Skeptic** argues against each idea with evidence.
- [ ] Debate loop **limited to 3 rounds**. Ideas defeated with evidence are dropped. Every idea cites its gap evidence. No renamed clones of existing products.

### 5C. M3 Orchestrator (Member A)
- [ ] Both workflows as **testable state machines**:
  - Discover: request, niches, ideator, gap analyst, skeptic, critic, validate survivors, ranked result.
  - Validate: intake (clarify only if the answer changes the result), evidence, four scorers in parallel, features, verdict, challenge, stability, card.
- [ ] Parallel agents, retries, timeouts, **stop at budget and ask the user**, re-run only what changed.
- [ ] Every decision written as a trace record.
- [ ] Behaviour tests with **recorded model responses** covering: invalid JSON from a scorer, a tool timeout, an empty source, a poisoned page.

**Done when:** `python -m orchestrator validate "<idea>" --profile profile.json` returns a full verdict card JSON, and `discover` returns a ranked list.

> **📸 CHECKPOINT 5 (behaviour tests):** green output of the four behaviour tests (invalid JSON, timeout, empty source, poisoned page blocked). Name: `agentops_01_behaviour_tests.png`.

---

## PHASE 6: Backend, gateway and UI (Week 6 to 7)

**Modules:** M2 profile, session and cache, M1 gateway and web UI.

### 6A. M2 (Member A)
- [ ] Postgres schema with **migrations** (Alembic): users, profiles, ideas, idea_versions, verdicts, dimension_scores, approvals, traces_index, conversations, plus the KB tables.
- [ ] **Layered backend:** routes, services, repositories.
- [ ] Redis cache for verdicts and retrieval with TTL. **Cache keys include profile version and rubric version.** Cache hits visible in logs and metrics.

### 6B. M1 gateway and UI (Member B)
- [ ] Endpoints: `/auth/register`, `/auth/login`, `/profile` (GET, PUT), `/discover`, `/validate`, `/runs/{id}`, `/runs/{id}/events` (SSE), `/runs/{id}/answer`, `/runs/{id}/approve`, `/ideas/{id}/challenge`, `/ideas/{id}/whatif`, `/ideas`, `/ideas/{id}/versions`, `/compare`, `/metrics`.
- [ ] Rate limiting and input validation. API address **set at runtime**, never hard-coded.
- [ ] UI covering U1 to U10: signup/login/profile, Discover, live agent view with spend, approval prompt, clarifying questions, verdict card (gates, six scores with evidence links, weights, confidence, stability), what-if, challenge, history and compare, INSUFFICIENT EVIDENCE explanation.
- [ ] **Component tests** for the UI.
- [ ] The browser talks only to M1. Never to models or scouts directly.

**Done when:** you can run the full product in the browser locally and click through all of U1 to U10.

> **📸 CHECKPOINT 6 (UI, first pass):** take every required UI screenshot now as a backup, then **retake them on Kubernetes in Phase 11**:
> - `ui_01_profile.png`: profile page saved.
> - `ui_02_discover_results.png`: ranked Discover list with verdicts.
> - `ui_03_verdict_card.png`: verdict card with gates, six scores, weights, confidence, stability.
> - `ui_04_challenge.png`: a challenge on a claim, defended or removed.
> - `ui_05_whatif_v2.png`: "what would make this GO", apply a change, version 2.
> - `ui_06_insufficient_evidence.png`: INSUFFICIENT EVIDENCE card saying what was missing.
> - `ui_07_live_agents_and_approval.png`: live agent view with tool calls, spend, and an approval prompt.

---

## PHASE 7: AgenticOps (Week 7)

**Module:** M13.

- [ ] **Tracing:** every agent step, tool call and model call writes a trace record under one run id (`POST /trace`, `GET /runs/{id}/trace`, JSON lines on a volume). Build a **replay command** that re-runs a stored run using recorded tool results.
- [ ] **Budgets:** caps on tokens, pages, steps and cost per run, enforced in the orchestrator and tool layer. Over budget means stop or ask the user.
- [ ] **Prompt and rubric registry:** versioned files; every verdict records the engine, rubric and weight versions used.
- [ ] **Evaluation harness:** runs the system on labelled ideas, outputs agreement and a confusion matrix, and checks behaviour (tools used, evidence cited, budget kept, injection resisted). It must run as a single command so it can become a Kubernetes Job and a nightly Jenkins stage.
- [ ] **Drift reports** after each ingestion: data freshness, niche coverage, shift in the verdict distribution.
- [ ] **Dashboard:** cost per verdict, latency per agent, cache hit rate, fallbacks, approvals, blocked injections (a Prometheus `/metrics` endpoint plus Grafana, or a simple page reading `/metrics`).

**Done when:** one run produces a readable trace, a replay works, and the dashboard shows real numbers.

> **📸 CHECKPOINT 7A (trace):** a full trace of one run (steps, tools, tokens, cost). Name: `ops_01_trace.png`.
>
> **📸 CHECKPOINT 7B (dashboard):** dashboard with cost per verdict, latency, cache hits, fallbacks, approvals, blocked injections. Name: `ops_02_dashboard.png`.
>
> **📸 CHECKPOINT 7C (drift report):** a drift report after an ingestion. Name: `ops_03_drift_report.png`.
>
> **📸 CHECKPOINT 7D (budget stop):** a run stopping at budget and asking for approval. Name: `ops_04_budget_stop.png`.

---

## PHASE 8: Tune the verdict (Week 7 to 8)

**Goal:** measure and improve the Verdict Engine against human judgment. This is graded separately in the report.

- [ ] Build your own **labelled set** (at least 25 to 30 ideas): clear GOs, clear NO-GOs, borderline cases, thin-evidence cases, each with a profile and a human verdict. **Both of you label independently**, then resolve differences and record who labelled what.
- [ ] Never use these ideas for fine-tuning.
- [ ] Run the system on all of them and build the **"before" confusion matrix**.
- [ ] Tune T_go, T_no, floors and weights. Report separately how often the system says **GO when humans said NO-GO**, because that is the worst error.
- [ ] Do not overfit. Check the tuned values on a few ideas you held back.
- [ ] Save the final values in `config/` (they become the ConfigMap later). Build the **"after" confusion matrix**.
- [ ] Write **decision records 2 and 3** (for example: "verdict by code, not by LLM", "fine-tuned scorer with hosted fallback", "NetworkPolicy with a single tool layer").
- [ ] Finalise the AI-usage log up to this point.

**Done when:** before and after matrices exist, final config is saved.

> **📸 CHECKPOINT 8 (tuning):** `tuning_01_before_matrix.png` and `tuning_02_after_matrix.png`, with the "GO when NO-GO" error count in each caption.

### 🔒 Code freeze gate (end of Phase 8)

Before moving on, confirm all of this works **locally**:

- [ ] Full Discover and Validate flows work from the browser.
- [ ] All tests pass.
- [ ] No hard-coded `localhost` or secrets in the code.
- [ ] Every service has `/health` and `/ready`.
- [ ] You know which machine will run Docker and Kubernetes (see the hardware warning).

Only fix bugs from now on. New features can wait.

---

## PHASE 9: GitHub workflow and GitHub Actions (Week 8)

**Goal:** turn your plain repo into a properly managed one, with real PR history.

### 9A. Repository hardening
- [ ] Add your partner and the people marking as collaborators. Make sure they can open the repo.
- [ ] Confirm no keys or passwords were ever committed (`git log -p | grep -i key`, or a scanner such as gitleaks). If found, rotate the keys.
- [ ] Add a README (start with the final version in Phase 13), `.gitignore`, `.dockerignore`, `.env.example`, a PR template and issue templates.

### 9B. Issues and PRs (use your existing feature branches)
- [ ] Create **one issue per task or module** (about 15 to 25), then link each PR to its issue (`Closes #12`).
- [ ] Push all feature branches. **Do not enable protection yet**, so your branch PRs can show reviews first, or enable it first and merge one at a time. Either order works as long as each PR has a review from the other member.
- [ ] Open a PR per module branch and have the **other member review it** (comments, at least one requested change in a couple of them).
- [ ] Merge them into `main` one at a time.

### 9C. Protect `main`
- [ ] Settings, Branches: require pull requests, **no direct pushes**, require status checks to pass, require **one review**.

> **📸 CHECKPOINT 9A (protected main):** branch protection rules page. Name: `git_01_protected_main.png`.
>
> **📸 CHECKPOINT 9B (PR with required checks):** a PR page showing required checks and the review approval. Name: `git_02_pr_required_checks.png`. Take this after 9D when the checks exist.

### 9D. Intentional merge conflict
- [ ] Create two branches that edit the **same lines** of one file (for example a line in the README or a config value).
- [ ] Merge the first. Open a PR for the second, which now conflicts. **Resolve it in the PR** (web editor or locally), then merge.

> **📸 CHECKPOINT 9C (merge conflict):** the conflict screen and the resolved, merged PR. Name: `git_03_merge_conflict_pr.png`.

### 9E. GitHub Actions on every PR (`.github/workflows/pr-checks.yml`)
- [ ] Lint and type checks (`ruff check .`, `mypy services`).
- [ ] Unit tests including the Verdict Engine (`pytest services/verdict`).
- [ ] UI component tests.
- [ ] **Retrieval quality gate** (`pytest eval/retrieval`, fails below baseline).
- [ ] Docker build (needs Phase 10 Dockerfiles; add this job right after Phase 10A).
- [ ] Trivy image scan (`exit-code: 1`, severity CRITICAL).
- [ ] Kubernetes manifest validation (kubeconform or `kubectl --dry-run`; add after Phase 11A).
- [ ] Mark every job as a **required check** on `main`.
- [ ] **Make one run fail on purpose** (for example a test with a wrong assertion on a throwaway branch), then fix it.

> **📸 CHECKPOINT 9D (Actions green):** a green workflow run listing all jobs. Name: `ci_01_actions_green.png`.
>
> **📸 CHECKPOINT 9E (Actions failing):** a red run with the failing job and message visible. Name: `ci_02_actions_failing.png`.

---

## PHASE 10: Docker (Week 8 to 9)

**Goal:** one reproducible image per module, plus a compose file that starts everything.

### 10A. Dockerfiles
- [ ] One Dockerfile per image, following the guide's pattern: **multi-stage, non-root user, pinned versions** (`python:3.12-slim`, pinned requirements), `EXPOSE 8000`, a `.dockerignore`.
- [ ] **At least 6 distinct images.** Use the grouping table in Section 0 if RAM is tight.
- [ ] Tag images with the **commit SHA**, never only `latest`.
- [ ] Model server: do not bake large weights into git. Download the GGUF at build time or mount a volume, and document it.
- [ ] Scan each image locally (`trivy image <name>`) and fix CRITICAL findings.
- [ ] Add the Docker build and Trivy jobs to GitHub Actions (finishes 9E).

### 10B. docker-compose (development only)
- [ ] `docker-compose.yml` with Postgres, Redis, vector store and all services, using env vars and `.env.example`.
- [ ] Healthchecks using `/ready`.
- [ ] Run migrations on start, and a seed or snapshot loader so the KB has data without re-scraping.
- [ ] **Network rule:** only the `tools` service has internet access in your design. Make sure no other container calls external sites.

### 10C. README
- [ ] Write the "how to run" section as a short list of commands that a new person can follow. Test it on a clean checkout, or ask your partner to.

**Done when:** `docker compose up` brings up the full system and you can use the UI.

> **📸 CHECKPOINT 10A (images):** `docker images` showing the distinct images tagged by SHA. Name: `docker_01_images.png`.
>
> **📸 CHECKPOINT 10B (image scan):** a Trivy scan result with no CRITICAL findings. Name: `docker_02_trivy_scan.png`.
>
> **📸 CHECKPOINT 10C (compose running):** `docker compose ps` with all services healthy. Name: `docker_03_compose_ps.png`.

---

## PHASE 11: Kubernetes (Week 9 to 10)

**Goal:** the whole system runs in namespace `idea-validator`, as the guide's Figure 3 describes.

### 11A. Cluster and manifests (`k8s/`)
- [ ] Create a local cluster (k3d recommended on your hardware) and a **local registry** for your images. Load or push SHA-tagged images.
- [ ] `Namespace idea-validator`.
- [ ] **Deployments + Services:** ui, gateway (api), orchestrator, agents, verdict, tools, kb, critic, model, agentops.
- [ ] **StatefulSets or PVCs:** Postgres, vector store, Redis (if persistent).
- [ ] **CronJobs:** scouts (every 6 hours or daily) and ingestion plus freshness check.
- [ ] **Jobs:** evaluation job and fine-tuned model import.
- [ ] **ConfigMaps:** weights, thresholds, floors, rubric versions, budgets. **Secrets:** API keys, DB password (never committed in plain form).
- [ ] **Ingress** as the single entry point.
- [ ] Every workload has **liveness and readiness probes** (`/health`, `/ready`), **requests and limits**, non-root and a pinned image.
- [ ] **Autoscaler (HPA)** on the gateway.
- [ ] Rolling update with `maxUnavailable: 0`.
- [ ] Add the manifest validation job to GitHub Actions (finishes 9E).

### 11B. Measure requests and limits
- [ ] Run a realistic workload (a few Validate runs, one Discover run) and record `kubectl top pods -n idea-validator`.
- [ ] Set requests and limits from those numbers and write the table in the report. Do not guess.

> **📸 CHECKPOINT 11A (all pods running):** `kubectl get pods -n idea-validator` with every pod Running or Completed. Name: `k8s_01_pods_running.png`.
>
> **📸 CHECKPOINT 11B (measurements):** `kubectl top pods` output used to set requests and limits. Name: `k8s_02_top_pods.png`.

### 11C. NetworkPolicy
- [ ] Default-deny egress for the namespace, then allow DNS, traffic between your services, and **internet egress only for the `tools` pods** (by label).
- [ ] **Test it:** from a non-tools pod try an external address and show it **failing**, then do the same from the tools pod and show it **working**.
- [ ] If the failing test succeeds (the policy is not enforced), your CNI is not enforcing NetworkPolicy. Switch to one that does (k3s default, Calico or Cilium).

> **📸 CHECKPOINT 11C (NetworkPolicy):** one screenshot with both terminals or commands: blocked from a normal pod, allowed from the tools pod. Name: `k8s_03_networkpolicy_test.png`.

### 11D. Rollout and rollback
- [ ] Update an image with `kubectl set image deploy/gateway ...` and watch `kubectl rollout status deploy/gateway -n idea-validator`.
- [ ] Deploy a **deliberately bad image** (for example one that fails its readiness probe), watch the rollout stall without downtime, then `kubectl rollout undo deploy/gateway -n idea-validator`.

> **📸 CHECKPOINT 11D (rollout and rollback):** the rollout, the bad release, and the `rollout undo` result. Name: `k8s_04_rollout_rollback.png`.

### 11E. Retake the product screenshots on Kubernetes
- [ ] Redo all `ui_*.png` shots from Phase 6, the trace, dashboard and drift report from Phase 7, now served from the cluster.
- [ ] Run the evaluation Job on the cluster and capture its logs.

> **📸 CHECKPOINT 11E:** `ui_01` to `ui_07`, `ops_01` to `ops_03`, and `k8s_05_eval_job_logs.png`.

**Done when:** the product works end to end through the Ingress, with everything running on Kubernetes.

---

## PHASE 12: Jenkins (Week 10)

**Goal:** delivery pipeline that runs after merge and nightly.

- [ ] Run **Jenkins in a container** with access to Docker and the cluster's kubeconfig (stored as a **Jenkins credential**, never in the repo).
- [ ] Because GitHub cannot reach Jenkins on your laptop, use **SCM polling** (for example every 2 minutes) or an ngrok tunnel.
- [ ] Write the `Jenkinsfile`, with stages: checkout, build and tag (commit SHA), push to registry, deploy to the test cluster (`kubectl set image`), smoke test, and (nightly) full evaluation compared with the stored baseline.
- [ ] Scripts: `scripts/push_images.sh`, `scripts/smoke_test.sh`, `scripts/check_eval.sh`.
- [ ] A failure must **stop the pipeline so nothing is deployed**. A `post { failure { ... } }` block states this.
- [ ] Nightly trigger with `triggers { cron(...) }`, which runs the Eval stage only on the timer.
- [ ] Run it once green. Then **break it on purpose** (for example a failing smoke test or a bad image tag), confirm nothing was deployed, and fix it.
- [ ] Optional bonus: show that a failing nightly evaluation blocks promotion.

> **📸 CHECKPOINT 12A (Jenkins green):** the pipeline stage view, all stages green. Name: `ci_03_jenkins_green.png`.
>
> **📸 CHECKPOINT 12B (Jenkins failing):** a failing run, with the stage that stopped the pipeline visible. Name: `ci_04_jenkins_failing.png`.

---

## PHASE 13: Report, polish and submission (last 4 to 5 days)

### 13A. Final checks (Day 1)
- [ ] Fresh clone on a clean folder, follow the README exactly, and confirm the system starts.
- [ ] No secrets in the repo. `.env.example` present.
- [ ] Repo is visible to the markers.
- [ ] Both members have commits, PRs authored and reviews that match the contribution table.

### 13B. Report (PDF, at most 10 pages, not counting screenshots) (Days 2 to 3)
Follow this exact section order:

1. Summary and changes from the given architecture (mention your container grouping and why).
2. Modules and architecture figure.
3. Verdict design: gates, weights, thresholds, rubrics, tuning results with **before and after confusion matrix**, one worked example.
4. Knowledge base: sources, card counts, retrieval results.
5. Fine-tuning: data, settings, comparison table, one case where it did not help.
6. AgenticOps results: traces, budgets, drift, dashboard, eval results.
7. Platform: pipeline, Kubernetes design, how you measured requests and limits.
8. Known limits and next steps.

### 13C. Screenshot pack (Day 3)
- [ ] Assemble the screenshots from Section 15 into one PDF or a `screenshots/` section, each with a **one-line caption**.

### 13D. Other deliverables (Day 4)
- [ ] **AI-usage log** complete (date, tool, what you asked, what you changed, why).
- [ ] **At least 3 design decision records** in `docs/decisions/` (one page or less each).
- [ ] **Contribution table**, signed by both, matching the git history.
- [ ] Final README polish.

### 13E. Submit (Day 5, with spare time)
- [ ] Submit on GCR: GitHub link, report PDF, screenshots, AI log and decision records, contribution table.
- [ ] Open the submission as if you were the marker and confirm every link works.
- [ ] Tag a release in git (`v1.0`) and keep the cluster state or a short demo recording as a backup.

---

## 14. Weekly timeline at a glance

| Week | Phases | Main output |
|---|---|---|
| 1 | 0, 1 | Schemas, tool layer, scouts, ingestion started |
| 2 | 1, 2 | 1,500+ cards, hybrid search, retrieval baseline |
| 3 | 2, 3 | Niches and gaps, rubrics, verdict engine with tests |
| 4 | 3, 4 | Fine-tuning dataset, training on Colab |
| 5 | 4, 5 | Scorer model, validators, critic, generator agents |
| 6 | 5, 6 | Orchestrator, backend, cache, gateway |
| 7 | 6, 7, 8 | UI, AgenticOps, labelled set started |
| 8 | 8, 9 | Tuning done, code freeze, GitHub workflow and Actions |
| 9 | 10, 11 | Docker images, compose, Kubernetes manifests |
| 10 | 11, 12 | NetworkPolicy, rollout, Jenkins |
| 11 | 13 | Report, screenshots, submission |

If your deadline is shorter, merge Phases 1 and 2, cut M8 debate rounds to the minimum that works, and keep the dashboard simple (a page reading `/metrics`). **Do not cut:** the verdict engine and its tests, the fine-tuning comparison, NetworkPolicy, rollout and rollback, or Jenkins. These are specifically required in the screenshots.

---

## 15. Master screenshot checklist

Tick each one when saved **and** captioned.

| # | File | What it shows | Taken in |
|---|---|---|---|
| 1 | `kb_01_card_counts.png` | Cards per source and total | Phase 1 |
| 2 | `kb_02_retrieval_results.png` | Retrieval recall table (vector vs keyword vs hybrid) | Phase 2 |
| 3 | `verdict_01_unit_tests.png` | Verdict engine tests green incl. worked example | Phase 3 |
| 4 | `ft_01_comparison_table.png` | Base vs fine-tuned vs hosted | Phase 4 |
| 5 | `ft_02_training_loss.png` | Training and validation loss | Phase 4 |
| 6 | `ft_03_failure_case.png` | Case where fine-tuning did not help | Phase 4 |
| 7 | `agentops_01_behaviour_tests.png` | Behaviour tests (invalid JSON, timeout, empty source, poison) | Phase 5 |
| 8 | `ui_01` to `ui_07` | Profile, Discover, verdict card, challenge, what-if v2, INSUFFICIENT EVIDENCE, live view and approval | Phase 6, **retake in 11E** |
| 9 | `ops_01_trace.png` | One run's trace | Phase 7, retake in 11E |
| 10 | `ops_02_dashboard.png` | Dashboard | Phase 7, retake in 11E |
| 11 | `ops_03_drift_report.png` | Drift report | Phase 7, retake in 11E |
| 12 | `ops_04_budget_stop.png` | Budget stop and approval | Phase 7 |
| 13 | `tuning_01` and `tuning_02` | Before and after confusion matrices | Phase 8 |
| 14 | `git_01_protected_main.png` | Protected main rules | Phase 9 |
| 15 | `git_02_pr_required_checks.png` | PR with required checks | Phase 9 |
| 16 | `git_03_merge_conflict_pr.png` | Merge-conflict PR resolved | Phase 9 |
| 17 | `ci_01_actions_green.png` | Green GitHub Actions run | Phase 9 |
| 18 | `ci_02_actions_failing.png` | Failing GitHub Actions run | Phase 9 |
| 19 | `docker_01_images.png` | Images tagged by SHA | Phase 10 |
| 20 | `docker_02_trivy_scan.png` | Image scan | Phase 10 |
| 21 | `docker_03_compose_ps.png` | Compose services healthy | Phase 10 |
| 22 | `k8s_01_pods_running.png` | All pods running | Phase 11 |
| 23 | `k8s_02_top_pods.png` | Measurements for requests and limits | Phase 11 |
| 24 | `k8s_03_networkpolicy_test.png` | Blocked vs allowed egress | Phase 11 |
| 25 | `k8s_04_rollout_rollback.png` | Rollout, bad release, rollback | Phase 11 |
| 26 | `k8s_05_eval_job_logs.png` | Evaluation Job on the cluster | Phase 11 |
| 27 | `ci_03_jenkins_green.png` | Green Jenkins run | Phase 12 |
| 28 | `ci_04_jenkins_failing.png` | Failing Jenkins run | Phase 12 |

Required by the description: items 14, 15, 16, 17, 18, 27, 28, 22, 25, 24, the UI set, 9, 10, 11, and the retrieval and fine-tuning results (2, 4).

---

## 16. Risks and how this plan handles them

| Risk | What to do |
|---|---|
| Docker, Jenkins and Kubernetes left for the end (the guide's top warning) | Phase 0 rules make services container-ready. At the end of Phase 8, spend half a day running **one** service (the verdict engine) in a container and one pod in k3d, as a thin test of your setup. If it fails, you learn this a week early. |
| 8 GB RAM laptop | Group containers, use k3d, train on Colab, serve a 1B GGUF model, or use your partner's machine or a free-tier VM. |
| Scraping too slow for 1,500 cards | Start ingestion in Phase 1 and let it run in the background. Keep the snapshot. |
| A model decides the verdict by accident | Verdict logic stays only in M11. Add a test that M11 imports no LLM client. |
| Scores with no evidence ids | Scorers abstain. M12 checks claims. Eval harness reports the evidence-id rate. |
| Cache returns stale verdicts after a rule change | Include profile version and rubric version in the cache key. Test it. |
| Uneven contribution | Review the git log weekly. Swap tasks if one person is far ahead. |
| Secrets pushed to git | Use `.env` plus `.gitignore` from day 1, and run a secret scan in Phase 9A. |
| Overfitting thresholds to your labelled set | Hold out a few ideas for a final check in Phase 8. |
