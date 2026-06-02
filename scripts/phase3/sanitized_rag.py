"""
sanitized_rag.py — "sanitized retrieval" pipeline mode (Phase 3 index-time defense).

SanitizedRAGSystem is a thin RAGSystem subclass pointed at the SEPARATE sanitized ChromaDB
(data/rag_index/sanitized_chromadb, built by build_sanitized_index.py). It overrides only
__init__ to swap the persistence path + collection; it reuses the FROZEN RAGSystem.query()
verbatim — same embedder (all-MiniLM-L6-v2), same top-k=5, same SUT (Claude Sonnet 4.6),
same system prompt. The only difference vs Phase 2 is the retrieval corpus has sev>=3 PII
already removed at index time.

Pipeline mode:
    rag  = SanitizedRAGSystem(k=5)
    pipe = DefensePipeline(rag, DefenseConfig())   # all query-time layers OFF
The sanitized index is then the ONLY active defense, isolating its contribution.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import anthropic
import chromadb
import chromadb.errors
from sentence_transformers import SentenceTransformer

from scripts.rag_system import RAGSystem, _EMBED_MODEL

SANITIZED_PATH = os.path.join(ROOT, "data", "rag_index", "sanitized_chromadb")
SANITIZED_COLLECTION = "phase3_sanitized_seed42"


class SanitizedRAGSystem(RAGSystem):
    """RAGSystem pointed at the index-time-sanitized ChromaDB (separate path)."""

    def __init__(self, k: int = 5) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set.")
        self._anthropic = anthropic.Anthropic(api_key=api_key)

        self._chroma = chromadb.PersistentClient(path=SANITIZED_PATH)
        try:
            self._collection = self._chroma.get_collection(SANITIZED_COLLECTION)
        except chromadb.errors.NotFoundError:
            raise ValueError(
                f"Collection '{SANITIZED_COLLECTION}' not found in {SANITIZED_PATH}. "
                "Run scripts/phase3/build_sanitized_index.py first."
            )

        self._embedder = SentenceTransformer(_EMBED_MODEL)
        self.collection_name = SANITIZED_COLLECTION
        self.k = k
