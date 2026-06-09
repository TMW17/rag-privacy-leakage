# PHASE5_PLAN.md — Master's Thesis Writing Plan

> **Authoritative Phase-5 map. Supersedes `Phase5.md`** (the earlier sketch; a pointer has been
> added there). Plan + schedule only — **no thesis prose is written yet**.
>
> **Invariant carried from the correction phase:** every number in the thesis traces to an on-disk
> artifact; nothing typed from memory; if a step needs data that is not present, **STOP and flag it**
> rather than fabricate. This is the discipline that makes the results defensible — it does not relax
> for the write-up.

---

## 0. Where things stand

- **Experiments are DONE and committed.** Phase 1 (corpus, formal defs, SOTA), Phase 2 (attack
  framework + 28.8 % baseline), Phase 3–4 (layered defenses + two-instrument measurement). Esma's
  5 corrections landed at `6643f54`; the defended-κ uncertainty bounds at `d578fe8`.
- **The thesis itself is at zero.** The source documents are *raw material*, not chapters.
- **The honest assembly question, resolved with evidence (see §1–§3):** it is **neither** "mostly
  written, just consolidate" **nor** "raw material for ~2 chapters, the rest is new." It is a
  **three-way split** — three chapters are heavy *consolidate-and-reconcile*, two are *hybrid*
  (good source + genuinely new material), three are *new from notes* — plus a separate 15–20pp guide.
- **Capture-first priority:** the **two-instrument / defended-κ = 0.306 story** (Ch 5). It is the
  novel methodological contribution and the freshest in working memory. Draft it before anything else.

---

## 1. Source-material inventory (what actually exists on disk)

| Document | Lines | Content | Thesis target |
|---|---|---|---|
| `phase1.tex` | 4514 | **Consolidated Phase-1 deliverable**: State of the Art → LINDDUN → Formal Attacker Profiles → Formal (L,S) defs → Ground Truth → re-id → κ=0.875 | **Ch 2 + Ch 3** |
| `State_Of_The_Art.tex` | 663 | 50 sources, 5 pillars, gap analysis, annotation matrix (the standalone original `phase1.tex` Ch 1 consolidates) | Ch 2 |
| `Threat_Model.tex` | 2799 | LINDDUN, 4 profiles w/ CVSS, capability matrix, attack-objective→leakage map, taxonomy, **architecture diagrams**, threat-model limitations | Ch 3 |
| `Formal_Leakage_Definitions_and_Ground_Truth.tex` | 1401 | (L,S) defs, corpus, annotation protocol, **evaluation engine ("LLM-as-Judge placeholder")**, re-id, inter-annotator κ | Ch 3 |
| `Phase2_Report_Detailed.tex` | 792 | scenarios, RAG system, dual-ASR method, judge validation (κ=0.827), **28.8 % baseline**, per-profile/family, severity dist., hand-verified leaks | **Ch 4** |
| `Phase3_4_Report_Expanded.tex` | 865 | two-instrument measurement, defended-κ=0.306, ablation, **28.8→17.3 %**, knee C01100, Pareto, risk matrix, linkage residual, probes | **Ch 5 + Ch 6** |
| Sprint 0–4 reports, `Phase3_4_Consolidated_Report.tex` | — | per-sprint working detail | supplementary / appendix mining |

**Locked metric artifacts (the numbers that must not change):**
`results/phase3/ablation/metrics/final_metrics.json` (28.8 %, 17.3 %, knee, ablation, RQ-cited blocks) ·
`results/phase3_4/judge_defended_calibration/{kappa_defended.json, residual_bounds.json}` (κ chain,
defended bounds) · `results/baseline/baseline_metrics_augmented.json` (baseline ASR **and `mean_S`** — see §3) ·
`results/phase3/tradeoff/tradeoff_meta.json` + `results/phase3/utility/utility_results.json` (utility).

---

## 2. Chapter structure mapped to RQ1–RQ5

RQs are **founded** (set up) in one chapter and **answered** (empirically) in another — kept distinct below.

