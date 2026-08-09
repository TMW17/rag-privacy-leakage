# Discussion (Ch7) — reasoning SPINE

> **What this is.** The argument structure for Chapter 7, captured while the whole thesis is fresh,
> before a cold draft. Ugly bullets on purpose. Ch7 is *new synthesis with no source report* — this file
> is what it's written from. **Not** chapter prose; do not lift verbatim.
>
> **Discipline.** Every claim names its source — a committed chapter (Ch3/4/5/6) or an artifact. Synthesis
> claims that exceed measurement are flagged **[ARGUMENT]** (a discussion legitimately reasons beyond the
> data — but the line stays visible). Numbers are frozen: reference committed values, introduce none.
>
> **Number note:** F2 baseline = **0.6** (`final_metrics.json` C00000, the canonical baseline committed in
> Ch4 after the baseline-source fix), *not* 0.633 (pre-fix Phase-2 value). Canonical-baseline rule, PHASE5_PLAN §4.

---

## 1. THE METHODOLOGICAL HEADLINE (the central contribution)

- **Measuring a defended RAG system with a single instrument is wrong in a direction the analyst cannot
  see.** The rule engine reports the full stack at 0.000 (apparent near-elimination); the validated judge
  reports **17.3%**. The gap is not measurement error — it is the engine's blindness to semantic and
  cross-document leakage, *reported as protection*. [Ch5; `final_metrics.json`]
- The engine is not merely noisier — it is wrong in ONE direction: it can only *under*-count (it credits
  leaks to annotated entities on retrieved docs), so its blindness always looks like success. So the
  single-instrument error is **systematic, not random**, and **optimistic**. [Ch5; Ch4 conservative-floor]
- **Why this generalizes beyond this corpus** — the contribution is a claim about *evaluation methodology*,
  not about one number:
  - **[ARGUMENT — reasoning, not measured]** Any deterministic / annotation-bound detector is structurally
    blind to leakage that is *emergent* (paraphrase, inference, cross-document re-association) — it can only
    match what is a discrete, pre-enumerated entity. A defense that suppresses *discrete* disclosures while
    leaving *emergent* ones therefore scores as near-total under such a detector, on any corpus.
  - **[MEASURED, this corpus]** the specific 0.000-vs-0.173 gap, and that it is concentrated in the linkage
    family (engine reports F2→0, judge holds 0.6–0.7). [Ch5/Ch6; `final_metrics.json`]
  - So the *direction* of the error (single detector overstates) is an argument that travels; the
    *magnitude* (≈40% real reduction vs apparent ~100%) is this corpus. Keep that split explicit.
- Takeaway line for Ch7: *the headline finding is not "17.3% leaks" but "you cannot trust a single
  detector to tell you how much."* [ARGUMENT, grounded in Ch5]

## 2. THE FIVE RQs AS ONE STORY (the through-line — the spine of the spine)

Per-RQ facts (all committed):
- **RQ1** — undefended baseline: direct PII (F1) strongest at **0.778**, linkability (F2) **0.6**; together
  they carry essentially all strict leakage. [Ch4; `final_metrics.json` C00000]
- **RQ2** — redaction (L2) is the decisive layer; full stack **28.8%→17.3%** (~40%), knee at C01100. [Ch5; `final_metrics.json`]
- **RQ3** — judge validated at **κ=0.827** undefended (above the human ceiling) but **degrades to κ=0.306**
  on defended text; the multi-agent panel was abandoned as circular. [Ch5; `kappa_defended.json`, `final_metrics.json` RQ3]
- **RQ4** — the **insider is the hardest adversary** to defend (0.333→0.278, barely moves), because the
  insider attacks by linkage, not extraction. [Ch6; `final_metrics.json` RQ4]
- **RQ5** — residual **17.3% (L)** / **S̄ 0.371 judged (S)**; **linkage (F2) the dominant unreduced
  component** in both registers. [Ch6; `final_metrics.json`, `severity_aggregates.json`]

