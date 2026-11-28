"""Hybrid retrieval (dense vector + Okapi BM25 + RRF reranking) for M6 Knowledge Base."""

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from shared.schemas import EvidenceItem, IdeaCard, SearchRequest, SearchResponse

TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def _dense_embed(text: str, dim: int = 384) -> list[float]:
    """Build a normalized dense vector combining word tokens and char 3-grams."""
    vec = [0.0] * dim
    tokens = _tokenize(text)
    if not tokens:
        return vec
    features: list[tuple[str, float]] = [(f"w:{tok}", 1.5) for tok in tokens]
    joined = " ".join(tokens)
    for idx in range(max(0, len(joined) - 2)):
        gram = joined[idx : idx + 3]
        if gram.strip():
            features.append((f"g:{gram}", 0.5))

    for feat, weight in features:
        digest = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "little") % dim
        sign = 1.0 if (digest[4] % 2 == 0) else -1.0
        vec[bucket] += sign * weight

    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0.0:
        vec = [v / norm for v in vec]
    return vec


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


@dataclass
class IndexedChunk:
    evidence_id: str
    card_id: str
    name: str
    text: str
    source: str
    url: str
    niche_tags: list[str]
    published_at: str | None
    fetched_at: str
    tokens: list[str]
    tf: Counter[str]
    vector: list[float]


