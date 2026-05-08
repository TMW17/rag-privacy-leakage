# CLAUDE.md

## Operational Guide for AI Coding Agents

> **What this file is.** Contracts, invariants, and conventions for any AI coding agent working on this codebase. For the scientific background and motivation, read `PROJECT.md`. For the active-phase plan, read `Phase2.md`.

---

## 1. Project in one paragraph

Master's thesis at ESI Sidi Bel Abbès (AI & Data Science, 2025–2026). Author: TADJ Mohamed Walid.
Goal: measure and mitigate privacy leakage in enterprise RAG systems using two formal metrics — binary leakage function **L** (did any unauthorized entity leak?) and severity score **S** (how bad?) — applied across four attacker profiles against a 155-document synthetic PII corpus.

---

## 2. Directory layout

```
Code/
├── CLAUDE.md                  ← this file
├── PROJECT.md                 ← full thesis explanation (source of truth for science)
├── Phase1.md                  ← state-of-art literature review (Phase 1 complete)
├── Phase2.md                  ← active roadmap (Phase 2 in progress)
├── Makefile                   ← Phase 1 pipeline runner (see §6)
├── requirements.txt           ← all Python dependencies
│
├── scripts/                   ← Phase 1 pipeline (frozen artifacts — do not modify)
│   ├── config.py              ← ALL paths and constants (single source of truth)
│   ├── generate_dataset.py    ← Step 1: generate 155-doc corpus
│   ├── annotate_dataset.py    ← Step 2: annotate 2,280 PII entities
│   ├── evaluation_engine.py   ← Core metric library: L, S, AttackerProfile
│   ├── reidentification_risk.py   ← k-anonymity / l-diversity analysis
│   ├── kappa_validation.py    ← inter-annotator agreement (Cohen's κ)
│   └── validate_ground_truth.py   ← pre-flight consistency gate (exits 0 or 1)
│
├── experiments/               ← Phase 2 RAG system (to be built in week 3)
│   └── (rag_system.py will go here — see Phase2.md §4)
│
├── scenarios/                 ← Phase 2 adversarial scenario registry (week 1–2)
│   └── (v0_skeletons.json, v1_queries.json — see Phase2.md §3)
│
├── data/
│   ├── ground_truth/          ← FROZEN Phase 1 outputs (never regenerate without reason)
│   │   ├── ground_truth.json              155 documents, 4 classes
│   │   ├── ground_truth_index.json        flat doc_id → document lookup
│   │   └── ground_truth_annotations.json  2,280 entity-level PII annotations
│   ├── rag_index/
│   │   └── chromadb/          ← Phase 2 ChromaDB vector store (built at week 3 start)
│   └── synthetic/             ← reserved for future datasets
│
├── results/                   ← analysis outputs
│   ├── reidentification_risk.json
│   ├── kappa_results.json
│   ├── baseline_summary.csv   ← Phase 2 output (50 sc. × 3 runs)
│   └── baseline_metrics.json  ← Phase 2 output (ASR, S̄ per profile/family)
│
└── experiment_logs/           ← JSONL per-query logs from Phase 2+ runs
```

---

## 3. The four attacker profiles

These are the **single source of truth**. Every script, enum, and config that references profiles must use exactly these names and thresholds.

| Profile | Enum value     | CVSS | Auth threshold | What leaks                      |
| ------- | -------------- | ---- | -------------- | ------------------------------- |
| P1      | `"Internal"`   | 6.5  | 2              | severity ≥ 3 from corpus        |
| P2      | `"External"`   | 8.2  | 0              | any corpus disclosure           |
| P3      | `"Admin"`      | 9.1  | 3              | severity ≥ 4 via chat interface |
| P4      | `"ThirdParty"` | 7.7  | 3              | aggregate/cross-tenant sev. ≥ 4 |

Defined in `scripts/config.py:AUTHORIZATION_LEVELS` and `scripts/evaluation_engine.py:AttackerProfile`.

---

## 4. The two formal definitions

```
L(q, r, D, u) = 1   if ∃ entity e in response r where severity(e) > authorized_level(u)
              = 0   otherwise

S(q, r, D, u) = Σ s(e) · w(e)   for all leaked entities e
```

- `s(e)` ∈ {2, 3, 4, 5} — entity severity from the 37-type taxonomy (PROJECT.md §6)
- `w(e)` ∈ {0.60, 0.75, 0.90, 1.00} — detection-method confidence weight

Detection-method → confidence-weight mapping (invariant — do not change without updating annotations):

| Method          | w(e) |
| --------------- | ---- |
| Regex           | 1.00 |
| NER             | 0.90 |
| Keyword+Context | 0.75 |
| LLM-as-Judge    | 0.60 |

---

## 5. Phase 1 pipeline — what exists and is frozen

Run with `make` from the project root. All outputs in `data/ground_truth/` and `results/` are **frozen** — do not delete or regenerate unless explicitly told to rebuild.

```bash
make                  # run full Phase 1 pipeline (skips up-to-date steps)
make validate         # pre-flight consistency gate — must exit 0 before Phase 2 work
make clean && make    # force full rebuild from scratch
```

