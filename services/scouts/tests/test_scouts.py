"""Unit tests for M4 Scouts: source parsing, failure isolation, and M5-only egress."""

import ast
import json
from pathlib import Path

from services.scouts.src.connectors import run_scouts
from shared.schemas import FetchRequest, FetchResponse

ROOT = Path(__file__).resolve().parents[3]


class FakeToolsClient:
    """In-memory mock of M5 POST /fetch for deterministic scout unit tests."""

    def __init__(self, fail_source: str | None = None) -> None:
        self.fail_source = fail_source
        self.requested_urls: list[str] = []

    def fetch(self, req: FetchRequest) -> FetchResponse:
        self.requested_urls.append(req.url)
        if self.fail_source and req.source == self.fail_source:
            raise RuntimeError(f"Simulated upstream failure for {req.source}")

        if req.source == "hackernews":
            body = json.dumps(
                {
                    "hits": [
                        {
                            "objectID": "42",
                            "title": "Show HN: Fast SQLite RAG",
                            "url": "https://example.com/rag",
                            "story_text": "Local RAG without Docker overhead",
                            "created_at": "2026-10-01T00:00:00Z",
                        }
                    ]
                }
            )
        elif req.source == "github":
            body = json.dumps(
                {
                    "items": [
                        {
                            "full_name": "acme/cli-triage",
                            "html_url": "https://github.com/acme/cli-triage",
                            "description": "Triage flaky CI runs locally",
                            "topics": ["devtools", "ci"],
                            "language": "Python",
                            "created_at": "2026-09-12T00:00:00Z",
                        }
                    ]
                }
            )
        elif req.source == "yc":
            body = json.dumps(
                [
                    {
                        "name": "MetricPulse",
                        "slug": "metricpulse",
                        "one_liner": "Monitor LLM cost drift",
                        "long_description": "Tracks agent token cost and latency.",
                        "tags": ["ai", "observability"],
                        "stage": "seed",
                    }
                ]
            )
        else:
            body = "{}"

        return FetchResponse(
            url=req.url,
            source=req.source,
            status_code=200,
            content=body,
            fetched_at="2026-11-28T00:00:00Z",
        )


def test_scouts_never_call_external_urls_directly() -> None:
    forbidden_modules = {"requests", "urllib"}
    for path in (ROOT / "services" / "scouts" / "src").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in forbidden_modules
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in forbidden_modules
            elif (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id in {"httpx", "requests"}
                and node.attr in {"get", "AsyncClient", "Client"}
            ):
                raise AssertionError(
                    f"Direct {node.value.id}.{node.attr} found in {path.name}"
                )


def test_run_scouts_isolates_failing_source() -> None:
    tools = FakeToolsClient(fail_source="github")
    items, errors = run_scouts(["hn", "github", "yc"], tools, per_source_limit=1)
    assert "github" in errors
    assert len(items) == 2
    assert {item.source for item in items} == {"hackernews", "yc"}
    assert len(tools.requested_urls) >= 3
