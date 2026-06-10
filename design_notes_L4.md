# Phase 6 — design spine: a stateful linkage defense for the F2 residual

> **STAGE 0 (this document): design + asset audit only. No pipeline code, no API calls.**
> Written to be reviewed before any build, like the chapter spines.

> ### ⚠️ Naming: the requested "L4" is already taken — this layer is **L7**
> The committed pipeline (`scripts/phase3/defense_pipeline.py`) already defines, in order:
> **L1** input filter, **L2** retrieval redaction (+ an L2-LLM variant), **L3** conversation-state
> refusal (already *stateful*), **L4** = *output filter* (Presidio on the response), **L5**
> provenance + role-based ACL, and **L6** = *linkage recall-closure* (salary/medical suppression,
> Task 3.5). The 5-digit config core `C[L1 L2 L3 L4 L5]` is fixed. So the new k-anonymity linkage
> gate is the **next free index, L7**. This file keeps the requested name `design_notes_L4.md`,
> but the layer is called **L7** throughout to avoid colliding with the existing L4 / L6.
> **Decision for review:** confirm the name **L7** (recommended), or specify another.

---

## 0. Stage-0 review outcome — decisions locked

Reviewed; Stage 0 stands. Decisions:
1. **Name = L7** — confirmed. The requested "L4" collides with the committed output-filter **L4**
   and, more importantly, the linkage **recall-closure L6** (salary/medical suppression). Viva
   consequence to address in the write-up: **L6 already targets linkage**, so the framing must say
   *why L6 was not enough* and what L7 adds — combinatorial, cross-turn **k-anonimity** over QI
   *combinations*, versus L6's single-attribute recall-closure.
2. **Judge spend = engine-first, then judge (staged; do NOT skip the judge).** Engine-score the F2
   campaign first (free) as a direction check; only if the engine moves do we re-judge the new F2
   outputs with Opus-v2 (small, sha256-cached spend). An L7 result on engine-alone would be exactly
   the single-instrument error RQ3 exposes — the judge is the primary verdict.
3. **k-threshold = LOCKED to the sweep k ∈ {2, 5, 10}, k = 5 reference.** Yields the *knee-for-k*
   security–utility curve (the thesis's Pareto-knee move applied to linkage); ~3× the cells / judge
   spend, greenlit. **Pre-registered expected shape (monotonic):** tightening k should *monotonically*
   lower F2 ASR and *raise* the utility cost (k=2 barely moves F2 at low cost; k=10 moves it most at
   heavy cost, hardest on the benign control). A **flat** (F2 unchanged across all three) or
   **inverted** curve is a gate bug to debug — **not** a real null. Registered now so Stage 4 reads
   the curve honestly rather than rationalising whatever comes out.

**QI-consistency — VERIFIED on disk (no drift between thesis and extension).** The pre-registered
seven-QI set is **identical** to `scripts/reidentification_risk.py::quasi_identifiers` =
`{department, salary_range, medical_condition, performance, gender, age_range, office_location}` —
*not* a superset chosen now. The committed headline figures are subsets of it: **84/100** = the worst
**4-subset** `{department, medical_condition, age_range, office_location}`; **l-div 40/63** = the
**3-subset** `{department, salary_range, medical_condition}` (sensitive set `{name, national_id,
salary}`; `salary` enters both as the `salary_range` QI and as a protected sensitive attribute, per
the committed analysis). Stage 1's consistency check (recompute 84/100 + 40/63 from the
generalization hierarchy) must therefore reproduce; if it does not, the QI definition drifted and
Stage 1 stops.

---

## 1. The problem, precisely

**What survives.** Judged-strict ASR (`results/phase3/ablation/metrics/final_metrics.json`,
`per_cell[*].judged_strict`):

| Config | overall judged ASR | **F2_LINKABILITY** |
|---|---|---|
| C00000 (none) | 0.2885 | **0.60** |
| C10000 (L1) | 0.3654 | 0.70 |
| C01000 (L2) | 0.1923 | 0.70 |
| C00100 (L3) | 0.3462 | 0.60 |
| C01100 (L2+L3, knee) | 0.1923 | 0.70 |
| **C11111 (full)** | **0.1731** | **0.60** |

F2 is **0.60 at baseline AND at the full stack** — redaction never reduces it (it even rises to
0.70 mid-stack, an artefact of redaction reshaping the response without removing the linkage).
With 10 live F2 scenarios, F2 ≈ 6 leaks, i.e. **~2/3 of the 17.3% full-stack residual is F2.**
Cutting F2 is the only lever that materially moves 17.3%.