| Ch | Title | RQ founded → answered | Primary artifacts (cite) | Work type | pp | Depends on |
|----|-------|----------------------|--------------------------|-----------|----|-----------|
| 1 | Introduction (problem, contribution, RQs) | all | `PROJECT.md` §1–3,9 (notes) | **NEW** | 5–7 | everything (write last) |
| 2 | State of the Art | — (frames all) | `phase1.tex` Ch 1 / `State_Of_The_Art.tex` | **CONSOLIDATE** (+ light reconcile) | 12–15 | — |
| 3 | Threat Model & Formal Foundations | RQ4 founded; (L,S) for RQ1–RQ5 | `phase1.tex` Ch 2–8 / `Threat_Model.tex` / `Formal_Leakage…tex` | **CONSOLIDATE + RECONCILE** | 12–15 | — |
| 4 | Attack Framework & Undefended Baseline | **RQ1 answered**; RQ4 (baseline half) | `Phase2_Report_Detailed.tex`; `baseline_metrics_augmented.json` | **CONSOLIDATE** (+ de-dup) | 8–10 | Ch 3 |
| 5 | Layered Defenses & Two-Instrument Measurement | **RQ2, RQ3 answered** | `Phase3_4_Report_Expanded.tex` §2–5; `final_metrics.json`; `kappa_defended.json`; `residual_bounds.json` | **HYBRID** (source + NEW κ) | 12–15 | Ch 3, Ch 4 |
| 6 | Security–Utility Trade-off & Residual Risk | **RQ5 answered**; RQ4 (per-profile defense) | `Phase3_4_Report_Expanded.tex` §6; `tradeoff_meta.json`; `utility_results.json`; risk matrix | **HYBRID** (see S-gap §3) | 8–10 | Ch 4, Ch 5 |
| 7 | Discussion (methodological lesson, limits, probes) | all (synthesis) | `Phase3_4` §8–9; `Phase2` discussion; §3/§4 here | **NEW** (synthesis) | 6–8 | Ch 5, Ch 6 |
| 8 | Conclusion & Future Work | all | all reports' conclusions (notes) | **NEW** | 3–4 | all (write last) |
| — | Best Practices Guide (separate 15–20pp deliverable) | RQ5 | risk matrix + knee (C01100) recommendation | **NEW** standalone | 15–20 | Ch 6 |

**Total thesis body ≈ 66–84pp** (fits the 60–80 envelope; trim in the Ch 2/3 consolidation if long).

### Per-chapter notes (work type justified, not asserted)

- **Ch 1 — NEW.** Only exists as `PROJECT.md` notes. Must state the convergence contribution, motivate
  the five RQs as one linked argument, and preview the honest findings (incl. the two-instrument lesson).
  Write last, once the body fixes the actual claims.
- **Ch 2 — CONSOLIDATE.** `phase1.tex` Ch 1 is near-final academic prose. Light reconcile only: the
  "Positioning of This Thesis" subsection promises capabilities (multi-agent judge) that reality revised
  — one or two sentences must point forward to what was *actually* built (Ch 5), not the plan.
- **Ch 3 — CONSOLIDATE + RECONCILE.** Profiles, LINDDUN, CVSS, taxonomy, (L,S) defs, corpus, re-id, κ=0.875
  are near-final. **But `phase1.tex`/`Formal_Leakage…tex` were written pre-experiment and carry
  forward-promises the results overturned** — they must be reconciled, not lifted verbatim: (a) the
  "LLM-as-Judge **placeholder**" must point to the real validated instrument in Ch 5; (b) the **(L,S)
  definitions stay, but S's fate must be honestly flagged** (§3); (c) the re-id framing must adopt the
  corrected reading (§4). Failing to reconcile = importing falsified claims into the thesis.
- **Ch 4 — CONSOLIDATE.** `Phase2_Report_Detailed.tex` is full prose. De-duplicate its "Threat Model
  Recap" (now Ch 3) and harmonize κ notation with Ch 5. Baseline 28.8 % is the reference all defenses
  reduce from — fix it here before Ch 5/6.
- **Ch 5 — HYBRID (write first).** §2–5 of the expanded report are strong source, but the **defended-κ =
  0.306 two-instrument story + residual bounds [5.3 %, 25.8 %]** are this session's new material and the
  novel contribution. **RQ3 must be reframed** (see §4.3): the originally-planned *multi-agent* judge was
  abandoned as circular; the honest answer is a single validated judge, cross-vendor corroborated.
- **Ch 6 — HYBRID.** Pareto knee (C01100), ablation, linkage residual are source-backed. **RQ5's defined
  answer (S̄_residual) is the S-gap (§3)** — resolve before drafting. Utility = **faithfulness +
  context-precision + latency only** (artifacts confirm these three; BLEU/ROUGE/relevance/completeness
  from the `PROJECT.md` plan have no artifact — do not claim them).
