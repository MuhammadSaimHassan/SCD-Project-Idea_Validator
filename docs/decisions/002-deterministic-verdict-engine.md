# ADR-002: Keep verdict classification deterministic and code-owned

- **Status:** Accepted
- **Context:** The system combines model-generated dimension scores with a final
  Go / No-Go recommendation. Letting a language model choose the final verdict
  would make hard gates, sensitivity checks, and user challenges difficult to
  reproduce or audit.
- **Options:**
  1. Ask an LLM to produce the final verdict.
  2. Use a deterministic rules engine with versioned thresholds and weights.
  3. Use a model verdict and apply hard gates as post-processing.
- **Decision:** Use M11's deterministic engine for the final verdict. Models
  provide dimension scores; code applies the evidence, feasibility, risk, and
  duplicate gates, weights, thresholds, confidence, and sensitivity rules.
- **Why:** The same validated request and versioned configuration produce the
  same verdict. This makes challenge and what-if results reproducible and keeps
  unsupported model output from bypassing hard gates.
- **Trade-offs:** The engine is only as good as its scoring inputs and
  human-selected thresholds. We therefore keep tuning separate from fine-tuning,
  require independent labels and a held-out set, and report false GO decisions
  against human NO-GO labels before promoting configuration.
- **Validation:** `python -m eval.verdict.cli` compares baseline and tuned
  confusion matrices. Production config changes require `--write-config` and a
  non-regressing held-out report.
- **AI use:** AI assisted with implementation and documentation; project
  members remain responsible for labels, adjudication, and accepting any tuned
  configuration.
