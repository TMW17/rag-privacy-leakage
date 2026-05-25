# Phase 3 Starting Priorities

Source: Phase 2 baseline (ASR_strict augmented = 28.8%, n=52 scenarios).
All section references point to `report/PHASE2_BASELINE_REPORT_v2.md`.

---

## Threat landscape summary (from §4 and §5)

| Attack family | ASR_strict | Mean S (given leak) | Priority |
|---------------|------------ |---------------------|----------|
| F1_DIRECT_PII | 77.8%       | 9.30                | CRITICAL |
| F2_LINKABILITY | 63.3%      | 9.07                | CRITICAL |
| F3_DIRECT_INJECTION | 0.0% | 4.90              | LOW      |
| F4_OBFUSCATION | 0.0%       | 0.72                | LOW      |
| F5_JAILBREAK   | 6.7%       | 1.85                | MEDIUM   |
| F6_RECON       | 11.1%      | 2.80                | MEDIUM   |
| F7_SOCIAL_ENG  | 0.0%       | 1.20                | LOW      |
| F8_CORPUS_POISONING | 14.3% | 0.0 (not yet S-scored) | HIGH |

---

## Layer 1 — Input filtering (query sanitisation, prompt injection guards)

**Status: DEPRIORITIZED.**

F3 (Direct Injection) ASR_strict = 0%.  F5 (Jailbreak) ASR_strict = 6.7%.
F7 (Social Engineering) ASR_strict = 0%.  The Claude Sonnet 4.6 system prompt
already refuses the vast majority of direct injection and jailbreak attempts.
Input filtering would produce the smallest absolute reduction in ASR_strict
and risks degrading legitimate query utility.

**Recommendation:** Implement a lightweight keyword blocklist as a baseline
safety rail, but do not invest ablation budget here until F1/F2 are mitigated.
Reference: §5.1 (F3 analysis), §5.5 (F5 analysis), Appendix B (refusal breakdown).

---

## Layer 2 — Presidio retrieval-stage PII redaction

**Status: HIGH PRIORITY.**

F1 (Direct PII) accounts for the largest share of ASR_strict leaks (77.8%)
and the highest severity scores (mean S = 9.30).  Presidio can redact PII
from retrieved chunks before they reach the LLM prompt, directly cutting the
retrieval surface.  The retrieval precision rate is only 8.33%, meaning the
system over-retrieves PII-dense chunks; a retrieval ACL layer would amplify
Presidio's impact.

**Target:** Reduce F1 ASR_strict from 77.8% to < 20%.
**Ablation configs:** Presidio (names only), Presidio (full taxonomy), Presidio
+ retrieval ACL, Presidio + chunk-level severity filter.
Reference: §4.2 (F1 deep dive), §6.2 (retrieval precision analysis),
Phase2.md §5 (Phase 3 tech stack sketch).

---

## Layer 3 — Conversation-aware refusal (memory-gated policy)

**Status: HIGH PRIORITY.**

F2 (Linkability) ASR_strict = 63.3% with mean S = 9.07 — nearly as dangerous
as F1.  Linkability attacks assemble PII across multi-turn context; a
single-turn refusal policy cannot stop them.  A conversation-aware guard that
tracks cumulative entity disclosure across turns and refuses when the
combination crosses a severity threshold is needed.

**Target:** Reduce F2 ASR_strict from 63.3% to < 15%.
**Ablation configs:** Per-turn entity tracking, session-level disclosure budget,
NeMo Guardrails conversational policy.
Reference: §4.3 (F2 multi-turn analysis), §5.2 (conversation memory logging),
Appendix A (hand-verified linkability cases).

---

## Layer 4 — Output filtering (post-generation PII scan)

**Status: SUPPLEMENTARY.**

Output filtering (Presidio on the LLM's generated text) acts as a last-resort
backstop.  It will catch some leaks that slip through Layers 2 and 3 but
introduces latency and risks over-redacting legitimate output.  Deploy after
Layers 2 and 3 are validated.

**Target:** Residual ASR_strict < 5% after Layers 2–3.
Reference: §6.3 (output filter design notes).

---

## Layer 5 — Corpus provenance validation (poisoning defence)

**Status: HIGH PRIORITY, NEW from W6.1.**

P3-POISON-007 confirmed that descriptive corpus poisoning (injecting a
plausible-sounding but false employee record into the ChromaDB collection)
is reproducible across all 3 runs.  The RAG system retrieved the poisoned
chunk in 85.7% of relevant queries (p3_retrieval_rate) and leaked the
fabricated PII in 16.7% of those retrievals.

A provenance validation layer — cryptographic document hashing at index time,
hash check before retrieval — prevents poisoned documents from entering
the retrieval pool.  This is a new Phase 3 requirement not in the original
Phase 2 plan.

**Target:** p3_retrieval_rate of poisoned docs → 0%.
**Ablation configs:** Hash-only guard, hash + metadata signature, hash +
collection isolation.
Reference: baseline/p4_offline_metrics.json (metric4), §4.8 (F8 corpus
poisoning), Appendix D (poisoned document examples).

---

## Ablation matrix

**Planned scope:** 32 defence configurations × 135 scenarios (52 Phase 2 +
83 extended for Phase 3 edge cases).

**Estimated API cost:** $50–70 (Claude Sonnet 4.6 at temperature=0).

**Utility metrics to measure alongside ASR_strict:**
- RAGAS (faithfulness, answer relevancy, context precision)
- BLEU / ROUGE-L (answer quality degradation)
- End-to-end latency p50 / p95 (measured via `loguru` JSONL timestamps)

**Recommended run order (lowest cost → highest cost):**
1. Layer 5 (provenance hash check) — cheapest, no LLM calls needed for guard
2. Layer 2 (Presidio retrieval redaction) — moderate cost
3. Layer 3 (conversation-aware refusal) — moderate cost + NeMo setup
4. Layer 2 + 3 combined — validates interaction effects
5. Layer 4 (output filter) — added on top of combined
6. Full stack (all layers) — reference configuration
7. Layer 1 (input filter) — last, as a regression check

---

## Files to read first

1. `report/PHASE2_BASELINE_REPORT_v2.md` — full 9655-word Phase 2 report
2. `baseline/baseline_metrics_augmented.json` — primary metrics (read programmatically)
3. `baseline/baseline_metrics_comparison.md` — engine-only vs augmented side-by-side
4. `judge_calibration/README_judge_calibration.md` — judge setup and κ results
5. `data/attack_scenarios_summary.csv` — 52 scenarios with IDs and families