- **Ch 7 — NEW.** The methodological lesson (two instruments disagree; the judge over-flags refusals yet
  corroborates linkage), the plan-vs-reality reconciliations, the consolidated limitations, and the
  exploratory probes (Enron, L2-LLM) — kept explicitly EXPLORATORY, never headline. Synthesis, not assembly.
- **Ch 8 — NEW.** Notes only.

---

## 3. ⚠ The S-metric gap — most viva-dangerous; decide before Ch 6

**Finding (from disk):** the formal contribution is the **(L, S)** pair. `PROJECT.md` §5 defines
**RQ2 = ΔS** (`S_baseline − S_defended`) and **RQ5 = S̄_residual** (mean S under the full stack). On disk:

- `baseline_metrics_augmented.json` computes **`mean_S_overall` / `mean_S_by_profile`** — so S̄ exists **at the baseline only**.
- `final_metrics.json` (the entire defense-ablation result set: per-cell, deltas, RQ1/RQ2/RQ4/RQ3 blocks)
  has **no severity keys whatsoever** — every defended number is **ASR (mean L)**.
- Therefore **ΔS and S̄_residual were never computed for the defended configurations.** S survives at
  baseline and in the entity-level risk matrix, but the S-half of the formal contribution is **absent
  from exactly the results that answer RQ2 and RQ5.**

**Why it matters:** an examiner reads "my formal contribution is (L,S)" then "my defense results report
only mean L." That is the single most exposed seam in the thesis.

**Two honest resolutions (pick one early):**
1. **Cheap new analysis, NO model calls (preferred if data present).** The per-record judged severities
   appear to exist (`severity_judge` in the judge artifacts; e.g. `kappa_defended.json` per-record;
   baseline already aggregates `mean_S`). Aggregating ΔS and S̄_residual across the defended cells is then
   a pure re-computation. **Verify first** that the defended-cell logs (`experiment_logs/`, the ablation
   judged outputs) carry per-record severity for *all* cells; if they do not, **STOP** — do not back-fill.
2. **Explicit reframe.** State that L-based ASR (dual-instrument) is the operational headline and that S is
   retained for entity-level risk stratification (the risk matrix), with RQ2/RQ5 answered in ASR terms and
   the (L,S) definition presented as the measurement *framework* rather than both being headline metrics.

**✅ VERIFIED (this session, no recomputation, no model calls) — Exit 1 is viable; data is on disk:**
- **Engine `S`: present per-record for every defended cell** — the `S` field in
  `results/phase3/ablation/engine/{C00000_anchor,C10000,C01000,C00100,C01100,C11111}.jsonl`
  (non-trivial, e.g. C11111 range [0.0, 14.4]; n=89/cell). Engine ΔS and S̄_residual are an **immediate
  aggregation today.**
- **Judge `severity_judge`: present** for all 227 unique judged responses in
  `results/phase3/ablation/judged/judge_cache.jsonl` — **but not naïvely joinable to cells** (engine
  `response_hash` is a 16-char hash ≠ the judge `_judge_key` sha256; 0/89 join directly). The judged
  severities are recoverable via the **existing** `scripts/phase3/judge_ablation.py` cell→key logic
  (the same path that produced `kappa_defended.json`), still **no model calls**.
- **Bottom line:** the severities were recorded, just never aggregated into `final_metrics.json`. Prefer
  **Exit 1**. Engine ΔS/S̄ is trivial; judged ΔS/S̄ is a modest scripting task (reuse the join) — no
  re-judging, no back-filling. Exit 2 remains the clean fallback if the judged join proves fragile.

Either way the plan must surface this in Ch 3 (when S is defined) and resolve it in Ch 6.

---

## 4. Gaps no current artifact covers (genuinely new writing/analysis)

