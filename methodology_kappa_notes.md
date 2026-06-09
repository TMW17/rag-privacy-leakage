# Methodology notes — the two-instrument / defended-κ = 0.306 story

> **Purpose.** Capture the *reasoning* behind the judge-calibration result while it is fresh. The
> numbers are safe in committed JSON; the argument lives only in working memory and decays fast. This
> file seeds the Methodology chapter (Ch 5) and viva prep. Ugly bullets are fine — completeness first.
>
> **Sources (every number below traces here):**
> `results/phase3_4/judge_defended_calibration/kappa_defended.json` (confusion matrix, κ chain,
> over-/under-flag counts, raw agreement) · `results/phase3_4/judge_defended_calibration/residual_bounds.json`
> (Rogan–Gladen degeneracy, decomposition, the [5.3 %, 25.8 %] band) · `Phase3_4_Report_Expanded.tex`
> §2.1 (narrative) and §9 (limitations). Defended numbers are over the C01100+C11111 calibration sample,
> n = 46; the residual headline q = 0.173 is C11111 judged-strict (`final_metrics.json`).

---

## 1. The two instruments, and why they disagree

- **Instrument A — the rule engine.** Deterministic. Detects PII by matching the model's response
  against the 2,190-entity ground-truth annotations (regex / NER / keyword-context / etc.), applies the
  profile authorization threshold, scores L and S. It sees *what is annotated and syntactically present*.
- **Instrument B — the LLM-as-Judge.** Claude Opus 4.7 (exact prompt/temp provenance in
  `kappa_defended.json`; note the judge runs at API-default temperature ~1, so it carries its own
  non-determinism — part of the noise floor). It reads the response *semantically* — paraphrase,
  inference, cross-turn linkage — things no annotation match can catch.
- **Why they disagree:** they are answering the same question with different sensory organs. The engine
  is blind to semantic/linkage leakage (a re-identification assembled across turns matches no single
  annotation). The judge sees that, but it also "sees" leakage in polite refusals and redacted residue
  where none occurred. On *undefended* raw model output the two largely agree (disclosures are explicit).
  On *defended* output — redacted, refused, degraded — they diverge sharply and in **opposite directions**.

## 2. Why the disagreement is the methodological HEADLINE, not a footnote

- Most RAG-leakage work reports one ASR from one instrument and moves on. The novel contribution here is
  the demonstration that **the measured leakage rate is instrument-dependent, and the two natural
  instruments disagree systematically on exactly the output defenses produce.**
- It reframes the question from *"what is the leakage rate?"* to *"leakage rate as seen by which
  instrument, validated how, and erring in which direction?"* — which is the honest way to measure a
  defended system.
- Concretely: on defended text the **engine is worse than useless** (κ = −0.0952 vs human — below
  chance), because the leaks that survive defenses are precisely the semantic/linkage ones it cannot see.
  So the judge *must* be primary on defended output — but the judge itself degrades there. The whole
  chapter is about navigating that honestly, not hiding it.

## 3. Why κ collapses 0.827 → 0.306 on *defended* text specifically

- Judge-vs-human κ: **0.827 undefended → 0.306 defended** (Δ = −0.521).
- Two compounding reasons:
  1. **Different reading task.** Defended output is refusals, redactions, and degraded answers. The judge
     was validated on raw disclosures (easy, explicit). On defended text the signal is subtle (residue,
     cross-turn linkage) and the judge's failure modes activate — it reads refusals as leaks.
  2. **κ is prevalence-sensitive.** The judge-positive base rate differs between the two calibration
     samples (**13/46 undefended vs 18/46 defended**). κ is chance-corrected, so a shift in how often a
     "leak" occurs moves κ even if raw accuracy were stable. This is why raw agreement is reported
     alongside (see §6) — it isolates the *real* drop from the prevalence artifact.

## 4. The bidirectional error (the core confusion matrix)

Judge vs human, defended, n = 46: **TP = 7, FP = 11, FN = 3, TN = 25.**

- **Over-flag (false alarms): 11 of 18 judge-positives.** Of the 18 responses the judge flagged as leaks,
  the human confirmed only **7** (PPV = 7/18 = **0.389**); the other **11** were false alarms
  (FDR = 11/18 = **0.611**) — almost all **polite refusals or redacted non-answers the judge read as
  disclosures**.
- **Under-detect (misses): 3 of 10 human-confirmed leaks.** The human identified 10 real leaks; the judge
  caught 7 and **missed 3** (sensitivity = 7/10 = **0.70**, FNR = **0.30**). The 3 misses (rows 36/38/39
  in `kappa_defended.json`) are **all P1-LINK re-identification by linkage** — age-bracket re-id assembled
  across turns.
- **Direction summary:** the judge errs by **crying leak at a refusal more often than by missing a real
  one**. Over-flagging dominates; under-detection is rarer but concentrated and consequential (§5).

## 5. Why the missed leaks CORROBORATE the central claim (do not undermine it)

- The thesis's central residual finding is that **F2 linkability — cross-document / cross-turn
  re-identification — is the principal *unreduced* leak that survives the full defense stack** (judged
  residual ≈ 0.60–0.70 across configs, within the noise floor → unreduced, not config-worse).
- The judge missed **exactly** that kind of leak (re-id by linkage), and the **human caught them**. Three
  consequences, all reinforcing:
  1. The surviving residual is **corroborated by human judgment**, not an artifact of the judge inventing
     leaks. The thing the thesis treats as its central finding is the thing a human confirms.
  2. The judge **under-counts** linkage → **17.3 % is a lower bound on what the instruments can see, not
     an upper one.** The headline is conservative *in this direction*, not inflated.
  3. Linkage is the **hardest leak for both automated instruments** (engine blind to it; judge misses
     some) — which *is* the point: defenses and detectors both struggle with linkability, so it is the
     residual that matters. The misses are evidence for the thesis, framed correctly.

