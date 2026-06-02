"""
build_sanitized_index.py — index-time sanitization defense (Phase 3).

Anonymize sev>=3 PII (Presidio worker under .venv-presidio) in each of the 155 docs BEFORE
indexing, then build a SEPARATE ChromaDB at data/rag_index/sanitized_chromadb using the SAME
embedding (all-MiniLM-L6-v2) and chunking (512/64, same separators) as the Phase-2 clean index.

Reuses scripts/build_index.py verbatim for serialization (_TEXT_BUILDERS), the splitter
(_SPLITTER), the embedder (HuggingFaceEmbeddings), and the add schema — only the doc text is
redacted between serialization and chunking. FREE (no SUT). Idempotent (rebuilds the collection).
"""
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from scripts import build_index as bi          # inherits the Py-3.14 spaCy-stub shim
import chromadb
from scripts.phase3.presidio_bridge import redact as presidio_redact

SANITIZED_PATH = os.path.join(ROOT, "data", "rag_index", "sanitized_chromadb")
SANITIZED_COLLECTION = "phase3_sanitized_seed42"
_BATCH = 100


def main():
    docs = bi._load_documents()                # [(doc, doc_class), ...] (155)
    doc_ids = [d["document_id"] for d, _ in docs]
    classes = [c for _, c in docs]
    texts = [bi._TEXT_BUILDERS[c](d) for d, c in docs]   # frozen Phase-2 serialization

    # ── Anonymize sev>=3 PII BEFORE indexing (Presidio subprocess, .venv-presidio) ──
    print(f"Redacting sev>=3 PII in {len(texts)} docs via Presidio worker ...", flush=True)
    res = presidio_redact(texts, sev_threshold=3, timeout=1200)
    redacted = res["redacted"]
    total_redacted = sum(s["n_redacted"] for s in res["stats"])
    print(f"  redacted {total_redacted} sev>=3 spans across {len(redacted)} docs", flush=True)

    # ── Chunk the REDACTED text with the SAME splitter/params ──
    all_ids, all_texts, all_metas = [], [], []
    for did, cls, rtext in zip(doc_ids, classes, redacted):
        chunks = [c for c in (bi._SPLITTER.split_text(rtext) or [rtext]) if c.strip()]
        for i, c in enumerate(chunks):
            all_ids.append(f"{did}::chunk{i}")
            all_texts.append(c)
            all_metas.append({"doc_id": did, "doc_class": cls, "chunk_index": i,
                              "is_poisoned": False, "sanitized": True})
    print(f"  {len(all_ids)} chunks from {len(doc_ids)} sanitized docs", flush=True)

    # ── Embed with the SAME model as build_index ──
    embedder = bi.HuggingFaceEmbeddings(model_name=bi.EMBEDDING_MODEL)
    embeddings = embedder.embed_documents(all_texts)

    # ── (Re)create the separate sanitized collection ──
    client = chromadb.PersistentClient(path=SANITIZED_PATH)
    try:
        client.delete_collection(SANITIZED_COLLECTION)
    except Exception:
        pass
    coll = client.create_collection(name=SANITIZED_COLLECTION, metadata={
        "corpus_size": len(doc_ids), "snapshot": "sanitized",
        "embedding_model": bi.EMBEDDING_MODEL, "chunk_size": bi.CHUNK_SIZE,
        "chunk_overlap": bi.CHUNK_OVERLAP, "sanitizer": "presidio_bin_a_sev>=3",
        "indexed_at": datetime.now(timezone.utc).isoformat()})
    for s in range(0, len(all_ids), _BATCH):
        e = min(s + _BATCH, len(all_ids))
        coll.add(ids=all_ids[s:e], embeddings=[list(x) for x in embeddings[s:e]],
                 documents=all_texts[s:e], metadatas=all_metas[s:e])

    print(f"DONE: sanitized index -> {SANITIZED_PATH} :: {SANITIZED_COLLECTION} "
          f"({coll.count()} chunks, {total_redacted} sev>=3 spans redacted)")


if __name__ == "__main__":
    main()
