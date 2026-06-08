# Baseline Plan — Docs QA RAG (Claude Code run)

Grounded in `.octopus/context/current_context.md`. BASELINE step only:
establish **retrieval quality first**. Do not touch generation/prompts yet.

## Decision
- Baseline retriever: **BM25** over the document corpus.
- Metric: **Recall@k** (primary) + MRR + source-hit rate, on a FIXED labeled query set.
- Retrieval-only: generation is NOT evaluated until retrieval hits the target.

## Steps
1. Build/load a fixed labeled query→relevant-chunk evaluation set. Freeze it.
2. Chunk the corpus once (record chunk size/overlap); index with BM25.
3. Retrieve top-k per query; compute Recall@k, MRR, source-hit rate on the eval set.
4. Inspect failing queries (chunking vs lexical mismatch) — evidence for next step.
5. Every future answer must cite the retrieved source chunk (faithfulness) — set up now.

## Guardrails (from context)
- Evaluate retrieval before generation; one controlled change per experiment.
- Do not tune on the private eval answers / test queries.
- Keep the eval query split fixed.

## Next step (do not skip)
```bash
octopus exp ingest --run-dir runs/baseline_bm25 --kind baseline
octopus exp profile
```
Stop here; do not add dense retrieval / reranker / generation until BM25 recall is logged.
