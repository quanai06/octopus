"""BM25 retrieval baseline for Docs QA RAG.

Claude Code baseline deliverable (eval). Retrieval-only: no generation here.
Encodes the decisions from .octopus/context/current_context.md. Not executed.
"""

from __future__ import annotations

from pathlib import Path

CORPUS_DIR = Path("data/corpus")
EVAL_QUERIES = Path("data/eval/queries.jsonl")  # FIXED labeled query set
K_VALUES = (1, 3, 5, 10)
CHUNK_SIZE, CHUNK_OVERLAP = 512, 64  # recorded; one controlled change at a time


def chunk_corpus():
    """Chunk documents once with fixed size/overlap; return chunks with source ids."""
    # TODO: read CORPUS_DIR; return [(chunk_id, source_doc, text), ...]
    raise NotImplementedError


def build_bm25(chunks):
    # TODO: tokenize chunk texts and build a BM25 index (e.g., rank_bm25).
    raise NotImplementedError


def load_eval_queries():
    """Fixed query -> relevant chunk/source ids. Never tune on these answers."""
    # TODO: read EVAL_QUERIES (jsonl): {"query": ..., "relevant_ids": [...]}
    raise NotImplementedError


def evaluate_retrieval(index, queries) -> dict:
    """Recall@k, MRR, and source-hit rate on the fixed eval set (retrieval only)."""
    # TODO: for each query, retrieve top-max(K); compute Recall@k / MRR / source-hit.
    # Each returned hit must carry its source id so answers can cite it later.
    raise NotImplementedError


def main() -> None:
    chunks = chunk_corpus()
    index = build_bm25(chunks)
    queries = load_eval_queries()
    metrics = evaluate_retrieval(index, queries)
    print({"recall_at_k": metrics, "note": "generation NOT evaluated at baseline"})


if __name__ == "__main__":
    main()