**THE THROUGH-LINE (state this explicitly — it is what makes Ch7 a discussion, not a recap):**

> **The leak that is hardest to *prevent* is hardest to *measure*, for the same underlying reason — and
> that is not a coincidence but the spine of the whole result.** Re-identification by linkage is
> *emergent*: a person reconstructed from individually-innocuous attributes scattered across documents,
> not a discrete entity sitting in one record. Because it is emergent, (i) **no redaction layer can remove
> it** — there is no discrete span to redact (RQ2/RQ5: F2 0.6→0.6, unreduced); (ii) **no deterministic
> detector can even see it** — there is no annotated entity to match (RQ3: engine κ=−0.10 on defended,
> reports F2→0); (iii) **only a semantic judge can see it — and that judge is precisely the instrument
> that degrades on the redacted/refused output the defenses produce** (RQ3: κ 0.827→0.306, and the 3
> missed leaks are *all* linkage); and therefore (iv) **the hardest adversary to defend is the insider
> whose method is linkage** (RQ4). The defense gap and the measurement gap are not two problems — they are
> the *same* problem (emergent linkage) seen from two sides.**

- **[ARGUMENT]** the "emergent → hard to stop AND hard to see, same cause" causal claim is the synthesis;
  the four facts it connects are each measured (sourced above). The *connection* is the argument.
- Corollary that ties it shut: the judge's missed leaks being *linkage specifically* is why the residual
  is **corroborated, not inflated** — the human caught what the judge missed, so 17.3% is a lower bound on
  what the instruments see, not an artifact of judge over-counting. [Ch5; `kappa_defended.json`]
- Second corollary: this is why **severity tells the same story as leakage** (S̄ mirrors ASR: L2 decisive,
  L3 nothing, knee≈full) — both metrics are reading the same emergent-vs-discrete split. [Ch6; `severity_aggregates.json`]

## 3. THE JUDGE-CALIBRATION STORY AS A METHODOLOGICAL CONTRIBUTION

(Pull from `methodology_kappa_notes.md` — reference it, don't re-derive.)
- κ **0.827→0.306** on defended text; raw agreement 93%→70% (the prevalence-independent companion, reported
  first). [`kappa_defended.json`; `methodology_kappa_notes.md`]
- **Bidirectional error** (NOT a clean ceiling): 11 over-flags (refusals/redactions read as disclosures)
  + 3 misses (all re-identification by linkage). The judge errs by crying-leak-at-a-refusal more than by
  missing a real one. [`kappa_defended.json`]
- The missed leaks **corroborate** the linkage finding (item 2 corollary). [`kappa_defended.json`]
- **Honest bounding, not a point fix:** Rogan–Gladen degenerates to −34% (enriched sample breaks
  specificity); the valid estimator under verdict-stratified sampling is PPV·q + FOR·(1−q) → point 15.6%,
  band **[5.3%, 25.8%]** containing 17.3%; the recentring is 0.33 SE, unresolvable. The forbidden claim:
  never assert true leakage < 17.3% (selection bias — all judge-positives sampled). [`residual_bounds.json`]
- **Contribution to the LLM-as-judge literature:**
  - **[ARGUMENT, grounded in Ch5 §5.5]** A multi-agent arbitration panel whose members share a vendor
    lineage manufactures the *appearance* of independence without its substance — an arbitrator from the
    same family cannot, even in principle, improve on the judge it arbitrates. The honest alternative is a
    **single validated judge** (κ=0.827 vs human) **corroborated across vendors** (κ=0.843 — corroboration,
    NOT a second human validation; keep the labels rigid). The *abandonment is itself a finding*, not a
    retreat. [Ch5 §5.5]
  - **[ARGUMENT]** Generalizable lesson: judge reliability is *distribution-dependent* — a judge validated
    on raw output cannot be assumed reliable on the redacted/refused output a defense produces; defended-
    distribution recalibration should be standard practice, not an afterthought. [grounded in `kappa_defended.json`]

## 4. LIMITATIONS, WOVEN (how they interact + what they bound — not a checklist)

- **The instrument cluster:** single-provider judge (Opus 4.7) + same-vendor L2-LLM probe blind-spot +
  single-annotator validation (κ=0.827 vs the author; second annotator = future work). These *compound*:
  they are all "one vendor / one annotator" exposure on the same measurement instrument. [Ch5; Ch6 probes]
- **The corpus cluster:** synthetic, independent-attribute sampling → absolute numbers don't transfer
  (relative findings do); 84/100 re-id is an **upper bound on intrinsic uniqueness** (NOT conservative),
  distinct from the auxiliary-data argument that real risk could be higher; F8 poisoning rests on one
  scenario (no CI). [Ch3 §3.5/§3.6; `reidentification_risk.json`]
- **The utility cluster:** only 3 metrics instrumented (faithfulness/context-precision/latency); cost
  measured at the two extremes (C00000 vs C11111), so the **knee's** marginal cost is bounded but **not
  isolated** (per-config utility = future work). [Ch6; `utility_results.json`]
- **The meta-point (state it):** these are **characterized** limitations — measured, bounded, and named,
  not hidden. That is methodological *maturity*, and it is consistent with the thesis's own headline (a
  result is only as good as the instrument that measured it, and we measured our instrument). [ARGUMENT,
  grounded in §3]
