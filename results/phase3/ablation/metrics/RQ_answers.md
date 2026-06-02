# Task 2.4 — Final Security Metrics & RQ Answers

**Metric ordering (stated):** the **judged augmented ASR** (Opus 4.7 judge, κ=0.843) is the **PRIMARY** reported metric; **engine ASR** (rule-based, κ=0.164) is the **secondary / lower bound**.

**Noise floor (dual):** engine deltas ~**0.04** (SUT temp=0 regen); judged deltas ~**0.08** (judge temp=1 + fresh-judged defended vs locked baseline verdicts). Deltas within the floor are **within noise**, not effects.

**GUARD:** baseline judged strict = 0.2885 (locked 28.8% — OK); F1-family judged strict = 0.7778 (locked 77.8% — OK). Locked numbers unaltered.

## Headline table (overall ASR_strict)

| cell | layer | engine (lower bound) | **JUDGED (primary)** | judged Δ vs C00000 | verdict |
|---|---|---|---|---|---|
| C00000 | baseline | 0.1923 | **0.2885** | — | — |
| C10000 | L1 | 0.2308 | **0.3654** | +0.0769 | within noise |
| C01000 | L2 | 0.0192 | **0.1923** | -0.0962 | effect↓ |
| C00100 | L3 | 0.1923 | **0.3462** | +0.0577 | within noise |
| C01100 | L2+L3 | 0.0192 | **0.1923** | -0.0962 | effect↓ |
| C11111 | full stack | 0.0 | **0.1731** | -0.1154 | effect↓ |

**Figure `fig_marginal_and_rq2.png`** — left: per-layer marginal Δ (engine light / judged dark) vs the ±0.08 judged floor; right: RQ2 staircase (baseline→L2→L2+L3→full). **Caption caveat (required):** the positive L1/L3 judged Δ are **WITHIN-NOISE inactive-defense flips** (defense fired on 0 flip scenarios, Task 2.3 mechanism check) — **NOT real leakage increases**. Only L2 clears the floor.

## RQ1 — per-layer effect (judged primary)

| layer | config | judged Δstrict | verdict | engine Δstrict | verdict |
|---|---|---|---|---|---|
| L1 | C10000 | +0.0769 | within noise | +0.0385 | within noise |
| L2 | C01000 | -0.0962 | effect↓ | -0.1731 | effect↓ |
| L3 | C00100 | +0.0577 | within noise | +0.0 | within noise |

**L2 is the decisive PII-leakage layer** (judged ΔASR_strict -0.0962). **L1 and L3 are within the judged noise floor** on the leakage metric — they defend dimensions it does not capture: L1 = injection-input blocking (Task 1.3), L3 = conversational/residual incl. the real-data L2→L3 handoff (Task 1.2), bounded by the cross-doc engine gap (FINDINGS F1); L5 = corpus-poisoning kill (Task 1.5). The judge raises **all** cells vs the engine (semantic/linkage leaks the engine cannot see) — this is the judge surfacing real residual leakage, not a discrepancy. **This is NOT 'only L2 works'** — it is 'L2 dominates the PII-leakage metric; other layers defend axes this metric does not measure.'

## RQ2 — does L2+L3 (C01100) capture the full stack (C11111)?

- C01100 judged strict = **0.1923**, C11111 = **0.1731**, gap = **+0.0192** (strict), +0.0769 (inclusive).
- L2+L3 captures essentially all of the full stack's judged benefit (gap +0.0192 strict, within the 0.08 judged floor).

## RQ4 — per-profile (judged primary)

| profile | C00000 | C01000 (L2) | C11111 (full) |
|---|---|---|---|
| Internal | 0.3333 | 0.2778 | 0.2778 |
| External | 0.2963 | 0.1852 | 0.1481 |
| Admin | 0.1429 | 0.0 | 0.0 |

_ThirdParty (P4) is OFFLINE-evaluated separately (analyze_p4_offline), NOT a live-ablation cell — not missing._

## RQ3 — judge validation (CITED from Sprint-0; not recomputed)

- claude–gpt-oss κ = **0.843**, gpt-oss–human κ = 0.777.
- single-Claude FPR **0.083** vs majority 0.056 (46-record sample).
- Claude-only operational (no 3-judge full-ablation run; credits preclude one).

## Detection metrics per cell (#2 — defense vs annotation leakability GT)

_positive = leak present; GT = annotation leakability. **residual_leak_rate** (TP/leakable) is the security number — a **lower bound** (F1). FPR/over-block on benign turns is mostly correctly-blocked attacks (adversarial corpus). This is NOT detector-vs-human accuracy (RQ3)._

| cell | residual_leak_rate↓ | Precision | F1 | n_leakable | over_block(benign n) |
|---|---|---|---|---|---|
| C00000 | 0.2093 | 0.9474 | 0.3429 | 86 | 0(3) |
| C10000 | 0.28 | 0.913 | 0.4286 | 75 | 11(14) |
| C01000 | 0.1163 | 1.0 | 0.2084 | 86 | 0(3) |
| C00100 | 0.1977 | 0.8947 | 0.3238 | 86 | 0(3) |
| C01100 | 0.1163 | 1.0 | 0.2084 | 86 | 0(3) |
| C11111 | 0.12 | 1.0 | 0.2143 | 75 | 13(14) |