## 6. Why I led with RAW AGREEMENT (93 % → 70 %) as κ's companion

- Raw agreement: **undefended 43/46 = 93.5 % → defended 32/46 = 69.6 %.**
- κ is chance-corrected **and prevalence-sensitive**; the two samples differ in leak prevalence (13/46 vs
  18/46), so a κ drop **conflates "the judge got worse" with "the base rate shifted."**
- Raw agreement is **prevalence-independent** → directly comparable across the two samples. It answers
  "how much did agreement *actually* fall" cleanly (≈ 23 points), while κ answers "how much beyond chance."
- **Report both; neither alone is honest.** Raw agreement is the fairer cross-sample headline; κ is the
  chance-corrected companion. (This is stated explicitly in `kappa_defended.json` → `raw_agreement.note`.)

## 7. The Rogan–Gladen degeneracy, and the estimator that replaces it

- **Naïve instinct:** correct the apparent rate q = 0.173 with the judge's sensitivity/specificity via
  the textbook Rogan–Gladen formula: `p = (q + spec − 1) / (sens + spec − 1)`.
- **It returns −0.336 (≈ −34 %)** — a nonsensical negative leakage rate. *Do not report this as a number;
  report it as the diagnostic that the method is wrong here.*
- **Why it degenerates:** the calibration sample was **enriched for judge-positives** — it took **ALL 18**
  judge-flagged responses in the pool but only a **fraction (28 of 125)** of judge-negatives. So the
  **sample specificity (25/36 = 0.694) is biased LOW**: it captured every false positive but only some
  true negatives. The sample false-positive rate (0.306) therefore *exceeds* the apparent rate (0.173),
  which forces R–G negative. **Sensitivity/specificity do not transfer from a sample stratified on the
  test's own verdict.**
- **The valid estimator under verdict-stratified sampling** uses the quantities that *do* survive that
  sampling — PPV (estimated on the census of all 18 positives) and the false-omission rate FOR:
  ```
  p = PPV·q + FOR·(1−q)
    = 0.389·0.173 + 0.107·0.827
    = 0.067            +  0.089
    = 0.156
  ```
  - First term = real leaks **among judge-positives** (the over-flag correction, pulls **down** toward 6.7 %).
  - Second term = missed leaks **among the large judge-negative mass** (the under-detect correction, adds
    **~9 points back up**).
  - **The two corrections nearly cancel.** That is the whole point: over-flagging alone looks like it
    should slash the rate to ~7 %, but the missed-leak mass restores it to ~15.6 %.

## 8. The one claim I must NEVER make: "true leakage < 17.3 %"

- The point estimate (15.6 %) sits *below* 17.3 %, and it is tempting to say "so the real rate is lower."
  **This is forbidden — it is a selection-bias trap.**
- The sample took **all** judge-positives (enriched), so the over-flagging (11 false alarms) is highly
  visible while the missed leaks among the vast unflagged population are easy to under-count (only 28 of
  125 negatives were checked; 3 misses there project to ~13 in the full pool). The "it's really ~7 %"
  move uses only the visible over-flag correction and ignores the misses.
- Plus: the recentring is **1.7 pp = 0.33 SE** — statistically unresolvable in direction (§9). And §5/§9:
  both instruments miss cross-document leakage, so the truth is a lower bound, not an upper one.
- **Correct statement:** *"Propagating the judge's two error rates recenters the residual by less than
  one standard error; the corrected interval is wide and contains 17.3 %. The data cannot place the true
  residual below 17.3 %."*

## 9. The honest bound [5.3 %, 25.8 %] — wide on purpose

- Decomposition point p = 0.156; propagated binomial SE = 0.052 (from SE(PPV) = 0.115, SE(FOR) = 0.058).
- ≈95 % interval = **[0.053, 0.258] = [5.3 %, 25.8 %]**, which **contains 0.173**. Δ(17.3 − 15.6) = 1.7 pp
  = **0.33 SE** → unresolvable in direction.
- **Wide by construction:** it rests on 18 flagged, 10 human-confirmed, and **only 3 missed** leaks — 3
  data points. Normal approximation with 3 events is rough; treat the band as "at least this wide."
- **Sensitivity check:** all 3 misses fall in the under-sampled `redacted_residue` stratum; weighting
  strata back to population sizes gives FOR = 0.118 → point **16.5 %**, i.e. *closer* to 17.3 % — which
  reinforces "cannot place it below."
- **One-line takeaway for the viva:** *calibration error WIDENS the interval around the residual; it does
  not MOVE the number.* 17.3 % stays the figure of record; the κ=0.306 work bounds its uncertainty, it
  does not overturn it.

---

### Loose ends to resolve when this becomes Ch 5 prose
- Reconcile with the Phase-1 "LLM-as-Judge **placeholder**" framing (`Formal_Leakage…tex`): connect the
  placeholder forward to this validated instrument.
- RQ3 reframe: the originally-planned multi-agent panel was abandoned as **circular** (arbitrator same
  vendor as judge); the honest answer is a **single validated judge, cross-vendor corroborated**
  (κ=0.843 corroboration ≠ κ=0.827 human validation — keep these distinct).
- Keep engine framed as the **lower-bound** instrument throughout (κ=−0.10 defended = below chance).