**Why redaction can't touch it.** L2/L4 remove *discrete PII spans* (a name, an SSN, a salary
string). F2 leakage is **re-identification by linkage**: a person reassembled from
quasi-identifiers (QIs) — department + age-range + office + medical condition — each individually
innocuous and *not* a redactable PII span. The disclosure is a property of the **combination**,
surfaced **across turns**, not of any single field.

**F2 is multi-turn (verified).** The 10 live F2 scenarios (`scenarios/registry/v1_queries.json`,
`attack_family = F2_LINKABILITY`) are P1-LINK-001..007 (Internal) + P2-LINK-001..003 (External),
2–4 turns each. `results/phase3_4/l3_accumulation_submetric/l3_firing.json` confirms the existing
stateful L3 fires **only** on F2 multi-turn cases (P1-LINK-002, P1-LINK-007, P2-LINK-001).

**The sobering anchor.** C00100 (L3 alone) judged F2 = **0.60 = baseline**: L3's stateful refusal
*fired* on 3 scenarios yet judged F2 **did not move**. The attack discloses the QIs in *earlier*
turns; refusing at the final turn is too late — the judge already counts the accumulated linkage.
**This is the bar L7 must clear: not "fire," but reduce the judged leak by acting turn-by-turn.**
It is also the honest risk: if the residual is genuine emergent linkage even over *coarsened* QIs,
L7 may move it only partially, or not at all.

A defense must therefore reason over **QI combinations, across turns** — not over single fields.

---

## 2. The design — L7: a stateful k-anonymity / l-diversity context gate

**Placement (matches the existing redaction layer).** L2 (redaction) is wired in the *decomposed*
path **post-retrieval, pre-generation**: `retrieve → L5 → ctx-min → L2 → L6 → _generate → L3 → L4`.
Per the instruction to match how redaction is wired, **L7 sits in the same place — post-retrieval,
after L2/L6, immediately before `_generate`** — so it operates on the **retrieved context** (which
has *structured* QI fields), not on free-text output. This deliberately avoids the output-side
QI-detection detector-gap (department / age / office are not standard PII types Presidio catches).

**Statefulness (what makes it different from per-response redaction).** Like L3's
`_l3_state`, L7 keeps **per-conversation** state, reset in `begin_scenario()`. It tracks, per
retrieved target record, the set of QI (field → value) disclosures it has **allowed through so far**
across turns.

**Mechanism (k-anonymity gate).** For the current turn's retrieved records, for each record:
1. accumulate the QI values about that record disclosed so far + the new ones this turn;
2. compute the **candidate-set size** `k` = number of corpus records (out of 100) matching the
   accumulated QI constraints (recomputed *live* against the corpus — see §3);
3. if the next QI would push `k` **below the threshold**, **generalize** it (age 34 → "30–40";
   "Cardiology, 3rd floor" → "Medical division"; salary 92k → "50–100k") or, if no generalization
   level keeps `k ≥` threshold, **suppress** it.
Optionally enforce **l-diversity** (≥ l distinct sensitive values within the candidate set) as a
secondary check; k-anonymity is primary for Stage 1.

**Pre-registered parameters (committed here, before any run — see §3 for why this matters).**
- **QI set (fixed, from Phase 1 — NOT chosen to beat F2):** exactly the seven QIs in
  `scripts/reidentification_risk.py` →
  `{department, salary_range, medical_condition, performance, gender, age_range, office_location}`.
- **Bucketing:** reuse `reidentification_risk.py`'s `age_range` (pd.cut) and `salary_range` bins.
- **k-threshold:** **k ≥ 5** — the script's own `k_anonymity_satisfied` definition and the standard
  HR/medical k-anonymity value. Pre-committed; report sensitivity to k ∈ {3,5,10} only if cheap.
- **Generalization hierarchies (pre-committed):** age → age_range → suppress; salary → salary_range
  → suppress; office_location → building/division → suppress; medical_condition → category →
  suppress; department / performance / gender → suppress (no natural generalization).

**Open Stage-1 implementation detail (flagged, not yet decided):** exactly how per-turn QI
constraints are attributed to a target — per *retrieved record* (clean: the gate has each record's
structured QIs) vs per accumulated *conversation constraint*. Stage 1 picks one and documents it;
this does not change the Stage-0 design or audit.

---

## 2.1 QI generalization hierarchy + Stage-1 consistency check — DONE (PASS)

