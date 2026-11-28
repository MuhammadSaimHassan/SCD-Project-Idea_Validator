"""Retrieval quality gate enforced in CI and locally."""

import json
from pathlib import Path

from eval.retrieval.evaluate import evaluate_modes
from services.kb.src.retriever import HybridKnowledgeBase

ROOT = Path(__file__).resolve().parents[2]


def test_retrieval_quality_gate() -> None:
    eval_corpus = ROOT / "eval" / "retrieval" / "eval_cards.jsonl"
    queries_path = ROOT / "eval" / "retrieval" / "queries.json"
    baseline = json.loads(
        (ROOT / "eval" / "retrieval" / "baseline.json").read_text(encoding="utf-8")
    )

    kb = HybridKnowledgeBase.from_snapshot(eval_corpus)
    assert kb.card_count >= 150
    metrics = evaluate_modes(kb, queries_path, k=5)

    hybrid_recall = metrics["hybrid"]["recall_at_5"]
    hybrid_mrr = metrics["hybrid"]["mrr_at_5"]
    assert hybrid_recall >= float(baseline["min_hybrid_recall_at_5"])
    assert hybrid_mrr >= float(baseline["min_hybrid_mrr_at_5"])
    assert hybrid_recall >= metrics["vector"]["recall_at_5"]
    assert hybrid_recall >= metrics["keyword"]["recall_at_5"]
