"""Export all canonical Pydantic models to JSON Schema files under schemas/."""

import json
from pathlib import Path

from pydantic import BaseModel

from .contracts import (
    CheckRequest,
    CheckResponse,
    FetchRequest,
    FetchResponse,
    ScoreRequest,
    SearchRequest,
    SearchResponse,
    VerdictRequest,
    WhatIfRequest,
)
from .models import (
    DimensionScore,
    EvidenceItem,
    IdeaCard,
    StudentProfile,
    TraceRecord,
    Verdict,
)

SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "idea_card": IdeaCard,
    "student_profile": StudentProfile,
    "evidence_item": EvidenceItem,
    "dimension_score": DimensionScore,
    "verdict": Verdict,
    "trace_record": TraceRecord,
    "fetch_request": FetchRequest,
    "fetch_response": FetchResponse,
    "search_request": SearchRequest,
    "search_response": SearchResponse,
    "score_request": ScoreRequest,
    "verdict_request": VerdictRequest,
    "whatif_request": WhatIfRequest,
    "check_request": CheckRequest,
    "check_response": CheckResponse,
}


def export_schemas(output_dir: Path) -> list[Path]:
    """Write formatted JSON Schema files to output_dir and return created paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, model in SCHEMA_MODELS.items():
        target = output_dir / f"{name}.schema.json"
        schema_json = json.dumps(model.model_json_schema(), indent=2) + "\n"
        target.write_text(schema_json, encoding="utf-8")
        written.append(target)
    return written


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    paths = export_schemas(root / "schemas")
    print(f"Exported {len(paths)} JSON schema files to {root / 'schemas'}")
