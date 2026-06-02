# Task 2.4 — Final Security Metrics & RQ Answers

**Metric ordering (stated):** the **judged augmented ASR** is the **PRIMARY** reported metric (Opus 4.7 judge; **judge–human κ=0.827**, corroborated cross-vendor claude–gpt-oss **κ=0.843**); **engine ASR** (rule-based, engine–human **κ=0.164**) is the **secondary / lower bound**.

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

## ΔASR_strict per family (vs C00000)

_cell = **judgedΔ** / engineΔ; `~` within noise (judged floor 0.08, engine 0.04), `↓/↑` = real effect. Small-N families are coarse (1 scenario = 1/N)._

| family (N) | C10000 (L1) | C01000 (L2) | C00100 (L3) | C01100 (L2+L3) | C11111 (full stack) |
|---|---|---|---|---|---|
| F1 (9) | +0.0~ / +0.0~ | -0.5556↓ / -0.5556↓ | +0.0~ / +0.0~ | -0.5556↓ / -0.5556↓ | -0.5556↓ / -0.5556↓ |
| F2 (10) | +0.1↑ / +0.1↑ | +0.1↑ / -0.3↓ | +0.0~ / -0.1↓ | +0.1↑ / -0.3↓ | +0.0~ / -0.4↓ |
| F3 (6) | +0.3333↑ / +0.1667↑ | +0.0~ / +0.0~ | +0.3333↑ / +0.1667↑ | +0.0~ / +0.0~ | +0.0~ / +0.0~ |
| F4 (5) | +0.0~ / +0.0~ | +0.0~ / +0.0~ | +0.0~ / +0.0~ | +0.0~ / +0.0~ | +0.0~ / +0.0~ |
| F5 (5) | +0.0~ / +0.0~ | -0.2↓ / -0.2↓ | +0.0~ / +0.0~ | -0.2↓ / -0.2↓ | -0.2↓ / -0.2↓ |
| F6 (3) | +0.0~ / +0.0~ | +0.3333↑ / +0.0~ | +0.0~ / +0.0~ | +0.3333↑ / +0.0~ | +0.3333↑ / +0.0~ |
| F7 (7) | +0.0~ / +0.0~ | +0.0~ / +0.0~ | +0.0~ / +0.0~ | +0.0~ / +0.0~ | +0.0~ / +0.0~ |
| F8 (7) | +0.1428↑ / +0.0~ | -0.1429↓ / +0.0~ | +0.1428↑ / +0.0~ | -0.1429↓ / +0.0~ | -0.1429↓ / +0.0~ |

## ΔASR_strict per profile (vs C00000)  _(same cell format; ThirdParty = offline, not a cell)_

| profile (N) | C10000 (L1) | C01000 (L2) | C00100 (L3) | C01100 (L2+L3) | C11111 (full stack) |
|---|---|---|---|---|---|
| Admin (7) | +0.1428↑ / +0.0~ | -0.1429↓ / +0.0~ | +0.1428↑ / +0.0~ | -0.1429↓ / +0.0~ | -0.1429↓ / +0.0~ |
| External (27) | +0.037~ / +0.037~ | -0.1111↓ / -0.1852↓ | +0.037~ / +0.037~ | -0.1111↓ / -0.1852↓ | -0.1482↓ / -0.1852↓ |
| Internal (18) | +0.1111↑ / +0.0555↑ | -0.0555~ / -0.2222↓ | +0.0556~ / -0.0556↓ | -0.0555~ / -0.2222↓ | -0.0555~ / -0.2778↓ |

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

- **judge–human κ = 0.827** — the judge's validation (binary, 46-record sample).
- claude–gpt-oss κ = **0.843** (cross-vendor agreement); gpt-oss–human κ = 0.777 (independent vendor vs human).
- claude–annotator2 κ = 0.775; inter-human (annotator2 vs primary) κ = 0.692.
- single-Claude FPR **0.083** vs majority 0.056.
- Claude-only operational (no 3-judge full-ablation run; credits preclude one). **No fabricated 3-judge full-ablation numbers.**

## Detection metrics per cell (#2 — defense vs annotation leakability GT)

_positive = leak present; GT = annotation leakability. **residual_leak_rate** (TP/leakable) is the security number — a **lower bound** (F1). FPR/over-block on benign turns is mostly correctly-blocked attacks (adversarial corpus). This is NOT detector-vs-human accuracy (RQ3)._

| cell | residual_rate↓ (F1 LB) | Precision | Recall | F1 | FPR (benign) | FNR (prevent) | n_leak/benign | over_block |
|---|---|---|---|---|---|---|---|---|
| C00000 | 0.2093 | 0.9474 | 0.2093 | 0.3429 | 0.3333 | 0.7907 | 86/3 | 0 |
| C10000 | 0.28 | 0.913 | 0.28 | 0.4286 | 0.1429 | 0.72 | 75/14 | 11 |
| C01000 | 0.1163 | 1.0 | 0.1163 | 0.2084 | 0.0 | 0.8837 | 86/3 | 0 |
| C00100 | 0.1977 | 0.8947 | 0.1977 | 0.3238 | 0.6667 | 0.8023 | 86/3 | 0 |
| C01100 | 0.1163 | 1.0 | 0.1163 | 0.2084 | 0.0 | 0.8837 | 86/3 | 0 |
| C11111 | 0.12 | 1.0 | 0.12 | 0.2143 | 0.0 | 0.88 | 75/14 | 13 |

_All detection numbers computed from the **serialized `L`/`S` fields** in the logs (events[].severity + L), NOT in-memory leak_detected/severity_score. positive=leak present; GT=annotation leakability. residual_rate (TP/leakable) = security number, lower bound (F1). Per-cell vs HUMAN ground truth is not computable (human labels are baseline-only = RQ3); these are defense-vs-leakability metrics._
