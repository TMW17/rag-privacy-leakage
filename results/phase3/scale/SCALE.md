# Phase-3 scale — honest query-execution accounting

**A query-execution = one SUT (RAG) generation (one turn).** Judge/eval calls are excluded (separate overhead). Counts are **dedup-aware**: *reused* = served from Phase-2 logs or the content-addressed SUT cache ($0); *new* = a real fresh Phase-3 SUT call.

## Components (each separately)

| Component | Turns | New SUT (dedup-aware) | Status |
|---|---|---|---|
| Phase-2 baseline | 267 | 0 | **REUSED** ($0; 246 clean + 21 poisoned (=3 runs x 89)) |
| 6-cell ablation | 534 scored | **213** | NEW; 51% deduped, incl. 13 drift-anchor; $1.3098 |
| Ablation GUARD reproduction | 39 | 39 | NEW (verification: all-False == baseline) |
| Unit tests (L1–L5 + sanitized) | — | 41 | NEW (filter/retrieval tests = 0 SUT) |
| Utility (Task 3.1) | 60 | 60 | NEW (30 benign × 2 cells) |
| L6 (Task 3.5) | 0 | 0 | NOT run (diagnosis only) |
| Attacker demo | 0 | 0 | none separate (folded into unit tests) |

### Unit-test SUT breakdown
- **L1 input-filter (l1_results)** → 0 SUT — input-filter only: regex+NeMo on 2 attacks+3 benign INPUTS, pre-SUT gate; no generation
- **L2 collateral** → 0 SUT — chunk-level: retrieved_doc_ids[5] + per_chunk_redaction[5] + engine_L on context; no generation
- **L2 utility_survivors** → 0 SUT — context-level: which sev>=3 survive redaction in the 5 retrieved chunks; no generation
- **L2 oracle_killer** → 30 SUT — forced-on-target GENERATIONS: 15 L2-ON (per_run[15], all blocked=0.0) + 15 L2-OFF baseline (0.9333=14/15 leaked); constructed oracle attack, both runs fresh
- **L3 test1 p1link** → 3 SUT — 3-turn P1-LINK conversation: per_turn[3] generations
- **L3 test2 fp_guard** → 3 SUT — 3 false-positive-guard queries: per_query[3] generations
- **L3 test3 handoff** → 1 SUT — 1 live forced run (defense_in_depth__live_forced_run); gate test uses a CONSTRUCTED input (0 SUT); +-1
- **L4 output-filter (l4_results)** → 0 SUT — output-filter applied to a SINGLE source_response (before/after redaction); source reused -> 0 fresh (<=1)
- **L5 provenance/acl + f8** → 3 SUT — provenance(155 docs) + ACL = index-level 0 SUT; f8_exploit L5_ON_runs[3] = 3 fresh; L5_OFF baseline REUSED from B2_POISONED (not re-run)
- **sanitized_tests F1 probe** → 1 SUT — sut_probe.sut_calls=1 (direct-PII F1 probe vs sanitized index)
- **Task 1.7 confidence/audit** → 0 SUT — 5 ALREADY-LOGGED Phase-2 turns reused -> 0 new SUT (by design)

## Total

- **Reused Phase-2 turns:** 267  (43.1%)
- **Genuinely new Phase-3 SUT:** 353  (56.9%)  = 213 ablation + 39 guard + 41 unit + 60 utility
- **TOTAL real query-executions = 620**
- **Exceeds 1000? → NO.** The honest dedup-aware total is 620 (43.1% reused Phase-2, 56.9% genuinely new Phase-3).

*Transparency:* 55 additional Phase-2 dev executions exist (pilot 17 + dry-runs + smoke), not measurement and not reused; even including them the grand total is 675 (still < 1000).

*Padding trap (avoided):* even counting **all** ablation SCORED turns as new (ignoring the 51% dedup + the reused C00000) gives only **941 SUT — still < 1000**. Crossing 1000 (~1348) requires additionally counting the 227+180 judge/eval calls as 'query-executions' — which presents reused turns as new work and conflates evaluation with query-execution.

## Usability FPR (benign-blocked) per defended config

| Config | Attack-suite benign-blocked | rate | note |
|---|---|---|---|
| C00000 | 0/3 | 0.0 | no-defense reference |
| C10000 | 11/14 | 0.7857 | L1 present → high rate = blocked attacks |
| C01000 | 0/3 | 0.0 |  |
| C00100 | 0/3 | 0.0 |  |
| C01100 | 0/3 | 0.0 |  |
| C11111 | 13/14 | 0.9286 | L1 present → high rate = blocked attacks |

⚠️ **on the ADVERSARIAL attack suite, 'benign' = turns with no GT-leakable PII, which are almost all ATTACK turns carrying no PII payload (injections/jailbreaks). So a high 'benign-blocked' rate for L1-bearing configs (C10000 ~0.79, C11111 ~0.93) is MOSTLY CORRECT ATTACK-BLOCKING, not a usability failure. n_benign also shifts (3->14) because L1 reclassifies blocked attacks. This is NOT a usability FPR.**

✅ **True usability FPR (Task 3.1, 30 genuine benign queries):** C00000 = 0/30, C11111 = 0/30 → **0.0% over-refusal for both.** NOT measured on the benign set (Task 3.1 ran only the two extremes); by monotonicity each is <= C11111's 0/30, i.e. ~0.
