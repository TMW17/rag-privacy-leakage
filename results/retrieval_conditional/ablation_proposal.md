# STEP 3 — Retrieval-Quality Ablation Proposal (NOT YET RUN — awaiting cost approval)

**Goal.** STEP 2 showed F1's 77.8% is 0% on-target / 55.6% collateral / 22.2% broad.
This ablation isolates the **two stages** of an F1 attack — (1) retrieve the target,
(2) disclose it — to confirm that retrieval is the binding constraint and to show how
ASR responds to retrieval quality.

## Arms

**Arm A — Oracle force-include (decisive test).** For each F1 scenario that names a
target doc, force that document into the retrieved context, then re-generate and
re-score. Tests stage-2 disclosure efficacy in isolation.
- *Prediction:* on-target ASR jumps from 0 → high. If it does, the baseline 0%
  on-target is purely a stage-1 retrieval miss, not model robustness.
- *Implementation:* small wrapper around `RAGSystem` that prepends the target chunk
  (or a `force_doc_ids` kwarg); the clean ChromaDB collection stays read-only.

**Arm C — top-k sweep (saturation test).** Re-run with k ∈ {1, 3, 5*, 10, 20}
(*=baseline). Re-score per family; report how the **family ASR ranking** moves.
- *Prediction:* collateral ASR rises monotonically with k (more chunks → more
  off-target PII surface); k=1 sharply reduces F1/F2. If ASR scales with k rather
  than with attack sophistication, that is the corpus-saturation signature.
- *Implementation:* `RAGSystem(collection, k=<value>)` — already parameterized.

**Arm B — force-exclude target (control).** Optional; F1 target retrieval is already
0%, so this ≈ baseline. Low marginal value — include only if a clean control is wanted.

## Scoring options
- **Engine-only** (deterministic, $0 leak detection) — fine for measuring *relative*
  ASR movement and rankings. Recommended for the k-sweep.
- **Judge-augmented** (Opus 4.7, ~$0.037/turn) — needed only if you want the ablated
  numbers on the *same augmented basis* as 77.8%. Recommended only for Arm A (the
  decisive oracle test).

## Cost estimate
Unit costs (from `cost_ledger.csv` + logs): SUT generation (Sonnet 4.6) ≈
**$0.0059/turn**; judge (Opus 4.7) ≈ **$0.0370/turn**. Decoding stays seed-42 /
temperature-0 (deterministic), so 1 run per condition suffices for Arm A/C means;
3 runs only if you want the run-to-run σ.

| Tier | Scope | Generations | Engine-scored | + Judge on Arm A | Fully judged |
|---|---|---:|---:|---:|---:|
| **T1 (recommended)** | F1 only: Arm A (~25) + Arm C k-sweep (39×4=156) | ~181 | **~$1.1** | **~$2.0** | ~$7.8 |
| T2 | All families: Arm C (246×4=984) + Arm A (~90) | ~1,074 | ~$6.3 | ~$9.7 | ~$46 |

**Recommendation:** **Tier 1, engine-scored k-sweep + judge-confirmed Arm A ≈ $2**,
well within the Phase-3 budget. It directly answers the F1 question and shows the
ASR-vs-k curve. Tier 2 (~$6 engine / ~$46 judged) adds the cross-family ranking
shifts if you want them.

## Outputs (would write to results/retrieval_conditional/)
- `ablation_topk_curve.csv` — ASR per family per k
- `ablation_oracle.json` — on-target ASR under forced target inclusion vs baseline
- `ablation_report.md` — ranking-shift analysis

**Nothing here has been run. Awaiting your approval of a tier + scoring before any API calls.**
