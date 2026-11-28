"""Measure Recall@5 and MRR@5 for vector, BM25 keyword, and hybrid+rerank search."""

import argparse
import json
import time
from pathlib import Path

from services.kb.src.retriever import HybridKnowledgeBase
from shared.schemas import SearchRequest


def evaluate_modes(
    kb: HybridKnowledgeBase,
    queries_path: Path,
    k: int = 5,
) -> dict[str, dict[str, float]]:
    queries = json.loads(queries_path.read_text(encoding="utf-8"))
    results: dict[str, dict[str, float]] = {}

    for mode in ("vector", "keyword", "hybrid"):
        hits = 0
        mrr_sum = 0.0
        t0 = time.perf_counter()
        for q in queries:
            resp = kb.search(SearchRequest(query=q["query"], top_k=k), mode=mode)
            returned_ids = [item.card_id for item in resp.items]
            expected = set(q["expected_card_ids"])
            if expected.intersection(returned_ids):
                hits += 1
            for rank, cid in enumerate(returned_ids, start=1):
                if cid in expected:
                    mrr_sum += 1.0 / rank
                    break
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        n = max(1, len(queries))
        results[mode] = {
            f"recall_at_{k}": round(hits / n, 4),
            f"mrr_at_{k}": round(mrr_sum / n, 4),
            "avg_latency_ms": round(elapsed_ms / n, 2),
            "queries": float(len(queries)),
        }
    return results


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate M6 retrieval modes on hand-written queries"
    )
    parser.add_argument(
        "--corpus",
        default="data/snapshot/cards.jsonl",
        help="Path to JSONL IdeaCard corpus",
    )
    parser.add_argument(
        "--queries",
        default="eval/retrieval/queries.json",
        help="Path to queries.json",
    )
    args = parser.parse_args(argv)

    corpus = Path(args.corpus)
    if not corpus.exists():
        corpus = Path("eval/retrieval/eval_cards.jsonl")
    kb = HybridKnowledgeBase.from_snapshot(corpus)
    metrics = evaluate_modes(kb, Path(args.queries), k=5)

    print(f"Corpus: {corpus} ({kb.card_count} cards, {kb.chunk_count} chunks)")
    print(f"{'Mode':<12} {'Recall@5':>10} {'MRR@5':>10} {'Latency(ms)':>13}")
    print("-" * 48)
    for mode in ("vector", "keyword", "hybrid"):
        m = metrics[mode]
        print(
            f"{mode:<12} {m['recall_at_5']:>10.4f} {m['mrr_at_5']:>10.4f} "
            f"{m['avg_latency_ms']:>13.2f}"
        )


if __name__ == "__main__":
    main()
