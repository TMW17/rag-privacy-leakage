"""
build_enron_index.py — index the ~100-email Enron slice IDENTICALLY to the synthetic corpus.

Same embedder (all-MiniLM-L6-v2), same splitter (RecursiveCharacterTextSplitter 512/64 — reused
verbatim from build_index), into a SEPARATE collection 'enron_slice' in the existing chromadb path
(which is gitignored: data/rag_index/chromadb/*). Adds a new INDEPENDENT collection — the frozen
synthetic collections (phase2_baseline_seed42, phase2_poisoned_p3) are untouched. FREE (no API).
Idempotent (drops+rebuilds the enron_slice collection only).
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import chromadb
import scripts.build_index as bi
from scripts.phase3.enron_select import body_of

SEL = os.path.join(ROOT, "results/phase3/enron/selection.json")
COLLECTION = "enron_slice"


def main():
    emails = json.load(open(SEL))["emails"]
    ids, texts, metas = [], [], []
    for i, e in enumerate(emails):
        raw = open(os.path.join(ROOT, e["path"]), encoding="latin-1").read()
        body, _ = body_of(raw)
        chunks = [c for c in (bi._SPLITTER.split_text(body) or [body]) if c.strip()]
        for j, c in enumerate(chunks):
            ids.append(f"enron_{i:03d}_{j:02d}")
            texts.append(c)
            metas.append({"source": e["path"], "user": e["user"]})

    print(f"{len(emails)} emails -> {len(texts)} chunks (splitter {bi.CHUNK_SIZE}/{bi.CHUNK_OVERLAP})")
    embedder = bi.HuggingFaceEmbeddings(model_name=bi.EMBEDDING_MODEL)
    embeddings = embedder.embed_documents(texts)

    client = chromadb.PersistentClient(path=bi.CHROMA_PATH)
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    coll = client.create_collection(name=COLLECTION, metadata={
        "source": "enron_slice", "embedding_model": bi.EMBEDDING_MODEL,
        "chunk_size": bi.CHUNK_SIZE, "chunk_overlap": bi.CHUNK_OVERLAP, "n_emails": len(emails)})
    B = 256
    for s in range(0, len(ids), B):
        e = min(s + B, len(ids))
        coll.add(ids=ids[s:e], embeddings=[list(x) for x in embeddings[s:e]],
                 documents=texts[s:e], metadatas=metas[s:e])

    print(f"collection '{COLLECTION}' built: {coll.count()} chunks in {bi.CHROMA_PATH}")
    print("(chromadb/* is gitignored; frozen synthetic collections untouched)")
    json.dump({"collection": COLLECTION, "n_emails": len(emails), "n_chunks": coll.count(),
               "embedder": bi.EMBEDDING_MODEL, "chunk_size": bi.CHUNK_SIZE, "chunk_overlap": bi.CHUNK_OVERLAP,
               "path": bi.CHROMA_PATH},
              open(os.path.join(ROOT, "results/phase3/enron/index_info.json"), "w"), indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
