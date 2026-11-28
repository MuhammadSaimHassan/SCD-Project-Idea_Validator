# Verdict tuning dataset and evaluation

The evaluation set must contain 25–30 or more ideas not used for fine-tuning.
Both project members label every case independently. Record both reviewers and
the adjudicated human verdict. Use `train` for tuning and keep a preselected
`holdout` split untouched until the tuned configuration is evaluated.

Each non-empty line in `labeled_ideas.jsonl` is one JSON object:

```json
{
  "case_id": "idea-001",
  "split": "train",
  "idea_text": "The student idea being evaluated",
  "request": {
    "idea_id": "human-eval-001",
    "version": 1,
    "run_id": "label-run-001",
    "profile": {},
    "scores": [],
    "gate_inputs": {}
  },
  "labels": [
    {"reviewer": "Member A", "verdict": "GO"},
    {"reviewer": "Member B", "verdict": "PIVOT"}
  ],
  "adjudicated_verdict": "PIVOT",
  "adjudicator": "Member A and Member B"
}
```

`profile`, `scores`, and `gate_inputs` must be complete valid shared-schema
objects. Include all verdict classes: GO, PIVOT (borderline), NO-GO, and
INSUFFICIENT_EVIDENCE (thin evidence). Do not add generated or assumed human
labels. The runner rejects one-reviewer cases, duplicate IDs, missing classes,
overlap with fine-tuning data, or fewer than 25 cases.

Run the evaluation without modifying production configuration:

```powershell
python -m eval.verdict.cli
```

The output includes before and after confusion matrices for both train and
holdout splits, accuracy, and the dangerous “GO when human said NO-GO” count.
The tuner only optimizes on `train`; use `--write-config` only after reviewing
the holdout report with both labelers.