Concrete ladders (machine-readable in `scripts/phase3/l7_consistency_check.py` → `QI_HIERARCHY`);
L0 = committed Phase-1 bucket, last step = SUPPRESS; L1 groupings are the **actual** corpus value
sets (not invented):

| QI | L0 (committed) | L1 generalization | terminal |
|---|---|---|---|
| age_range | decades 20-30 … 60-70 | ≤40 / 40-60 / >60 | suppress |
| salary_range | <50k … >110k | <70k / 70-110k / >110k | suppress |
| department | {Engineering, Finance, HR, Legal, Marketing} | Technical / Corporate Services / Commercial | suppress |
| office_location | building+floor (5 values) | building (A/B/C) → on-site | suppress |
| medical_condition | {anxiety, asthma, diabetes, hypertension, none} | mental-health / respiratory / cardiometabolic / none → has-condition/none | suppress |
| performance | {excellent, satisfactory, needs improvement} | meets / below | suppress |
| gender | {female, male} | (none) | suppress |

**Consistency check (`l7_consistency_check.py` — FREE: pure-Python, no pandas/API/pipeline) → PASS.**
An independent reimplementation reproduces the committed re-id headlines from L0:
k-anon worst 4-subset {department, medical_condition, age_range, office_location} = **84/100**;
l-div 3-subset {department, salary_range, medical_condition} = **40 of 63** vulnerable; and every
corpus value is covered by its L1 map. **No QI drift** — the gate's k-universe is exactly the one
the thesis defends. The check is the executable QI-pre-registration guard and exits non-zero on any
drift (re-run it after any QI/bucket change).

---

## 3. The circularity hazard — the single most important methodological point

This is exactly the failure RQ3 (panel circularity) predicts: **if the defense is optimised against
the very metric that scores it, "success" is circular and worthless at viva.** Two separations are
written into the design and must hold:

**(a) The gate's mechanism ≠ the success metric.** The k-computation (re-id logic) **drives** the
gate (decides when to generalize/suppress). Whether **F2 actually dropped is judged ONLY by the two
independent instruments the thesis already uses** — the rule-based **engine**
(`check_response_for_leakage`) and the **Opus 4.7 / prompt-v2 judge** — on the F2 scenarios.
`reidentification_risk.json` / `reidentification_risk.py` are **never** used to claim success.

**(b) The achieved-k is NOT a result.** Because the gate raises `k` by construction, the post-gate
`k` is **mechanically guaranteed to rise** and will **not be reported as an outcome.** Only
**engine + judge F2 ASR, ΔS, and utility** count as results.

**(c) The QI set is a *shared variable* — pre-registered, not fitted.** The gate generalizes the
same attributes that make F2 succeed, so it is by design tuned to the corpus's known uniqueness
structure. This is acceptable **only because the QI list is the fixed Phase-1 list (§2), committed
in this spine before any run, and not adjusted to F2 outcomes.** Stated plainly so the viva question
"did you pick QIs to beat F2?" is answered in advance: **no — the QI list predates and is
independent of the F2 evaluation.**

---

## 4. Config encoding — extend to a 6th bit, keep every old number bit-compatible

**Current encoding (verified).** `results/phase3/ablation/config_set6.json`:
`bit_layout = [L1_input_filter, L2_retrieval_redaction, L3_conversation_refusal, L4_output_filter,
L5_provenance_check]` — a **5-bit** core (2⁵ = 32 space; 6 cells run). `DefenseConfig` in
`defense_pipeline.py` has extra toggles (L2-LLM, context_minimization, confidence_threshold, L6,
audit_log) that are **outside** the 5-bit core. `future_work_configs` are unrun **5-bit** cells —
no 6th layer exists yet.

**Extension.** Add **one new bit, L7**, as the 6th digit → **6-digit configs** `C[L1 L2 L3 L4 L5 L7]`:
- `DefenseConfig` gains `L7_linkage_gate: bool = False` (default False).
- New `bit_layout` appends `L7_linkage_gate`; new cells carry 6-char `bit_vector`.
- **Bit-compatibility (non-negotiable):** every existing 5-digit cell ≡ its 6-digit form with
  **L7 = 0**. The committed cells (C00000…C11111) and every committed metric/log are **unchanged** —
  L7 defaults off, the existing code paths are untouched, and old IDs keep their old numbers. New
  work is written to **new** cell IDs / output dirs only.
- **New cells to run (§5):** `C000001` (L7 alone) and `C111111` (full stack + L7). Baselines
  `C00000` and `C11111` are reused, not regenerated.