class HybridKnowledgeBase:
    """In-memory hybrid vector + BM25 search engine loaded from IdeaCard snapshot."""

    def __init__(self, cards: list[IdeaCard] | None = None) -> None:
        self._cards: list[IdeaCard] = cards or []
        self._chunks: list[IndexedChunk] = []
        self._doc_freq: Counter[str] = Counter()
        self._avg_len: float = 1.0
        if self._cards:
            self._build_index()

    @classmethod
    def from_snapshot(cls, snapshot_path: Path) -> "HybridKnowledgeBase":
        if not snapshot_path.exists():
            return cls([])
        cards: list[IdeaCard] = []
        with snapshot_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    cards.append(IdeaCard.model_validate_json(line))
        return cls(cards)

    @property
    def card_count(self) -> int:
        return len(self._cards)

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    def _build_index(self) -> None:
        self._chunks = []
        self._doc_freq = Counter()
        for card in self._cards:
            full_text = (
                f"{card.name}. {card.summary}. {card.problem}. "
                f"Tags: {' '.join(card.niche_tags)}. {card.text}"
            ).strip()
            chunks = self._chunk_text(card, full_text)
            for chunk_id, chunk_text in chunks:
                toks = _tokenize(chunk_text)
                tf = Counter(toks)
                for tok in tf:
                    self._doc_freq[tok] += 1
                self._chunks.append(
                    IndexedChunk(
                        evidence_id=chunk_id,
                        card_id=card.id,
                        name=card.name,
                        text=chunk_text,
                        source=card.source,
                        url=card.url,
                        niche_tags=[t.lower() for t in card.niche_tags],
                        published_at=str(card.published_at) if card.published_at else None,
                        fetched_at=str(card.fetched_at),
                        tokens=toks,
                        tf=tf,
                        vector=_dense_embed(chunk_text),
                    )
                )
        total_len = sum(len(c.tokens) for c in self._chunks)
        self._avg_len = (total_len / len(self._chunks)) if self._chunks else 1.0

    @staticmethod
    def _chunk_text(
        card: IdeaCard, text: str, max_chars: int = 450, overlap: int = 50
    ) -> list[tuple[str, str]]:
        if len(text) <= max_chars:
            return [(f"{card.id}#c0", text)]
        out: list[tuple[str, str]] = []
        start = 0
        idx = 0
        step = max(1, max_chars - overlap)
        while start < len(text) and idx < 4:
            piece = text[start : start + max_chars].strip()
            if piece:
                out.append((f"{card.id}#c{idx}", piece))
                idx += 1
            start += step
        return out

    def _passes_filters(self, chunk: IndexedChunk, req: SearchRequest) -> bool:
        if req.source_filter:
            allowed_src = {s.lower() for s in req.source_filter}
            if chunk.source.lower() not in allowed_src:
                return False
        if req.niche_filter:
            wanted = {n.lower() for n in req.niche_filter}
            if not wanted.intersection(chunk.niche_tags):
                return False
        if req.date_from and chunk.published_at and chunk.published_at < req.date_from:
            return False
        return not (req.date_to and chunk.published_at and chunk.published_at > req.date_to)

    def _bm25_score(self, query_tokens: list[str], chunk: IndexedChunk) -> float:
        n_docs = len(self._chunks)
        if n_docs == 0 or not chunk.tokens:
            return 0.0
        k1 = 1.5
        b = 0.75
        doc_len = len(chunk.tokens)
        score = 0.0
        for tok in query_tokens:
            df = self._doc_freq.get(tok, 0)
            if df == 0:
                continue
            idf = math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))
            freq = chunk.tf.get(tok, 0)
            if freq == 0:
                continue
            denom = freq + k1 * (1.0 - b + b * (doc_len / self._avg_len))
            score += idf * ((freq * (k1 + 1.0)) / denom)
        return score

    def search(self, req: SearchRequest, mode: str = "hybrid") -> SearchResponse:
        """Search KB using 'vector', 'keyword' (BM25), or 'hybrid' (RRF + rerank)."""
        candidates = [c for c in self._chunks if self._passes_filters(c, req)]
        if not candidates:
            return SearchResponse(query=req.query, items=[], total_candidates=0)

        q_tokens = _tokenize(req.query)
        q_vec = _dense_embed(req.query)

        vec_ranked = sorted(
            candidates,
            key=lambda c: _cosine(q_vec, c.vector),
            reverse=True,
        )
        bm25_ranked = sorted(
            candidates,
            key=lambda c: self._bm25_score(q_tokens, c),
            reverse=True,
        )

        if mode == "vector":
            chosen = vec_ranked
        elif mode == "keyword":
            chosen = bm25_ranked
        else:
            pool_size = max(req.top_k * 8, 40)
            rrf_scores: dict[str, float] = defaultdict(float)
            chunk_map: dict[str, IndexedChunk] = {}
            for rank, c in enumerate(vec_ranked[:pool_size], start=1):
                rrf_scores[c.evidence_id] += 1.0 / (60.0 + rank)
                chunk_map[c.evidence_id] = c
            for rank, c in enumerate(bm25_ranked[:pool_size], start=1):
                rrf_scores[c.evidence_id] += 1.0 / (60.0 + rank)
                chunk_map[c.evidence_id] = c

            # Reranker: boost exact phrase / product-name hits and query token coverage
            q_lower = req.query.lower().strip()
            q_set = set(q_tokens)
            for eid, chunk in chunk_map.items():
                name_lower = chunk.name.lower()
                text_lower = chunk.text.lower()
                if q_lower and (q_lower in name_lower or q_lower in text_lower):
                    rrf_scores[eid] += 0.05
                if q_set:
                    overlap = len(q_set.intersection(chunk.tf.keys())) / len(q_set)
                    rrf_scores[eid] += 0.02 * overlap

            chosen = sorted(
                chunk_map.values(),
                key=lambda c: rrf_scores[c.evidence_id],
                reverse=True,
            )

        # Deduplicate by card_id in top_k results so citations span distinct cards
        items: list[EvidenceItem] = []
        seen_cards: set[str] = set()
        for chunk in chosen:
            if chunk.card_id in seen_cards:
                continue
            seen_cards.add(chunk.card_id)
            items.append(
                EvidenceItem(
                    evidence_id=chunk.evidence_id,
                    card_id=chunk.card_id,
                    quote=chunk.text[:280],
                    source=chunk.source,
                    url=chunk.url,
                    retrieved_at=chunk.fetched_at,
                )
            )
            if len(items) >= req.top_k:
                break

        return SearchResponse(
            query=req.query,
            items=items,
            total_candidates=len(candidates),
        )

    def stats(self) -> dict[str, object]:
        """Return freshness and coverage tracking metrics."""
        by_source: Counter[str] = Counter()
        last_fetched: dict[str, str] = {}
        niches: Counter[str] = Counter()
        for card in self._cards:
            by_source[card.source] += 1
            f_str = str(card.fetched_at)
            if card.source not in last_fetched or f_str > last_fetched[card.source]:
                last_fetched[card.source] = f_str
            for tag in card.niche_tags:
                niches[tag] += 1
        return {
            "total_cards": len(self._cards),
            "total_chunks": len(self._chunks),
            "counts_by_source": dict(by_source),
            "last_fetched_by_source": last_fetched,
            "top_niches": dict(niches.most_common(15)),
        }


def load_cards_from_jsonl(path: Path) -> list[IdeaCard]:
    """Helper to read IdeaCards from JSONL."""
    cards: list[IdeaCard] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                cards.append(IdeaCard.model_validate(json.loads(line)))
    return cards
