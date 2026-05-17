"""
build_index.py
==============
Indexes the 155-document Phase 1 corpus into ChromaDB collection
"phase2_baseline_seed42".

Run once before any Phase 2 campaign script.  Idempotent: a second run
detects the existing collection and exits 0 without re-indexing.

Usage
-----
    python scripts/build_index.py

First run  : 1–3 min  (sentence-transformers model download + 155-doc embed)
Second run : < 1 s    (collection found, skip)

Architecture
------------
  ground_truth.json  →  text builders  →  RecursiveCharacterTextSplitter(512/64)
    →  HuggingFaceEmbeddings(all-MiniLM-L6-v2, 384-dim)
    →  ChromaDB "phase2_baseline_seed42" (PersistentClient)

The public function chunk_document() is imported by build_poisoned_index.py
so the poisoned collection uses identical chunking parameters.

Author: TADJ Mohamed Walid
"""

import json
import os
import statistics
import sys
import time
import types
import warnings
from datetime import datetime, timezone
from typing import Dict, List, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# Spacy shim — must precede any langchain_text_splitters import.
#
# On Python 3.14, spacy's Cython extensions fail to compile; importing
# langchain_text_splitters cascades into spacy/__init__.py and crashes.
# Injecting a stub module prevents the chain reaction.
# Remove once spacy releases Python 3.14-compatible wheels.
# ─────────────────────────────────────────────────────────────────────────────
if "spacy" not in sys.modules:
    sys.modules["spacy"] = types.ModuleType("spacy")

warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

import chromadb
import chromadb.errors
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

# =============================================================================
# Constants
# =============================================================================

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GROUND_TRUTH_PATH = os.path.join(ROOT, "data", "ground_truth", "ground_truth.json")
CHROMA_PATH       = os.path.join(ROOT, "data", "rag_index", "chromadb")

COLLECTION_NAME = "phase2_baseline_seed42"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CHUNK_SIZE      = 512
CHUNK_OVERLAP   = 64
SEPARATORS      = ["\n\n", "\n", ". ", " ", ""]
CORPUS_SIZE     = 155
_BATCH_SIZE     = 100   # ChromaDB insertion batch size

# ground_truth.json list key  →  doc_class string
_DOC_CLASS_MAP: Dict[str, str] = {
    "employee_records": "employee_record",
    "system_configs":   "system_config",
    "internal_memos":   "internal_memo",
    "medical_reports":  "medical_report",
}

# Module-level splitter instance (shared by chunk_document and main)
_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=SEPARATORS,
)


# =============================================================================
# Document-class text builders (private)
# =============================================================================

def _employee_text(doc: dict) -> str:
    """
    "EMPLOYEE RECORD\\nField: Value\\n..." for every annotated field.
    Field order follows the Phase 1 annotation taxonomy (36 entity types).
    document_id is included so similarity search can surface docs by ID.
    """
    lines = [
        "EMPLOYEE RECORD",
        f"Document ID: {doc.get('document_id', '')}",
    ]
    field_labels = [
        ("national_id",       "National ID"),
        ("name",              "Name"),
        ("email",             "Email"),
        ("phone",             "Phone"),
        ("address",           "Address"),
        ("date_of_birth",     "Date of Birth"),
        ("iban",              "IBAN"),
        ("health_record_id",  "Health Record ID"),
        ("surname_job_title", "Surname / Title"),
        ("salary",            "Salary"),
        ("medical_condition", "Medical Condition"),
        ("employee_id",       "Employee ID"),
        ("immigration_status","Immigration Status"),
        ("performance",       "Performance"),
        ("gender",            "Gender"),
        ("age",               "Age"),
        ("department",        "Department"),
        ("job_title",         "Job Title"),
        ("office_location",   "Office Location"),
        ("work_schedule",     "Work Schedule"),
        ("project_assignment","Project Assignment"),
        ("training_status",   "Training Status"),
    ]
    for field, label in field_labels:
        val = doc.get(field)
        if val is not None and str(val).strip().lower() not in ("", "none", "n/a"):
            lines.append(f"{label}: {val}")
    return "\n".join(lines)


def _config_text(doc: dict) -> str:
    """
    "CONFIG\\nKey: Value\\n..." for all system-configuration fields.
    Includes credentials and keys — these are the sev-5 entities targeted
    by P3-POISON-006 (system credential exfiltration via corpus poisoning).
    """
    lines = [
        "CONFIG",
        f"Document ID: {doc.get('document_id', '')}",
    ]
    field_labels = [
        ("api_key_openai",       "API Key (OpenAI)"),
        ("api_key_anthropic",    "API Key (Anthropic)"),
        ("jwt_token",            "JWT Token"),
        ("password_hash",        "Password Hash"),
        ("db_connection_string", "DB Connection"),
        ("system_prompt",        "System Prompt"),
        ("private_key_snippet",  "Private Key"),
        ("internal_ip",          "Internal IP"),
        ("internal_file_paths",  "Internal File Paths"),
        ("architecture_details", "Architecture"),
    ]
    for field, label in field_labels:
        val = doc.get(field)
        if val is None:
            continue
        if isinstance(val, list):
            val = ", ".join(str(v) for v in val)
        if str(val).strip():
            lines.append(f"{label}: {val}")
    return "\n".join(lines)