---

## 5. Evaluation plan

**Scenarios.**
- **Primary:** the **10 live F2 scenarios** (P1-LINK-001..007, P2-LINK-001..003; multi-turn).
- **Control (collateral damage):** the **30 benign queries BEN-001..030**
  (`results/phase3/utility/utility_results.json`) + the non-F2 attack families — to measure
  over-suppression. **Predicted failure mode (write it up as *expected*, not a bug):** L7 generalizes
  department / age / office — precisely the *low-severity structural* attributes benign queries ask
  about. So utility (faithfulness, context-precision) will fall on BEN-001..030 **more** than the
  C11111 baseline already did. A large benign-utility drop is the *point* of the control, not a
  failure.

**Conditions (to isolate L7 and avoid the L3 double-count).**
- `C000001` (**L7 alone**) vs `C00000` — clean marginal attribution of L7.
- `C111111` (**full + L7**) vs `C11111` — marginal contribution *inside* the stack.
- **L3 double-count caveat (write explicitly):** L3 already fires on P1-LINK-002, P1-LINK-007,
  P2-LINK-001. On those ~3 scenarios L7 **cannot claim credit** — its real contribution is on the
  other ~7 (and on any judged leak L3 failed to move, which is *all* of them, since C00100 judged
  F2 = baseline). Report L7's F2 reduction both stack-free (L7 alone) and in-stack.

**Metrics.** F2 ASR by **engine** *and* **judge** (strict); **ΔS** (from engine logs, no model
calls); **utility** (faithfulness / context-precision / latency). Never the gate's achieved-k (§3).

**Invariants (identical to the whole thesis).** SUT Claude Sonnet 4.6 / temp 0 / max_tokens 1024;
judge Claude Opus 4.7 / **prompt v2** / Anthropic endpoint; embeddings all-MiniLM-L6-v2; ChromaDB
top-k 5; chunk 512 / overlap 64; seed 42; `begin_scenario()` first (resets state).

