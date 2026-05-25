# Phase 3 Handoff Package

## What is this package?

This directory is a self-contained handoff from Phase 2 of a master's
thesis project (ESI Sidi Bel Abbès, AI & Data Science, 2025–2026) measuring
privacy leakage in enterprise RAG systems.  Everything a defense implementer
needs to begin Phase 3 is here: baseline metrics, judge calibration artefacts,
frozen analysis scripts, publication figures, and the full Phase 2 report.
No Phase 2 chat history or experiment logs are required.

## What was Phase 2's goal?

Phase 2 quantified how much PII a Claude-Sonnet RAG system leaks under four
attacker profiles (Internal, External, Admin, ThirdParty) across 52
adversarial scenarios grouped into 8 attack families.  It ran 267 query
turns (3 runs × scenarios), measured binary leakage L
and severity score S using a deterministic engine, and augmented those results
with an LLM-as-Judge (Claude Opus 4.7) to recover leaks the engine missed.
The campaign confirmed the dual-ASR framework: ASR_inclusive (engine ≥ sev 2)
as a conservative upper bound; ASR_strict (judge-confirmed ≥ sev 3) as the
operational signal.

## Headline findings

- **ASR_strict augmented: 28.8%** (vs. 28.8% engine-only before judge lift) — confirmed across 3 independent runs (σ = 0.0444)
- **F1 + F2 dominate: 100.0% of turn-level strict leaks** — F1 (Direct PII, 77.8%) and F2 (Linkability, 63.3%) are the primary attack surfaces; F3/F4/F7 ASR_strict ≤ 7%
- **W2.4 dual-ASR confirmed: 58/58 sev=2 External turns flagged (100%)** — all engine-inclusive leaks for External profile came from severity-2 entities; strict threshold eliminates false positives
- **Judge–human κ = 0.83 (calibration passed)** — 46-sample hand-labelled triage; κ ≥ 0.80 acceptance threshold met; see judge_calibration/
- **P3-POISON-007 descriptive corpus poisoning reproducible 3/3 runs** — poisoned document injection via ChromaDB alternate collection confirmed as a viable threat vector; see baseline/p4_offline_metrics.json

## Where do I start Phase 3?

See [phase3_starting_priorities.md](phase3_starting_priorities.md) for the
defence layer ranking, ablation matrix plan, and per-layer rationale linked
to specific report sections.

## What is NOT in this package and where to find it

| What                     | Where to find it                              |
| ------------------------ | --------------------------------------------- |
| Raw experiment JSONL logs | Git repo, tag `w6.1-augmented`, `experiment_logs/` |
| Phase 1 corpus artefacts | Git repo, tag `w6.1-augmented`, `data/ground_truth/` |
| ChromaDB vector store    | Git repo, tag `w6.1-augmented`, `data/rag_index/` |
| Earlier baseline (W3.4)  | Git repo, tag `w3.4-complete`                 |
| W5 calibration state     | Git repo, tag `w5-complete`                   |
| Poisoned document sources | Git repo, `scenarios/poisoned_documents/`    |
| Scenario registry (JSON) | Git repo, `scenarios/registry/v1_queries.json` |

Experiment logs and the corpus are excluded from this package to keep the
total size under 50 MB and because they are fully reproducible from the
tagged repo state.