def _memo_text(doc: dict) -> str:
    """
    Memo body used directly to preserve semantic content for retrieval.
    Title, date, author, and classification frame the body; employee refs
    are appended so cross-reference queries surface the right documents.
    """
    parts = []
    if doc.get("title"):
        parts.append(doc["title"])
    meta_lines = []
    if doc.get("date"):
        meta_lines.append(f"Date: {doc['date']}")
    if doc.get("author"):
        meta_lines.append(f"Author: {doc['author']}")
    if meta_lines:
        parts.append("\n".join(meta_lines))
    if doc.get("body"):
        parts.append(doc["body"])
    if doc.get("employees_referenced"):
        parts.append(
            "Employees Referenced: " + ", ".join(doc["employees_referenced"])
        )
    if doc.get("classification"):
        parts.append(f"Classification: {doc['classification']}")
    return "\n\n".join(parts)


def _medical_text(doc: dict) -> str:
    """
    "MEDICAL REPORT\\nField: Value\\n..." with employee_ref cross-reference
    so that medical queries can link back to the HR employee record.
    """
    lines = [
        "MEDICAL REPORT",
        f"Document ID: {doc.get('document_id', '')}",
    ]
    field_labels = [
        ("patient_name",       "Patient"),
        ("patient_id",         "Patient ID"),
        ("employee_ref",       "Employee Ref"),
        ("diagnosis",          "Diagnosis"),
        ("treating_physician", "Physician"),
        ("date_of_visit",      "Date"),
        ("prescription",       "Prescription"),
        ("follow_up",          "Follow-up"),
        ("work_restriction",   "Work Restriction"),
    ]
    for field, label in field_labels:
        val = doc.get(field)
        if val is not None and str(val).strip().lower() not in ("", "none", "n/a"):
            lines.append(f"{label}: {val}")
    return "\n".join(lines)


_TEXT_BUILDERS: Dict[str, object] = {
    "employee_record": _employee_text,
    "system_config":   _config_text,
    "internal_memo":   _memo_text,
    "medical_report":  _medical_text,
}


# =============================================================================
# Public chunking function
# Imported by build_poisoned_index.py — do not rename or change signature.
# =============================================================================

def chunk_document(doc: dict, doc_class: str) -> List[str]:
    """
    Build indexable text for one document and split into chunks.

    Parameters
    ----------
    doc : dict
        One document dict from ground_truth.json.
    doc_class : str
        One of ``"employee_record"``, ``"system_config"``,
        ``"internal_memo"``, ``"medical_report"``.

    Returns
    -------
    list[str]
        Non-empty chunk strings ready for ChromaDB insertion.
        Always returns at least one element for non-empty documents.
    """
    builder = _TEXT_BUILDERS.get(doc_class)
    if builder is None:
        raise ValueError(f"Unknown doc_class: {doc_class!r}")
    text = builder(doc)  # type: ignore[operator]
    chunks = _SPLITTER.split_text(text)
    if not chunks and text.strip():
        chunks = [text]             # entire short document fits in one chunk
    return [c for c in chunks if c.strip()]


# =============================================================================
# Internal helpers
# =============================================================================

def _load_documents() -> List[Tuple[dict, str]]:
    """
    Flatten ground_truth.json into ``(doc, doc_class)`` pairs.
    Skips the "metadata" key by testing ``isinstance(value, list)``.
    """
    with open(GROUND_TRUTH_PATH, encoding="utf-8") as fh:
        corpus = json.load(fh)

    pairs: List[Tuple[dict, str]] = []
    for key, value in corpus.items():
        if not isinstance(value, list):
            continue                        # skip "metadata" dict
        doc_class = _DOC_CLASS_MAP.get(key)
        if doc_class is None:
            continue
        for doc in value:
            pairs.append((doc, doc_class))
    return pairs


def _idempotency_status(meta: dict) -> str:
    """
    Compare collection metadata against expected values.
    Returns ``"match"`` or a human-readable mismatch description.
    """
    expected = {
        "corpus_size":     CORPUS_SIZE,
        "snapshot":        "clean",
        "embedding_model": EMBEDDING_MODEL,
        "chunk_size":      CHUNK_SIZE,
        "chunk_overlap":   CHUNK_OVERLAP,
    }
    for key, exp in expected.items():
        actual = meta.get(key)
        if actual != exp:
            return f"key={key!r} expected={exp!r} got={actual!r}"
    return "match"


# =============================================================================
# Main
# =============================================================================

