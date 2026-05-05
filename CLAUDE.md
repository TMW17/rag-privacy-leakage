# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Authority

`PROJECT.md` at the repo root is the single source of truth. Read it before doing anything non-trivial. If code disagrees with `PROJECT.md`, the code is what needs fixing — not the doc. README.md describes layout only; PROJECT.md describes intent, contracts, and invariants.

This is a six-month MSc thesis at ESI Sidi Bel Abbès on **privacy leakage in enterprise RAG systems**. Phase 1 (this codebase) builds the measurement foundation — synthetic corpus, entity-level ground truth, k-anonymity/l-diversity analysis, inter-annotator agreement. Phases 2–4 (attacks, defenses, residual-risk analysis) live in `experiments/` and are not built yet.

## Pipeline (run in order from repo root)

```bash
source /Users/user/Desktop/PFE/rag_env/bin/activate

python scripts/generate_dataset.py        # 1. corpus → data/ground_truth/ground_truth*.json
python scripts/annotate_dataset.py        # 2. annotations → ground_truth_annotations.json
python scripts/reidentification_risk.py   # 3. k-anon + l-div → results/reidentification_risk.json
python scripts/validate_ground_truth.py   # 4. pre-flight gate, must exit 0
python scripts/kappa_validation.py        # 5. κ → results/kappa_results.json (independent of corpus)
```

`make all` runs steps 1–3 + 5 with output-dependency tracking. `make validate` runs step 4. `make clean` wipes all generated artifacts.

`evaluation_engine.py` is a library (imported by the other scripts and Phase 2/3/4 code); only run it directly for its `__main__` self-test.

### CLI flags worth knowing

`generate_dataset.py` exposes `--seed`, `--n-employees`, `--n-configs`, `--n-memos`, `--n-medicals`. Defaults reproduce the canonical n=1000 corpus (645/32/129/194). Pass distinct seeds for Monte Carlo runs.

## Architecture in one screen

The whole codebase exists to compute two formal functions defined in `PROJECT.md` §4:

- **L(q, r, D, u)** — binary leakage. Did *any* entity in the response exceed the user's authorization threshold?
- **S(q, r, D, u)** — continuous severity score. Sum of `severity × confidence_weight` across leaked entities.

Both are implemented in `scripts/evaluation_engine.py`. Every other script either *prepares input* (corpus, annotations) or *produces evidence* the metrics need (k-anon for Linkability, kappa for taxonomy reproducibility).

### Data flow

```
generate_dataset.py ──► ground_truth.json ──► annotate_dataset.py ──► ground_truth_annotations.json
                                          ╲                                        │
                                           ╲                                       ▼
                                            ► reidentification_risk.py     evaluation_engine.py
                                                                          (used by Phase 2+ experiments)
```

`validate_ground_truth.py` reads both ground truth files and runs six consistency checks (document coverage, severity coverage, LINDDUN coverage, confidence-weight consistency, entity volume, cross-references). It must exit 0 before any Phase 2 work.

`kappa_validation.py` is decoupled — its 20 test responses are inline. Corpus changes do not affect κ.

### The taxonomy

37 entity types in `ENTITY_SPECS` inside `annotate_dataset.py`. Each entity carries 6 properties: `(type, category, severity, detection_method, confidence_weight, linddun_category)`. This dict is the runtime encoding of **Table 6.1 in `docs/Threat_Model_Document.pdf`** and must stay byte-for-byte aligned with it. Five entity types are intentionally never instantiated (CREDIT_CARD, PASSPORT_ID, MEMBERSHIP, QUASI_IDENTIFIER, PARTIAL_ADDRESS) — see PROJECT.md §11.2.

## Hard invariants

These are inter-script contracts. Breaking one without fixing the consequence breaks everything downstream.

1. **`AUTHORIZATION_LEVELS = {Internal: 2, External: 0, Admin: 3}`** — defined once in `scripts/config.py`, imported by `annotate_dataset.py` and `evaluation_engine.py`. Admin = 3, not 0; matches the thesis exactly.
2. **Seeding** — `random.seed(seed)` AND `Faker.seed(seed)` are both called at the start of `generate_corpus()` in `scripts/generate_dataset.py`. Both are required (Faker has its own PRNG). Default `CORPUS_SEED = 42`.
3. **Document/entity counts are exact, not approximate.** Canonical figures: 1000 documents (645/32/129/194), ~14,935 entities, 32/37 entity types used, κ=0.875, κ_w=0.968. Any change must be reflected in PROJECT.md and the LaTeX. Earlier n=155 baseline was 2,315 entities.
4. **No hardcoded paths.** Always import path constants from `scripts/config.py`.
5. **`validate_ground_truth.py` must exit 0** after any change to `generate_dataset.py` or `annotate_dataset.py`.

## Things that look like bugs but aren't

- **Several detectors in `evaluation_engine.py` warn at runtime and fall back** to simpler implementations: `Regex+Presidio`, `NER+Presidio`, `Regex+Context`, `Membership-inference`, `Set-intersection`, `LLM-as-Judge`. These are deliberate Phase 1 placeholders (PROJECT.md §11.3) — the warning is the contract, not noise. Do not silence them.
- **`CROSS_REFERENCE` is created in `annotate_internal_memo()` without going through `ENTITY_SPECS`.** Intentional — cross-references are document-level metadata, not field-level PII. The `Entity types used: 32 / 37` printout filters to `ENTITY_SPECS` members only.
- **`reidentification_risk.py` per-line print shows `Unique: N/100 (X%)` even at n=645.** The `/100` denominator is a stale leftover; the percentage itself is computed correctly against the actual sample size, and the saved JSON is unaffected.
- **Five entity types are never instantiated** — CREDIT_CARD, PASSPORT_ID, MEMBERSHIP, QUASI_IDENTIFIER, PARTIAL_ADDRESS. Documented scope decisions, not bugs.

## Conventions

- Never split, rename, or merge existing scripts — granularity matches the thesis chapters.
- No databases, ORMs, frameworks, or heavyweight deps in Phase 1. JSON files are correct for this scale.
- No unit tests in Phase 1; `validate_ground_truth.py` is the test framework. Add `pytest` only when Phase 2 multi-seed runs require it.
- Preserve docstring style: header block with `=== `, function docstrings reference `Table 6.1 →`, comments explain the *why* not the *what*.
- When a change affects a number that appears in PROJECT.md (155, 1000, 2315, 14935, 0.875, 0.968, etc.), update PROJECT.md and the LaTeX in the same change.

## Where deeper context lives

- `PROJECT.md` — operational source of truth; read first
- `docs/Threat_Model_Document.pdf` — Chapter 2; full attacker profiles + Table 6.1
- `docs/Formal_Leakage_Definitions_and_Ground_Truth.pdf` — Chapter 3; the formal foundations of this codebase
- `docs/State_Of_The_Art.pdf` — Chapter 1; literature review
- `roadmap.markdown` — internal phase planning
