"""M4 Scout connectors reaching the internet strictly through M5 POST /fetch."""

import json
import logging
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from shared.schemas import FetchRequest, FetchResponse

logger = logging.getLogger("scouts")


class ToolsClient(Protocol):
    """Protocol for M5 Tool Layer client."""

    def fetch(self, req: FetchRequest) -> FetchResponse:
        ...


class HttpToolsClient:
    """Calls remote M5 Tool Layer container over HTTP."""

    def __init__(self, tools_url: str, timeout: float = 20.0) -> None:
        self._base = tools_url.rstrip("/")
        self._timeout = timeout

    def fetch(self, req: FetchRequest) -> FetchResponse:
        resp = httpx.post(
            f"{self._base}/fetch",
            json=req.model_dump(mode="json"),
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return FetchResponse.model_validate(resp.json())


@dataclass
class RawScoutItem:
    """Normalized intermediate item returned by a scout connector."""

    source: str
    name: str
    url: str
    summary: str
    problem: str
    customer: str
    niche_tags: list[str]
    stage: str
    funding_usd: int | None
    published_at: str | None
    text: str


def scout_hackernews(tools: ToolsClient, limit: int = 500) -> list[RawScoutItem]:
    """Fetch Show HN / Ask HN / startup pain posts via Algolia HN API through M5."""
    items: list[RawScoutItem] = []
    queries = ["Show HN", "Ask HN", "pain point", "developer tool", "automation"]
    per_page = 100
    seen_urls: set[str] = set()

    for query in queries:
        for page in range(5):
            if len(items) >= limit:
                return items
            resp = tools.fetch(
                FetchRequest(
                    source="hackernews",
                    url="https://hn.algolia.com/api/v1/search",
                    params={
                        "query": query,
                        "tags": "story",
                        "hitsPerPage": per_page,
                        "page": page,
                    },
                )
            )
            data = json.loads(resp.content)
            hits = data.get("hits", [])
            if not hits:
                break
            for hit in hits:
                object_id = str(hit.get("objectID", ""))
                url = str(
                    hit.get("url")
                    or f"https://news.ycombinator.com/item?id={object_id}"
                )
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                title = str(hit.get("title") or "HN Story").strip()
                story_text = str(hit.get("story_text") or "").strip()
                created_at = str(hit.get("created_at") or "")[:10] or None
                combined = f"{title}. {story_text}".strip()
                items.append(
                    RawScoutItem(
                        source="hackernews",
                        name=title[:120],
                        url=url,
                        summary=title[:220],
                        problem=story_text[:300] if story_text else title[:220],
                        customer="developers and startup founders",
                        niche_tags=["hackernews", query.lower().replace(" ", "_")],
                        stage="launched" if "Show HN" in title else "unknown",
                        funding_usd=None,
                        published_at=created_at,
                        text=combined,
                    )
                )
                if len(items) >= limit:
                    return items
    return items


def scout_github(tools: ToolsClient, limit: int = 500) -> list[RawScoutItem]:
    """Fetch public developer/product repositories via GitHub REST API through M5."""
    items: list[RawScoutItem] = []
    topics = [
        "cli developer-tools",
        "rag agentic",
        "self-hosted productivity",
        "devops monitoring",
        "education study tool",
        "saas starter",
    ]
    seen_urls: set[str] = set()

    for q in topics:
        for page in range(1, 3):
            if len(items) >= limit:
                return items
            resp = tools.fetch(
                FetchRequest(
                    source="github",
                    url="https://api.github.com/search/repositories",
                    params={"q": q, "sort": "stars", "per_page": 100, "page": page},
                )
            )
            data = json.loads(resp.content)
            repos = data.get("items", [])
            if not repos:
                break
            for repo in repos:
                url = str(repo.get("html_url") or "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                name = str(repo.get("full_name") or repo.get("name") or "GitHub Repo")
                desc = str(repo.get("description") or name).strip()
                repo_topics = [str(t) for t in (repo.get("topics") or [])][:5]
                lang = str(repo.get("language") or "").lower()
                tags = repo_topics + ([lang] if lang else [])
                pub = str(repo.get("created_at") or "")[:10] or None
                items.append(
                    RawScoutItem(
                        source="github",
                        name=name[:120],
                        url=url,
                        summary=desc[:220],
                        problem=desc[:300],
                        customer="software engineers",
                        niche_tags=tags or ["github"],
                        stage="launched",
                        funding_usd=None,
                        published_at=pub,
                        text=f"{name}: {desc}. Topics: {', '.join(tags)}",
                    )
                )
                if len(items) >= limit:
                    return items
    return items


def scout_yc(tools: ToolsClient, limit: int = 550) -> list[RawScoutItem]:
    """Fetch public YC directory company cards via M5."""
    resp = tools.fetch(
        FetchRequest(
            source="yc",
            url="https://yc-oss.github.io/api/companies/all.json",
        )
    )
    companies = json.loads(resp.content)
    if not isinstance(companies, list):
        return []

    items: list[RawScoutItem] = []
    for comp in companies[:limit]:
        name = str(comp.get("name") or "YC Company").strip()
        slug = str(comp.get("slug") or "").strip()
        url = str(
            comp.get("url")
            or comp.get("website")
            or f"https://www.ycombinator.com/companies/{slug}"
        )
        one_liner = str(comp.get("one_liner") or name).strip()
        long_desc = str(comp.get("long_description") or one_liner).strip()
        tags = [str(t).lower().replace(" ", "-") for t in (comp.get("tags") or [])][:5]
        industry = str(comp.get("industry") or "").lower().replace(" ", "-")
        if industry and industry not in tags:
            tags.append(industry)
        stage = str(comp.get("stage") or "seed").lower()
        items.append(
            RawScoutItem(
                source="yc",
                name=name[:120],
                url=url,
                summary=one_liner[:220],
                problem=long_desc[:350],
                customer=str(comp.get("subindustry") or "startups and SMBs"),
                niche_tags=tags or ["yc"],
                stage=stage,
                funding_usd=None,
                published_at=None,
                text=f"{name} — {one_liner}. {long_desc}".strip(),
            )
        )
    return items


def scout_reddit(tools: ToolsClient, limit: int = 200) -> list[RawScoutItem]:
    """Fetch public startup/side-project discussions via Reddit JSON API through M5."""
    items: list[RawScoutItem] = []
    subreddits = ["SideProject", "SaaS", "startups"]
    for sub in subreddits:
        if len(items) >= limit:
            break
        resp = tools.fetch(
            FetchRequest(
                source="reddit",
                url=f"https://www.reddit.com/r/{sub}/top.json",
                params={"t": "month", "limit": 100},
            )
        )
        data = json.loads(resp.content)
        children = data.get("data", {}).get("children", [])
        for entry in children:
            post = entry.get("data", {})
            permalink = str(post.get("permalink") or "")
            url = f"https://www.reddit.com{permalink}" if permalink else str(post.get("url") or "")
            if not url:
                continue
            title = str(post.get("title") or "Reddit Post").strip()
            selftext = str(post.get("selftext") or "").strip()
            items.append(
                RawScoutItem(
                    source="reddit",
                    name=title[:120],
                    url=url,
                    summary=title[:220],
                    problem=selftext[:350] if selftext else title[:220],
                    customer="indie builders and startup founders",
                    niche_tags=["reddit", sub.lower()],
                    stage="unknown",
                    funding_usd=None,
                    published_at=None,
                    text=f"{title}. {selftext}".strip(),
                )
            )
            if len(items) >= limit:
                break
    return items


SCOUT_REGISTRY: dict[str, Any] = {
    "hn": scout_hackernews,
    "github": scout_github,
    "yc": scout_yc,
    "reddit": scout_reddit,
}


def run_scouts(
    sources: list[str],
    tools: ToolsClient,
    per_source_limit: int = 550,
) -> tuple[list[RawScoutItem], dict[str, str]]:
    """Run scouts with per-source failure isolation."""
    collected: list[RawScoutItem] = []
    errors: dict[str, str] = {}
    for source in sources:
        fn = SCOUT_REGISTRY.get(source)
        if fn is None:
            errors[source] = f"Unknown scout source: {source}"
            continue
        try:
            batch = fn(tools, limit=per_source_limit)
            collected.extend(batch)
            logger.info("scout=%s fetched=%d", source, len(batch))
        except Exception as exc:  # noqa: BLE001
            errors[source] = str(exc)
            logger.warning("scout=%s failed error=%s", source, exc)
    return collected, errors
