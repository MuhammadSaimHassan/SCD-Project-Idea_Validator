"""Read-only registry of versioned prompts and scoring rubrics."""

import hashlib
from pathlib import Path
from typing import Any

from shared.config import load_rubrics


def registry_snapshot(repository_root: Path) -> dict[str, list[dict[str, Any]]]:
    prompt_root = repository_root / "prompts"
    prompts = [
        {
            "name": path.parent.name,
            "version": path.stem,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "path": str(path.relative_to(repository_root)),
        }
        for path in sorted(prompt_root.glob("**/*.md"))
    ]
    rubrics = load_rubrics(repository_root / "rubrics")
    rubric_entries = [
        {
            "dimension": dimension.value,
            "version": str(content.get("rubric_version", "unversioned")),
        }
        for dimension, content in sorted(rubrics.items(), key=lambda item: item[0].value)
    ]
    return {"prompts": prompts, "rubrics": rubric_entries}
