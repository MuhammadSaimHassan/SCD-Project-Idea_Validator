"""Repeatable M6i ingestion pipeline: dedupe, chunk, embed, index, snapshot."""

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from services.scouts.src.connectors import RawScoutItem
from shared.schemas import IdeaCard

from .normalizer import canonical_url, chunk_card, hash_embed, normalize_item, text_fingerprint


@dataclass
class IngestionStats:
    run_id: str
    added: int
    dropped: int
    total_cards: int
    counts_by_source: dict[str, int]


class IngestionStore:
    """SQLite-backed knowledge store + JSONL snapshot for cards, chunks, and ingestion runs."""

    def __init__(self, db_path: Path, snapshot_path: Path | None = None) -> None:
        self._db_path = db_path
        self._snapshot_path = snapshot_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._init_tables()

    def _init_tables(self) -> None:
        cur = self._conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS cards (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                summary TEXT NOT NULL,
                problem TEXT NOT NULL,
                customer TEXT NOT NULL,
                niche_tags_json TEXT NOT NULL,
                stage TEXT NOT NULL,
                funding_usd INTEGER,
                source TEXT NOT NULL,
                url TEXT NOT NULL,
                canonical_url TEXT UNIQUE NOT NULL,
                fingerprint TEXT UNIQUE NOT NULL,
                published_at TEXT,
                fetched_at TEXT NOT NULL,
                text TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS card_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                url TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                card_id TEXT NOT NULL,
                text TEXT NOT NULL,
                embedding_json TEXT NOT NULL,
                source TEXT NOT NULL,
                url TEXT NOT NULL,
                published_at TEXT
            );
            CREATE TABLE IF NOT EXISTS ingestion_runs (
                run_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                added INTEGER NOT NULL,
                dropped INTEGER NOT NULL,
                ts TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def ingest_items(self, items: list[RawScoutItem], run_source: str = "all") -> IngestionStats:
        """Dedupe by canonical URL and text fingerprint, chunk, embed, and save snapshot."""
        run_id = f"ing_{uuid.uuid4().hex[:10]}"
        cur = self._conn.cursor()
        existing_urls = {
            row[0] for row in cur.execute("SELECT canonical_url FROM cards").fetchall()
        }
        existing_fps = {
            row[0] for row in cur.execute("SELECT fingerprint FROM cards").fetchall()
        }

        added = 0
        dropped = 0
        for item in items:
            card = normalize_item(item)
            c_url = canonical_url(card.url)
            fp = text_fingerprint(card.text)
            if c_url in existing_urls or fp in existing_fps:
                dropped += 1
                continue

            existing_urls.add(c_url)
            existing_fps.add(fp)
            cur.execute(
                """
                INSERT INTO cards (
                    id, name, summary, problem, customer, niche_tags_json, stage,
                    funding_usd, source, url, canonical_url, fingerprint,
                    published_at, fetched_at, text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    card.id,
                    card.name,
                    card.summary,
                    card.problem,
                    card.customer,
                    json.dumps(card.niche_tags),
                    card.stage,
                    card.funding_usd,
                    card.source,
                    card.url,
                    c_url,
                    fp,
                    str(card.published_at) if card.published_at else None,
                    str(card.fetched_at),
                    card.text,
                ),
            )
            cur.execute(
                "INSERT INTO card_sources (card_id, platform, url, fetched_at) VALUES (?, ?, ?, ?)",
                (card.id, card.source, card.url, str(card.fetched_at)),
            )
            for chunk in chunk_card(card):
                emb = hash_embed(chunk["text"])
                cur.execute(
                    """
                    INSERT OR IGNORE INTO chunks (
                        chunk_id, card_id, text, embedding_json, source, url, published_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk["chunk_id"],
                        chunk["card_id"],
                        chunk["text"],
                        json.dumps(emb),
                        chunk["source"],
                        chunk["url"],
                        str(card.published_at) if card.published_at else None,
                    ),
                )
            added += 1

        cur.execute(
            "INSERT INTO ingestion_runs (run_id, source, added, dropped, ts) "
            "VALUES (?, ?, ?, ?, ?)",
            (run_id, run_source, added, dropped, datetime.now(UTC).isoformat()),
        )
        self._conn.commit()

        if self._snapshot_path is not None:
            self.export_snapshot(self._snapshot_path)

        counts = self.counts_by_source()
        return IngestionStats(
            run_id=run_id,
            added=added,
            dropped=dropped,
            total_cards=sum(counts.values()),
            counts_by_source=counts,
        )

    def counts_by_source(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT source, COUNT(*) FROM cards GROUP BY source ORDER BY source"
        ).fetchall()
        return {str(r[0]): int(r[1]) for r in rows}

    def export_snapshot(self, snapshot_path: Path) -> int:
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        rows = self._conn.execute(
            """
            SELECT id, name, summary, problem, customer, niche_tags_json, stage,
                   funding_usd, source, url, published_at, fetched_at, text
            FROM cards ORDER BY id
            """
        ).fetchall()
        with snapshot_path.open("w", encoding="utf-8") as fh:
            for r in rows:
                card = IdeaCard(
                    id=r[0],
                    name=r[1],
                    summary=r[2],
                    problem=r[3],
                    customer=r[4],
                    niche_tags=json.loads(r[5]),
                    stage=r[6],
                    funding_usd=r[7],
                    source=r[8],
                    url=r[9],
                    published_at=r[10],
                    fetched_at=r[11],
                    text=r[12],
                )
                fh.write(card.model_dump_json() + "\n")
        return len(rows)

    def load_snapshot(self, snapshot_path: Path) -> IngestionStats:
        """Reload cards from a local JSONL snapshot without touching external APIs."""
        items: list[RawScoutItem] = []
        with snapshot_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                card = IdeaCard.model_validate_json(line)
                items.append(
                    RawScoutItem(
                        source=card.source,
                        name=card.name,
                        url=card.url,
                        summary=card.summary,
                        problem=card.problem,
                        customer=card.customer,
                        niche_tags=card.niche_tags,
                        stage=card.stage,
                        funding_usd=card.funding_usd,
                        published_at=str(card.published_at) if card.published_at else None,
                        text=card.text,
                    )
                )
        return self.ingest_items(items, run_source="snapshot")