def main() -> int:
    t0 = time.perf_counter()

    # ── 1. Idempotency check ──────────────────────────────────────────────────
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    try:
        existing = client.get_collection(COLLECTION_NAME)
        status = _idempotency_status(existing.metadata or {})
        if status == "match":
            print(
                f"Collection '{COLLECTION_NAME}' already indexed "
                f"({existing.count()} chunks). Skipping."
            )
            return 0
        print(
            f"ERROR: Collection '{COLLECTION_NAME}' exists but metadata "
            f"does not match:\n  {status}\n"
            f"To rebuild, drop the collection first:\n"
            f"  python -c \"import chromadb; "
            f"chromadb.PersistentClient(path='{CHROMA_PATH}')"
            f".delete_collection('{COLLECTION_NAME}')\"",
            file=sys.stderr,
        )
        return 1
    except chromadb.errors.NotFoundError:
        pass    # first run — fall through to build

    # ── 2. Load documents ─────────────────────────────────────────────────────
    print("Loading ground_truth.json ...")
    docs_and_classes = _load_documents()
    n_docs = len(docs_and_classes)
    print(f"  {n_docs} documents loaded.")
    if n_docs != CORPUS_SIZE:
        print(
            f"WARNING: expected {CORPUS_SIZE} documents, got {n_docs}.",
            file=sys.stderr,
        )

    # ── 3. Chunk ──────────────────────────────────────────────────────────────
    print("Chunking documents ...")
    all_ids:    List[str]  = []
    all_texts:  List[str]  = []
    all_metas:  List[dict] = []
    per_doc_n:  List[int]  = []
    class_totals: Dict[str, int] = {c: 0 for c in _DOC_CLASS_MAP.values()}

    for doc, doc_class in docs_and_classes:
        doc_id = doc["document_id"]
        chunks = chunk_document(doc, doc_class)
        n = len(chunks)
        per_doc_n.append(n)
        class_totals[doc_class] += n
        for i, chunk in enumerate(chunks):
            all_ids.append(f"{doc_id}::chunk{i}")
            all_texts.append(chunk)
            all_metas.append({
                "doc_id":      doc_id,
                "doc_class":   doc_class,
                "chunk_index": i,
                "is_poisoned": False,
            })

    total_chunks = len(all_ids)
    print(f"  {total_chunks} chunks from {n_docs} documents.")

    # ── 4. Embed ──────────────────────────────────────────────────────────────
    print(
        f"Loading '{EMBEDDING_MODEL}' embedding model "
        "(downloads ~90 MB on first use) ..."
    )
    embedder = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    print(f"Embedding {total_chunks} chunks ...")
    embeddings = embedder.embed_documents(all_texts)
    print(f"  Done. Dimension = {len(embeddings[0])}.")

    # ── 5. Create collection ──────────────────────────────────────────────────
    collection_meta = {
        "corpus_size":     CORPUS_SIZE,
        "snapshot":        "clean",
        "embedding_model": EMBEDDING_MODEL,
        "chunk_size":      CHUNK_SIZE,
        "chunk_overlap":   CHUNK_OVERLAP,
        "indexed_at":      datetime.now(timezone.utc).isoformat(),
    }
    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata=collection_meta,
    )
    print(f"Created collection '{COLLECTION_NAME}'.")

    # ── 6. Insert in batches ──────────────────────────────────────────────────
    print(f"Inserting {total_chunks} chunks (batch size {_BATCH_SIZE}) ...")
    for start in range(0, total_chunks, _BATCH_SIZE):
        end = min(start + _BATCH_SIZE, total_chunks)
        collection.add(
            ids=all_ids[start:end],
            embeddings=[list(e) for e in embeddings[start:end]],
            documents=all_texts[start:end],
            metadatas=all_metas[start:end],
        )
    print(f"  Inserted all {total_chunks} chunks.")

    # ── 7. Verify stored count ────────────────────────────────────────────────
    stored = collection.count()
    if stored != total_chunks:
        print(
            f"WARNING: ChromaDB reports {stored} stored chunks "
            f"but {total_chunks} were submitted.",
            file=sys.stderr,
        )

    # ── 8. Summary statistics ─────────────────────────────────────────────────
    elapsed = time.perf_counter() - t0

    print()
    print("=" * 62)
    print("INDEX BUILD COMPLETE")
    print("=" * 62)
    print(f"Total documents     : {n_docs}")
    print(f"Total chunks        : {total_chunks}")
    print(f"Mean chunks / doc   : {statistics.mean(per_doc_n):.2f}")
    print(f"Median chunks / doc : {statistics.median(per_doc_n):.1f}")
    print(f"Max chunks / doc    : {max(per_doc_n)}")
    print()
    print("Chunks per document class:")
    for cls, count in class_totals.items():
        print(f"  {cls:<20}  {count:>5} chunks")
    print()
    print(f"Collection          : {COLLECTION_NAME}")
    print(f"ChromaDB path       : {CHROMA_PATH}")
    print(f"Wall-clock time     : {elapsed:.1f}s")
    print("=" * 62)

    return 0


if __name__ == "__main__":
    sys.exit(main())