> **⚓ CANONICAL DECISION (settled in Ch4, binds every chapter that says "reduction from baseline"):**
> **the canonical source for ALL attack-success rates is `final_metrics.json`, cell C00000** (the
> ablation's undefended cell — the same baseline Ch5/Ch6 reductions are measured against), reported
> family-by-family. The Phase-2 `baseline_metrics_augmented.json` artifact is used ONLY for what
> `final_metrics` lacks — severity (`mean_S`), the engine–judge cross-tab, retrieval precision, the
> hand-verified audit, the Phase-2 calibration κ — always **labelled as Phase-2**. Do NOT mix the two
> sources for the same ASR. (Ch4↔Ch5 mismatch this resolved: F2 0.633→0.600, F5 0.067→0.200, F6
> 0.111→0.000, engine 18.6%→19.2%; headline 28.8% and F1-dominance invariant.) Ch6 must use C00000 too.


1. **The S-metric gap** — see §3. Highest priority; may need a no-model-call ΔS/S̄ re-computation.
2. **No unified bibliography.** There is **no `.bib` file anywhere.** ~50 SOTA sources are not yet in a
   central BibTeX database. Building it is W-8 scaffolding work; until then no chapter can `\cite{}`.
3. **The abandoned multi-agent panel ⇒ RQ3 reframe.** `PROJECT.md` §8 and `Formal_Leakage…tex` describe a
   three-agent Attacker–Defender–Arbitrator loop; the expanded report (§2.1) records it was abandoned as
   **circular** (arbitrator same vendor as judge). RQ3 as written ("multi-agent … bounded false-positive
   rate") is **partly falsified** — defended κ=0.306 directly complicates "bounded FPR." The thesis must
   narrate the deviation honestly and re-answer RQ3 around a single validated judge. No artifact does this
   as a clean narrative; it is scattered across docs and must be written.
4. **Re-identification: conservative vs upper-bound contradiction.** `PROJECT.md` §7 calls the synthetic
   re-id figure **"conservative."** The corrected report (§9) calls 84/100 **"nearer an upper bound."**
   These are opposite. The corrected reading is the statistically right one and must be carried — *precisely*:
   independent attribute sampling **inflates** distinct quasi-identifier combinations, so **84/100 is an
   upper bound on intrinsic corpus uniqueness** (correlated real data → fewer combinations → less unique);
   the *separate* point that real-world risk could be higher comes from **attacker auxiliary information**,
   not from the corpus. `PROJECT.md` §7 conflates the two; the thesis must split them.
   **Terminology-collision watch (Ch3/Ch6):** Ch5 §5.1 correctly calls the *engine baseline* a
   "conservative floor" (the engine under-counts, missing non-retrieved leaks) — a **different axis** from
   the re-id "upper bound" (corpus uniqueness). "Floor" and "upper bound" will sit in the same thesis;
   keep them crisply distinct (leakage-detection undercount vs. attribute-uniqueness overcount) so they
   never read as a contradiction.
   **⚠ INTEGRATION-PASS FIX — source-prose transcription slips in `Formal_Leakage…tex` (and its
   `phase1.tex` copy):** the re-id prose says worst-case **85%** (dept+salary+age+office) and l-diversity
   **41/60 (68%)**, but the COMPUTED artifact `results/reidentification_risk.json` (canonical, and matching
   PROJECT.md + report §9) says **84/100** (dept+medical+age+office) and **40/63 (63%)**. Ch3 uses the
   artifact values (84, 40/63). Fix the source `.tex` prose to match the artifact during integration — or
   be ready to explain at the viva why Ch3 says 84 and an earlier doc says 85 ("artifact is canonical;
   earlier prose had a transcription slip, since corrected"). Don't let this note evaporate.
5. **Utility scope narrower than planned.** Claim only faithfulness / context-precision / latency (§2, Ch 6).
6. **The "LLM-as-Judge placeholder" → real instrument.** `Formal_Leakage…tex` presents the engine's judge as
   a placeholder; Ch 5 must connect it forward to the validated instrument.
7. **Front matter & apparatus (all new):** title page (ESI template), French + English abstract (confirm
   requirement), acronym list (RAG, LINDDUN, CVSS, GDPR, ASR, PII, κ…), notation/glossary table (L, S,
   profiles per `config.py` as single source of truth), ToC, list of figures/tables.
8. **Figures.** Architecture diagrams in `Threat_Model.tex` are likely verbatim/ASCII (≈135 lines each) —
   a thesis probably needs publication-quality redraws (TikZ or vector). Verify and budget.
9. **Best Practices Guide (15–20pp).** Not started; standalone deliverable per `PROJECT.md` §11.

---

## 5. Dependency order

```
scaffolding (.tex skeleton + unified .bib + notation glossary)   ← must precede all
        │
Ch3 (L,S, profiles, taxonomy)  →  Ch4 (baseline 28.8%)  →  Ch5 (defenses, κ)  →  Ch6 (utility, residual)
        │                                                         │
        └────────────── S-gap decision (§3) ─────────────────────┘  →  resolved in Ch6
                                                                  │
Ch5 + Ch6  →  Ch7 (Discussion)  ;  Ch2 (SOTA) parallel/independent  ;  Ch1 + Ch8 last  ;  BPG after Ch6
```

---

## 6. Week-by-week schedule (deadline-relative; dates are assumptions to confirm)

> **CONFIRMED (this session): submission = 2026-06-29** — 20 days from Day 1 (2026-06-09). Hard gate:
> **complete draft → Esma by ~Day 14 (Jun 22)**, with **Days 15–20 (Jun 23–29) reserved** for her
> feedback + revision + ESI formatting. Compressed by design; feasible only because the **reuse policy is
> confirmed** (lift *and elevate* own phase-report prose — Esma). Dependency order unchanged (§5).
> **Best Practices Guide DEFERRED to post-defense** (15–20 standalone pp is unrealistic inside 20 days) —
> pending your override. Principle: front-load the at-risk **Ch 5** and the new-synthesis **Ch 7 / Ch 1**;
> the consolidate chapters (2/3/4) lift-and-elevate fast and absorb any slip.

| Days | Dates | Focus | Deliverable |
|---|---|---|---|
| **D1–3** | Jun 09–11 | Scaffolding (`thesis.tex` + `\input` skeleton, `.bib` seed, notation glossary) · **Ch 5 (at-risk, first)** · S-gap resolved (Exit 1, §3) | skeleton compiles; **Ch 5 draft** |
| **D4–5** | Jun 12–13 | Ch 4 (baseline 28.8 %; lift-and-elevate `Phase2_Report_Detailed.tex`) | Ch 4 draft |
| **D6–8** | Jun 14–16 | Ch 6 (ablation recap, knee C01100, utility, residual; **ΔS/S̄ via Exit 1**) · Ch 3 start | Ch 6 draft; Ch 3 half |
| **D9–10** | Jun 17–18 | Ch 3 finish (threat model + formal defs, **reconciled — not lifted blind**) | Ch 3 draft |
| **D11–12** | Jun 19–20 | Ch 2 (SOTA consolidate) · Ch 7 (Discussion — synthesis) | Ch 2 draft; Ch 7 draft |
| **D13** | Jun 21 | Ch 1 (Intro) · Ch 8 (Conclusion) | Ch 1, Ch 8 draft |
| **D14** | Jun 22 | Integration: figures (+ diagram redraws), tables, cross-refs, notation harmonise, abstract(s) | **COMPLETE DRAFT → ESMA (HARD GATE)** |
| **D15–18** | Jun 23–26 | Incorporate Esma feedback; polish prose | revised draft |
| **D19–20** | Jun 27–29 | Final proofread, ESI formatting, submission | **submission** |

**Deferred (post-defense, pending override):** Best Practices Guide (15–20pp standalone).
**Slack reality:** there is none in D1–14. If a chapter slips, the consolidate chapters (2/3/4) absorb it
(stable source); Ch 5/6/7 cannot (at-risk / new). D14 is immovable — Esma's turnaround owns D15–20.

---

## 7. Inputs (status)

1. ✅ **Deposit date — CONFIRMED: 2026-06-29** (20 days; §6 re-anchored).
2. ✅ **Reuse policy — CONFIRMED:** may lift own phase-report prose, **but must elevate** it (more
   professional, better-structured, more polished academic register). "More professional = clearer, NOT
   stronger": no inflated results, no softened limitations (the honest framings survive verbatim in
   substance). → §2 "consolidate" chapters are lift-and-elevate.
3. ✅ **Best Practices Guide — DEFERRED** to post-defense (pending override).
4. ⬜ **ESI format constraints — OPEN:** official template? hard/soft page limit? **French abstract
   required?** (drives the front-matter gap, §4.7). Confirm before the D14 integration pass.

---

## 8. First concrete action when writing starts

Build the scaffolding (skeleton + `.bib` + notation glossary), **resolve the S-gap (§3)**, then draft
**Ch 5** (the defended-κ / two-instrument story) end-to-end from the committed artifacts — capturing the
at-risk material first, as a tone/quality proof before scaling to the consolidate chapters.

**STATUS — Ch 5 DONE:** drafted at `results/phase3_4/report/thesis/ch5_defenses_measurement.tex`
(9pp standalone, compiles clean; reviewed + corrected). The pattern that made it work: a captured
**reasoning spine** (`methodology_kappa_notes.md`) written *before* the prose.

**Carry that pattern forward — it is the make-or-break for the next 19 days.** The consolidate chapters
(2/3/4) already have their spine (the committed phase reports). But **Ch 7 (Discussion) and Ch 1 (Intro)
are new synthesis with no spine** — capture their argument in a notes file *before* drafting, or they
become blank-page panics in the final week. Do not draft Ch 7 / Ch 1 cold.