**Script contracts (Phase 1 scripts — do not modify logic without updating annotations):**

| Script                     | Reads                           | Writes                                         | Notes                       |
| -------------------------- | ------------------------------- | ---------------------------------------------- | --------------------------- |
| `generate_dataset.py`      | nothing                         | `ground_truth.json`, `ground_truth_index.json` | seed=42, deterministic      |
| `annotate_dataset.py`      | `ground_truth.json`             | `ground_truth_annotations.json`                | 2,280 entities, 37 types    |
| `reidentification_risk.py` | `ground_truth.json`             | `results/reidentification_risk.json`           | k-anon / l-diversity        |
| `kappa_validation.py`      | nothing (built-in test set)     | `results/kappa_results.json`                   | κ=0.875, κ_w=0.968          |
| `validate_ground_truth.py` | both ground truth files         | exits 0 or 1                                   | **gate before Phase 2**     |
| `evaluation_engine.py`     | `ground_truth_annotations.json` | (module API)                                   | import, do not run directly |

---

## 6. Phase 2 tech stack (to be built — see Phase2.md)

| Layer                   | Component                                | Notes                                                |
| ----------------------- | ---------------------------------------- | ---------------------------------------------------- |
| Orchestration           | LangChain 0.3.x                          | `ChatPromptTemplate`, `ConversationBufferMemory`     |
| Vector store            | ChromaDB 0.5.x                           | persistent at `data/rag_index/chromadb/`             |
| Embeddings              | `sentence-transformers all-MiniLM-L6-v2` | local, free, 384-dim                                 |
| LLM (system under test) | Claude Sonnet 4.6 (`claude-sonnet-4-6`)  | `ANTHROPIC_API_KEY`, `temperature=0`                 |
| LLM (judge)             | Claude Opus 4.7 (`claude-opus-4-7`)      | judge prompt at `scripts/judge_prompts/judge_v3.txt` |
| Logging                 | `loguru`                                 | JSONL to `experiment_logs/`                          |

**The RAG system (`experiments/rag_system.py`) does not exist yet.** It will be built in Phase 2 week 3. The corpus indexing procedure is in Phase2.md §4.4.

---

## 7. Key invariants — never violate these

1. **Corpus seed is 42.** `random.seed(42)` and `Faker.seed(42)` are set in `generate_dataset.py`. Any run with a different seed produces a different corpus and invalidates all annotations.

2. **Authorization thresholds are in `config.py` only.** The dict `AUTHORIZATION_LEVELS` in `scripts/config.py` is the single source of truth. `evaluation_engine.py` imports it. Never hardcode a threshold elsewhere.

3. **Phase 1 artifacts are frozen.** `ground_truth.json`, `ground_truth_index.json`, `ground_truth_annotations.json` — do not modify these manually. Only `generate_dataset.py` / `annotate_dataset.py` may write them, and only when `make clean && make` is intentionally run.

4. **Profile parameter is always explicit.** The evaluation engine never infers the attacker profile from the query. It is always passed as an explicit `AttackerProfile` enum value.

5. **ChromaDB corpus is read-only during Phase 2.** Profile 3 corpus-poisoning scenarios use a separate poisoned snapshot collection, not the clean baseline collection.

6. **Detection-method weights match annotations.** The `confidence_weight` field in every annotation record must equal the `w(e)` in the table above for its `detection_method`. `validate_ground_truth.py` check #4 enforces this.

---

## 8. Import pattern

All scripts resolve paths through `scripts/config.py`. Always do:

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.config import GROUND_TRUTH_FILE, ANNOTATIONS_FILE, AUTHORIZATION_LEVELS
from scripts.evaluation_engine import check_response_for_leakage, AttackerProfile
```

Never hardcode file paths. Never import `config.py` with a relative path.

---

## 9. Ground-truth corpus structure

`ground_truth.json` top-level keys:

```python
{
  "metadata":        { "version": "2.0", "seed": 42, "total_documents": 155, ... },
  "employee_records": [...],   # 100 documents
  "system_configs":   [...],   #   5 documents
  "internal_memos":   [...],   #  20 documents
  "medical_reports":  [...],   #  30 documents
}
```

Each document has a `"document_id"` field (e.g. `"hr_file_001"`, `"sys_config_001"`).
`ground_truth_index.json` is a flat `{ doc_id → document_dict }` for O(1) lookup.

When iterating over all documents (e.g. for ChromaDB indexing), flatten all four lists:

```python
all_docs = (corpus["employee_records"] + corpus["system_configs"]
            + corpus["internal_memos"] + corpus["medical_reports"])
```

---

## 10. Phase status

| Phase                      | Status          | Output                                                   |
| -------------------------- | --------------- | -------------------------------------------------------- |
| Phase 1 — Corpus & metrics | **Complete**    | 155 docs, 2,280 annotations, κ=0.875                     |
| Phase 2 — Attack framework | **In progress** | Scenarios (wk 1–2), RAG system (wk 3), campaign (wk 3–5) |
| Phase 3 — Defense ablation | Not started     | Presidio, NeMo Guardrails, output filter, retrieval ACL  |
| Phase 4 — Reporting        | Not started     | Thesis + Best Practices Guide                            |
