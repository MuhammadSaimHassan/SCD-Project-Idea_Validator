"""Normalize raw scout items into validated IdeaCards, chunk, and embed."""

import hashlib
import re
from datetime import UTC, datetime

from services.scouts.src.connectors import RawScoutItem
from shared.schemas import IdeaCard

NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def canonical_url(url: str) -> str:
    """Normalize URL for exact duplicate detection."""
    cleaned = url.strip().rstrip("/")
    return cleaned.lower()


def text_fingerprint(text: str) -> str:
    """Normalized alphanumeric fingerprint for near-duplicate detection."""
    norm = NON_ALNUM_RE.sub(" ", text.lower()).strip()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:24]


def make_card_id(source: str, url: str) -> str:
    """Deterministic card id derived from source and canonical URL."""
    digest = hashlib.sha256(f"{source}:{canonical_url(url)}".encode()).hexdigest()[:12]
    return f"card_{digest}"


def normalize_item(item: RawScoutItem) -> IdeaCard:
    """Convert RawScoutItem into a schema-validated IdeaCard."""
    now_iso = datetime.now(UTC).date().isoformat()
    card_id = make_card_id(item.source, item.url)
    clean_text = item.text.strip() or item.summary.strip() or item.name.strip()
    return IdeaCard(
        id=card_id,
        name=item.name.strip() or "Untitled Idea",
        summary=item.summary.strip() or item.name.strip(),
        problem=item.problem.strip() or item.summary.strip(),
        customer=item.customer.strip() or "general users",
        niche_tags=[t.strip().lower() for t in item.niche_tags if t.strip()],
        stage=item.stage.strip() or "unknown",
        funding_usd=item.funding_usd,
        source=item.source,
        url=item.url.strip(),
        published_at=item.published_at,
        fetched_at=now_iso,
        text=clean_text,
    )


def chunk_card(card: IdeaCard, max_chars: int = 400, overlap: int = 50) -> list[dict[str, str]]:
    """Split card text into chunks while preserving card_id on every chunk."""
    text = card.text.strip()
    if len(text) <= max_chars:
        return [
            {
                "chunk_id": f"{card.id}#c0",
                "card_id": card.id,
                "text": text,
                "source": card.source,
                "url": card.url,
            }
        ]

    chunks: list[dict[str, str]] = []
    start = 0
    idx = 0
    step = max(1, max_chars - overlap)
    while start < len(text):
        piece = text[start : start + max_chars].strip()
        if piece:
            chunks.append(
                {
                    "chunk_id": f"{card.id}#c{idx}",
                    "card_id": card.id,
                    "text": piece,
                    "source": card.source,
                    "url": card.url,
                }
            )
            idx += 1
        start += step
    return chunks


def hash_embed(text: str, dim: int = 64) -> list[float]:
    """Deterministic lightweight local embedding vector (normalized L2)."""
    vec = [0.0] * dim
    tokens = NON_ALNUM_RE.sub(" ", text.lower()).split()
    if not tokens:
        return vec
    for tok in tokens:
        digest = hashlib.blake2b(tok.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "little") % dim
        sign = 1.0 if (digest[4] % 2 == 0) else -1.0
        vec[bucket] += sign
    norm = sum(v * v for v in vec) ** 0.5
    if norm > 0:
        vec = [round(v / norm, 6) for v in vec]
    return vec
