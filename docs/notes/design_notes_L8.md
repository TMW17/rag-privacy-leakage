# Phase 8 — design spine: L8 disclosure accounting (cross-query candidate-set tracking)

> **STAGE 0 (this document): design + asset audit + pre-registered reading rules. NO spend, NO build yet.**

> **HONEST FRAME.** L8 *bounds* the multi-turn (mosaic) linkage attack at best; it does **not** eliminate
> linkage. Single-query uniqueness and the authorised-user-with-external-knowledge case are **out of scope**
> and stated as such. No "solves." A null / feasibility-foreclosed result is a legitimate finding (cf. L7,
> P7). Pre-register the reading rules before any run; nothing post-hoc.

---

## 0. THE HEADLINE: L8 *is* option B, already rejected in L7 Stage 2 on committed evidence

During **L7 Stage 2** (design_notes_L4.md §2.2, committed), exactly this mechanism was proposed as
**option (B) "per-conversation candidate-set tracking"** and **rejected on evidence**:

> "(B) … was rejected on evidence: a *single* chunk already collapses k<5, so set-narrowing would also
> fire at turn 0 — B would rediscover the same finding after a redesign and more spend. The deeper point:
> the F2 leak in this corpus is **single-chunk combinatorial uniqueness, not cross-turn accumulation**."

The firing test then **falsified cross-turn accumulation directly**: `qi-accumulated-across-turns = 0` on
all three F2 scenarios, because **each employee chunk exposes 4–6 QIs at once**. So the foreclosure is the
headline, grounded in a *committed* finding: **L8 is closed for the same reason L7's cross-turn claim and P7
were** — the leak is single-chunk, so a candidate-set accountant fires at turn 0 (single-query, out of
scope), not progressively.

**One premise to correct (it does NOT erode the foreclosure):** this phase assumed the 10 F2 scenarios are
"not designed to test progressive narrowing." They **are** progressive-narrowing (§3). But *testability ≠ a
leak that requires multiple turns* — the scenarios can exercise an accountant, yet the leak is still
single-chunk. So the asset gap is the **mechanism**, not the scenarios.

## 1. The mechanism — and why the chunk-vs-query-constraint fork collapses

A **per-session accountant**, stateful across queries: extract the QI constraints in play, maintain the
running **intersection** candidate set $C$ (corpus individuals consistent with all constraints disclosed so
far), and on breach $|C| < k$ refuse or coarsen (answer a suppressed aggregate — counts not individuals).

Two implementations seem available, but **a rational adversary collapses them to the same outcome**:
- **(i) chunk-based** ($C$ from retrieved chunks): each chunk is a full unique record ⇒ $|C|=1<k$ at
  **turn 0** ⇒ fires on the first retrieval = single-query, **out of scope**.
- **(ii) query-constraint-based** ($C$ from QI constraints named in the queries): narrows progressively
  (5→3→…) *only against an attacker who artificially spreads constraints across turns*. **A real adversary
  asks the combined query once** — `{Finance ∧ Algiers ∧ over-40}` in a single turn — at which point $|C|<k$
  **immediately, at turn 0, also out of scope.**

So **variant (ii) is not a live bounding mechanism.** It bounds *only* under one external precondition:
**the combined single query is independently blocked while the incremental sequence slips through.** In
this corpus that precondition is **false** — F2 leaks at 0.60 and the combined query works. Variant (ii)'s
honest home is therefore *contingent*: L8 has value **only layered on a deployment that already blocks
combined queries** (an input-control / governance precondition — the Ch8 defence-in-depth direction), **not
as a standalone defense and not as a property of L8 itself.**

## 2. Where it sits + the config bit

A **new seam**: post-retrieval, **session-stateful** across queries (L1–L7 were single-turn / per-chunk).
L8 is an **additive config bit** (like L6/L7), default **off**, bit-compatible: every committed cell
(C00000…C11111, L6, L7, P7) is reproduced **bit-for-bit unchanged**. Committed numbers FROZEN; L8 perturbs
nothing.

## 3. Asset audit + the gap verdict

| Asset | Status |
|---|---|
| QI hierarchy / consistency check (`l7_consistency_check.py`, 84/100 + 40/63) | **EXISTS** — gate |
| QI extractor (`l7_gate.py:extract_qis`, label-parse + gazetteer; p/r ≈1.0 structured, 1.0/0.85 prose) | **EXISTS** — reuse |
| 10 F2 scenarios (`v1_queries.json`, P1/P2-LINK) | **EXISTS** |
| Committed F2 baseline (judged 0.60) + Opus-v2 judge cache | **EXISTS** — comparator |

