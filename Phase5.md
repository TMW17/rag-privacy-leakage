# Phase 5 — Thesis Write-Up Plan

> **⤷ SUPERSEDED by [`PHASE5_PLAN.md`](PHASE5_PLAN.md)** (the verified, artifact-cited expansion:
> three-way assembly-vs-new split, per-chapter artifact citations, the S-metric gap, and a full gaps
> list). This file is kept as the original sketch; edit `PHASE5_PLAN.md`, not this one.

> **Active-phase plan** (supersedes Phase2.md as the current roadmap). Plan + timeline only — no
> thesis prose is written yet. Goal: consolidate the four completed phases into the 60–80pp master's
> thesis structured around RQ1–RQ5.

## 0. Where things stand (2026-06-08)

- **Experiments are DONE.** Phase 1 (corpus, formal defs, SOTA), Phase 2 (attack framework + 28.8%
  baseline), Phase 3–4 (layered defenses + measurement) are complete and committed. The Esma 5-point
  corrections landed at `6643f54`.
- **The thesis itself is not started.** The three phase reports are the *raw material* — much prose can
  be adapted/consolidated rather than written from scratch. The job is consolidation + connective
  tissue + harmonized notation + the new defended-κ material, not a blank page.
- **AT-RISK PRIORITY (capture first):** the **two-instrument / defended-κ = 0.306 story**. It is the
  novel methodological contribution *and* the freshest in working memory (built this session). Draft its
  narrative before anything else, while the reasoning, the confusion-matrix detail, and the "why it
  corroborates linkage rather than undermining it" logic are still sharp. Source of truth on disk:
  `results/phase3_4/judge_defended_calibration/{kappa_defended.json, sample_manifest.json}` and
  §2.1/§9 of `Phase3_4_Report_Expanded.tex`.

## 1. Target structure (8 chapters, mapped to RQs + source material)

| Ch | Title | RQ | Primary source material | Status of source | Est. pp | Effort |
|----|-------|----|--------------------------|------------------|---------|--------|
| 1 | Introduction (problem, contribution, RQs) | all | PROJECT.md §1–3,9 | written-as-notes | 5–7 | synthesize last |
| 2 | State of the Art | — | `State_Of_The_Art.pdf` / phase1.tex Ch.1 (50 sources, 5 pillars) | near-final prose | 12–15 | consolidate |
| 3 | Threat Model & Formal Foundations | RQ4 | phase1.tex Ch.2–8 (L/S, 4 profiles, taxonomy, corpus, annotation, re-id, κ=0.875) | near-final prose | 12–15 | consolidate + harmonize |
| 4 | Attack Framework & Undefended Baseline | RQ1 | `Phase2_Report_Detailed.tex` (scenarios, RAG system, 28.8%) | full prose | 8–10 | adapt |
| 5 | **Layered Defenses & Two-Instrument Measurement** | RQ2, RQ3 | `Phase3_4_Report_Expanded.tex` §2–5 + defended-κ artifacts | full prose + NEW κ material | 12–15 | **write first (at-risk)** |
| 6 | Security–Utility Trade-off & Residual Risk | RQ5 | Phase3_4 §6 (Pareto knee, utility, risk matrix, linkage residual) | full prose | 8–10 | adapt |
| 7 | Discussion (methodological lesson, limitations, probes) | all | Phase3_4 §8–9 + the κ-0.306 caveat | full prose | 6–8 | synthesize |
| 8 | Conclusion & Future Work | all | all reports' conclusions | notes | 3–4 | synthesize last |
| — | Best Practices Guide (separate deliverable) | RQ5 | risk matrix + knee recommendation | not started | 15–20 (standalone) | late |

**Scaffolding (W1, before any chapter):** master `thesis.tex` + per-chapter `\input` files, unified
preamble (lift the palette/macros from phase1.tex), single `.bib`, consistent notation (L, S, κ,
profile names per `config.py` — the single source of truth).

## 2. Dependency order (what must precede what)

- Ch5 → Ch7 (the methodological lesson in Ch7 depends on Ch5's two-instrument result being written).
- Ch3 (formal defs/notation) → Ch4, Ch5, Ch6 (they use L/S/profiles; fix notation in Ch3 first or in
  the scaffolding glossary).
- Ch4 (baseline 28.8%) → Ch5/Ch6 (defenses are measured *as reductions from* the baseline).
- Ch1, Ch8 last (they synthesize the whole).
- Best Practices Guide after Ch6 (it operationalizes the knee + risk matrix).

## 3. Week-by-week schedule

> **ANCHOR ASSUMPTION — confirm/adjust:** target full-draft-to-supervisor ≈ **2026-07-20**, submission
> ≈ **2026-08-03**, ~8 weeks out. The *sequencing* below is deadline-independent; only the dates shift.
> Tell me your real defense/submission date and I re-anchor in one pass.

| Week | Dates (assumed) | Focus | Deliverable |
|------|-----------------|-------|-------------|
| W1 | Jun 09–15 | Scaffolding + **Ch5 core** (two-instrument + defended-κ narrative — the at-risk priority) | compiling skeleton; Ch5 draft |
| W2 | Jun 16–22 | Ch4 (baseline) + Ch6 start (ablation, knee, linkage residual) | Ch4 draft, Ch6 half |
| W3 | Jun 23–29 | Ch6 finish (utility/Pareto/risk matrix) + Ch3 (threat model + formal defs) | Ch6 draft, Ch3 draft |
| W4 | Jun 30–Jul 06 | Ch2 (SOTA consolidation) + Ch7 (Discussion) | Ch2 draft, Ch7 draft |
| W5 | Jul 07–13 | Ch1 (Intro) + Ch8 (Conclusion) + Best Practices Guide draft | full body draft |
| W6 | Jul 14–20 | Integration pass: figures, tables, cross-refs, notation harmonize, abstract | **complete draft → Esma** |
| W7 | Jul 21–27 | Incorporate supervisor feedback; polish prose | revised draft |
| W8 | Jul 28–Aug 03 | Final proofread, formatting, submission prep | submission + buffer |

## 4. Inputs needed from the author (to finalize this plan)

1. **Real defense/submission date** → re-anchors the calendar.
2. **Reuse policy:** may the existing phase-report prose be lifted near-verbatim into the thesis
   (consolidation), or does the program require fresh prose (rewrite)? This is the single biggest
   driver of total effort.
3. **Language/format constraints:** ESI template? page limit hard or soft? French abstract required?
4. **Best Practices Guide** — in-scope for this timeline or deferred post-defense?

## 5. First concrete action when writing starts

Build the scaffolding, then draft **Ch5** (the κ-0.306 / two-instrument story) end-to-end from the
committed artifacts — capturing the at-risk material first, as a tone/quality proof before scaling to
the consolidation chapters.