- **Scope, plainly:** this is a **demonstration of a measurement methodology on a controlled corpus, not a
  certification of a deployable product.** [Ch5/Ch6 framing]

## 5. WHAT IT MEANS PRACTICALLY (bridge to deployment / Best Practices Guide)

- **Deploy the knee (C01100 = redaction + refusal), not the full stack:** it captures essentially all
  measured security (0.192 vs 0.173, within the 0.08 floor) at lower cost; the full stack is
  *defense-in-depth*, not a measured improvement. [Ch6; `final_metrics.json`]
- **Redaction (L2) is the load-bearing layer** — it is the only one that clears the noise floor; input
  filter and conversational refusal defend axes this metric barely exercises (L3 fires 3× alone, 0× behind
  redaction). Budget accordingly. [Ch6; `l3_firing.json`]
- **[ARGUMENT, residual decomposition measured]** Linkage will not yield to redaction — it needs a
  *different class* of defense (entity-resolution / directory-aware controls that redaction cannot
  provide). ~2/3 of the residual is detector-recall gap (fixable with better recognizers); ~1/3 is genuine
  linkage (needs entity resolution). [Ch6 residual decomposition]
- **Evaluate with a validated judge, not a detector alone** — and recalibrate it on the defended
  distribution. A deployment that trusts a rule engine will believe it has near-eliminated leakage when it
  has cut it ~40%. [ARGUMENT, grounded in Ch5]

## 6. FUTURE WORK (what the limitations imply — each maps to a §4 limitation)

- Second human annotator + full multi-vendor judge panel (closes the single-provider/single-annotator
  exposure). [→ §4 instrument cluster]
- Defended-distribution judge recalibration as standard method; raise κ off 0.306. [→ §3]
- Real-corpus validation beyond the single Enron probe (the judge-transfer over-flag is the open issue). [→ §4 corpus]
- Linkage / entity-resolution defenses (the residual redaction can't touch); per-attribute recognizers for
  the detector-recall 2/3. [→ §5]
- Per-configuration utility (isolate the knee's cost; the L3 marginal latency). [→ §4 utility]
- Compositional / multi-actor threats (each profile is single-actor here). [→ Ch3 limits]

---

### Through-line, in one sentence (the test of whether Ch7 is synthesis not recap)
**Re-identification by linkage is emergent, so it is simultaneously the leak redaction cannot remove, the
leak the deterministic engine cannot detect, and the leak the validated judge most degrades on — which is
why the hardest residual and the hardest measurement problem in this thesis are the same problem, seen from
two sides.**
