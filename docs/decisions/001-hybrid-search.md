# ADR-001: Use Hybrid Search with Reranking for the Knowledge Base

- **Title:** Use hybrid search with reranking for the knowledge base
- **Status:** Accepted
- **Context:** Vector search alone can miss exact product names and lower rank precision on exact identifiers, while keyword search alone misses paraphrased problem queries across our 1,649-card corpus (3,540 chunks).
- **Options:**
  1. Vector search only (dense n-gram + token cosine similarity)
  2. Keyword search only (Okapi BM25)
  3. Hybrid search (Vector + BM25 via RRF) with exact-match & token-coverage reranking
- **Decision:** Hybrid search (Vector + BM25 via RRF) with reranking.
- **Why:** Evaluated across 22 hand-written queries (`eval/retrieval/queries.json`) on the 1,649-card snapshot (`data/snapshot/cards.jsonl`): vector-only achieved `Recall@5 = 1.0000` and `MRR@5 = 0.9545` (182.55 ms/query), BM25 keyword achieved `Recall@5 = 1.0000` and `MRR@5 = 1.0000` (192.72 ms/query), and hybrid+rerank achieved **`Recall@5 = 1.0000` and `MRR@5 = 1.0000` (174.07 ms/query)** while preserving robustness on both semantic and exact-name lookups.
- **Cost:** Requires maintaining both the dense vector index and BM25 inverted index in M6 (~174 ms average query latency over 3,540 chunks in Python).
- **AI use:** Retrieval module and evaluation script drafted with AI; query set (`queries.json`), benchmark run, and ADR numbers verified by us.