**GAP VERDICT — the scenarios CAN test progressive narrowing; NO new attack set is needed.** The 10
committed F2 scenarios are explicitly progressive (each turn adds a QI constraint;
`cross_turn_aggregation_required` + `max_k_anonymity` in every success-criteria; e.g. P1-LINK-001:
`Finance∧Algiers` → `∧over-40` → "their compensation"). The gap is the **mechanism** (§0–§1), not the assets.

## 4. Pre-registered reading rules (fixed BEFORE any run)

- **(d) Single-query-equivalence — THE gate (subsumes the variant fork).** Does the combined-constraints
  query asked **once** leak as much as the full multi-turn sequence? If yes, the multi-turn structure is
  unnecessary, both variants fire at turn 0, and L8 (cross-query) is **moot** — the operational test of the
  single-chunk finding. This is the predicted failure point.
- **(a) "Bounds the mosaic attack"** = judged F2 on the narrowing sequences drops vs a **no-accounting
  baseline**, beyond the n=10 **±0.30** CI. Within CI = **null**.
- **(b) Random-throttle confound (mandatory, anti-circularity)** = a baseline refusing at the **same rate**
  as L8 without candidate-set logic. A drop that doesn't beat it = **throttling artifact, not accounting**.
- **(c) Detection trace — a check to run, NOT a predicted failure.** L8's detection is parsing **explicit QI
  constraints from queries** and intersecting against the frozen corpus — a deterministic computation on an
  easier input than response-scoring; `extract_qis` already runs at p/r ≈1.0 (structured) / 1.0–0.85
  (prose). (The κ = −0.10 result was engine-vs-human on whether a *response* constitutes linkage — a
  different task; do **not** cite it as L8's detection limit.) Log whether the accountant computes the
  narrowing correctly; expected to work. The real failure mode is (d), not detection.
- **Throttle-rate rule** = if L8 fires near-blanket (e.g. at turn 0/1 on most sequences), any F2 drop is
  **uninterpretable** — STOP with that as the finding.

## 5. The choice at this pause (the conclusion is largely pre-written)

Because §0 already answers this on committed evidence, Stage 1 would, with high prior, **re-confirm the
foreclosure** — precisely the "rediscover the same finding after more spend" §2.2 warned against. What a
$0 offline trace genuinely *adds* is small but real: the explicit **single-query-equivalence number** and a
**detection trace**. Against a short runway (abstract → Esma → front matter → final read → submit), even a
$0, foreclosed L8 competes with finishing. So:

- **(A) [lean] Accept §2.2 as already answering this.** Write L8 up as a **one-paragraph foreclosure note**
  citing the committed finding (option B, single-chunk uniqueness) — zero new work, no spend. The honest
  place for the contingent variant (ii) is one line in the Ch8 governance direction ("cross-query accounting
  helps only layered on combined-query blocking").
- **(B) Run the $0 Stage-1 offline trace** for the explicit single-query-equivalence number, then the same
  note with one measured line. Choose this only if L8 is wanted as a **fourth measured negative** in the
  thesis.

## 6. Honesty guards (every stage)

L8 *bounds* multi-turn at best, never eliminates; single-query uniqueness + authorised-user-with-external-
knowledge OUT OF SCOPE; **no "solves."** Random-throttle mandatory. n=10 ⇒ ±0.30 CI, stated. Null /
foreclosed are legitimate findings. Committed numbers/corpus/L7/P7 FROZEN; L8 additive only. Every number
traced to disk; nothing post-hoc.

---

**PAUSE — Stage 0 ends here.** Verdict: **L8 = the already-rejected option B; foreclosed on committed
evidence (single-chunk uniqueness).** Scenarios CAN test narrowing (premise corrected) but that doesn't
erode the foreclosure; variant (ii) bounds only as a *contingent* layer on combined-query blocking, not as a
standalone defense; detection is expected to work (κ=−0.10 was a different task). **Recommend (A): a
one-paragraph foreclosure note, no spend** — unless you specifically want L8 as a fourth measured negative,
in which case (B) the $0 offline trace. Review before I proceed.
