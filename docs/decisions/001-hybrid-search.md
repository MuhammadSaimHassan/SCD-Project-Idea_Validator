# ADR-001: Use Hybrid Search with Reranking for the Knowledge Base

- **Title:** Use hybrid search with reranking for the knowledge base
- **Status:** Proposed (numbers to be measured on 20 hand-written queries in RAG evaluation stage)
- **Context:** Vector search alone can miss exact product names, technical terms, and niche keywords in student queries; keyword search alone misses paraphrased user pain points.
- **Options:**
  1. Vector search only (embeddings)
  2. Keyword search only (BM25)
  3. Hybrid search (Vector + BM25) with reranking (RRF / cross-encoder)
- **Decision:** Pending empirical recall@5 benchmark on 20 hand-written queries (expected: Hybrid with reranking).
- **Why:** _To be filled after measuring recall@5 across all three options on `eval/retrieval/queries.json`._
- **Cost:** _To be filled with measured per-query latency overhead and container RAM footprint._
- **AI use:** Template and initial options drafted with AI; benchmark queries, measurements, and final selection verified by team members.
