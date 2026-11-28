"""CLI entrypoint for M4 Scouts (CronJob ready: --source hn)."""

import argparse
import json
import sys

from services.tools.src.config import ToolsSettings
from services.tools.src.fetcher import ToolFetcher

from .config import settings
from .connectors import HttpToolsClient, ToolsClient, run_scouts


def _build_tools_client() -> ToolsClient:
    if settings.tools_url:
        return HttpToolsClient(settings.tools_url, timeout=settings.request_timeout_seconds)
    return ToolFetcher(ToolsSettings())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run M4 Scout connector via M5 Tool Layer")
    parser.add_argument("--source", required=True, help="Source name: hn | github | yc | reddit")
    parser.add_argument("--limit", type=int, default=100, help="Max items to collect")
    args = parser.parse_args(argv)

    tools = _build_tools_client()
    items, errors = run_scouts([args.source], tools, per_source_limit=args.limit)
    print(
        json.dumps(
            {
                "source": args.source,
                "fetched": len(items),
                "errors": errors,
            },
            indent=2,
        )
    )
    return 1 if errors and not items else 0


if __name__ == "__main__":
    sys.exit(main())