**Budget note (surfaced, needs your greenlight).** The **engine** path is free. The **judge** is an
**Anthropic Opus 4.7 API call** (`judge_ablation.py`, sha256-cached): L7 produces *new* F2 responses
→ new unique (profile, response) pairs → **fresh Opus calls = real spend** (small — only the F2
scenarios' changed turns). Honest Stage-1 default: **run + engine-score immediately (free); judge
the new F2 outputs only on your go-ahead.** Do not assume the judge is free.

---

## 5.1 Stage-2 carry-forward — watch-items (from review)

1. **Firing test FIRST (cheap gate, before the campaign + any spend).** On a known F2 scenario,
   confirm L7 carries QI state *across turns* and generalizes the *right* attribute as QIs
   accumulate — i.e. does what L3 (last-turn refusal) and L6 (single-attribute recall-closure)
   structurally cannot. **Firing ≠ success:** it must suppress the *accumulating* QI mid-conversation,
   not just trigger. Only if it fires correctly does the full campaign run.
2. **The "extractor" is value-localization, not open-vocab extraction.** L7 acts on the *structured*
   retrieved context (chunk → doc_id → corpus record), reading QI *values* cleanly and tracking its
   *own* allow-decisions — no parsing of SUT output to compute k. The only text operation is
   localizing/replacing a *known* value-string in the chunk (like L2). Stage 2 must still **measure
   that localization's precision/recall** on the F2 cases: a missed value = the gate silently passes
   a QI ⇒ F2 won't move ⇒ **report as the localization/NER-recall caveat, never as "L7 fails."**
3. **Genuine residual L7 cannot close:** SUT *reasoning/paraphrase* over the generalized context
   (reasoning-based linkage). L7 controls context, not inference — this is the honest ceiling on the
   partial F2 reduction.
4. **L6/L3 distinction is the viva bar.** L6 (recall-closure) and L3 (refusal) both already targeted
   this leak and did *not* move judged F2. Stage 2 must show what L7 adds — cross-turn, combinatorial
   QI suppression as attributes accumulate — and report its marginal effect where L3/L6 already act.

## 6. Honest expectations (stated up front, so there is no pressure to fabricate)

- F2 falls **partially**, likely **not to zero** — coarsened QIs can still re-identify, and L3
  already showed a stateful gate can fire without moving the judged leak.
- **Utility drops**, hardest on the benign control set (§5) — legitimate structural info is
  generalized/suppressed. That cost is the security–utility tradeoff, reported as-is.
- Whatever the engine + judge say is the result — a partial F2 reduction at a measured utility cost
  is a **legitimate finding, not a failure.** No optimisation toward a clean win.

---

## 7. Asset audit (verified on disk — path · schema · status)

| Asset | Path | One-line schema | Status |
|---|---|---|---|
| Re-id uniqueness data | `results/reidentification_risk.json` | `k_anonymity_analysis` (91 QI-combos → k_min/k_mean/unique_records/risk%), `l_diversity_analysis` (63 groups → group_size, l_values, vulnerable), `summary` (QIs tested, 100 records) | **EXISTS** — reference only (§3); QIs = the 7 listed |
| Re-id scorer (gate k-logic) | `scripts/reidentification_risk.py` | defines QI set + `age_range`/`salary_range` bucketing + per-combo equivalence-class k (groupby) | **EXISTS** — gate recomputes k live from this logic |
| Synthetic corpus (k computed against) | `data/ground_truth/ground_truth.json` | 100 `employee_records`, machine-readable QI keys: `department, age, office_location, medical_condition, salary, performance, gender`, … | **EXISTS** — all QI fields present |
| Corpus lookup / annotations | `data/ground_truth/ground_truth_index.json`, `…_annotations.json` | flat doc_id→record; entity annotations (used by L5/engine) | **EXISTS** |
| F2 scenario definitions | `scenarios/registry/v1_queries.json` | 13 `F2_LINKABILITY` (10 live multi-turn P1/P2 ×2–4 turns + 2 P4 offline); fields: scenario_id, attacker_profile, attack_family, `turns[]`, success_criteria | **EXISTS** — multi-turn confirmed |
| Defense-layer code (wire point) | `scripts/phase3/defense_pipeline.py` | `DefensePipeline` + `DefenseConfig`; decomposed path with explicit L2/L6 post-retrieval seam where L7 plugs in | **EXISTS** |
| Config encoder | `scripts/phase3/ablation_runner.py`, `results/phase3/ablation/config_set6.json` | 5-bit cells (`bit_vector`, `bit_layout`, `defense_config`); `l5_acl=False` in ablation | **EXISTS** |
| Baseline — ASR | `results/phase3/ablation/metrics/final_metrics.json` | `per_cell[*].{engine_strict,judged_strict}.{overall,per_family}` (F2 0.60; full-stack 0.1731) | **EXISTS** — unchanged baseline |
| Baseline — severity | `results/phase3/ablation/metrics/severity_aggregates.json` | `per_cell_mean_S`, `delta_S_vs_baseline`, `S_residual_full_stack` | **EXISTS** |
| Baseline — utility / control | `results/phase3/utility/utility_results.json` | `per_query` BEN-001..030 with faithfulness + context_precision + latency | **EXISTS** — 30 benign control queries |
| Judge path | `scripts/phase3/judge_ablation.py` + `scripts/llm_judge.py` (`LLMJudge(prompt_version="v2")`) | Opus 4.7 / prompt v2 / Anthropic; sha256 judge cache | **EXISTS — but re-judging L7 outputs costs Anthropic spend** (flagged §5) |

**No missing assets; no schema gap blocks the gate as designed.** The only non-free dependency is
the judge re-run (budget, §5) — a cost gate, not a missing artefact.

---

## 8. Stage-0 confirmations + STOP

- **Circularity separation:** gate mechanism (re-id k) ≠ success metric (engine + judge); achieved-k
  is never reported; QI list is the fixed Phase-1 set, pre-registered above. ✔
- **Config extension:** new 6th bit L7; old 5-digit cells ≡ 6-digit with L7 = 0; every committed
  baseline/number unchanged. ✔
- **Honest-expectations frame:** partial F2 reduction at a utility cost, possibly not to zero,
  reported as-is; no optimisation toward a clean win. ✔
- **Blockers:** none. **All params locked (§0):** L7 name; engine-first→judge; k-sweep {2,5,10} /
  k=5 ref / monotonic shape pre-registered; QI set + generalization hierarchy pre-registered and
  **consistency-checked PASS** (§2.1, reproduces 84/100 + 40/63, no drift).
- **Next gate:** advisor verifies the hierarchy reproduces the committed re-id numbers (it does —
  `l7_consistency_check.py` exits 0), **then** Stage 2 = build the gate + run (pipeline code + the
  greenlit judge spend). Nothing built/spent yet.

**PAUSE — Stage 0 ends here. No pipeline code, no API spend until you review this spine + the audit.**
