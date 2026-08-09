# Introduction (Ch1) — spine, matched to the finished body

> **What this is.** The framing spine for Chapter 1, captured AFTER the body (Ch2–7) is written,
> so the intro promises only what the body delivers. Lighter than the Ch7 spine. Every framing point
> names the committed chapter that delivers it; anything Ch2–7 do NOT deliver does NOT go in the intro.
>
> **THE governing rule:** promises = deliveries, claim for claim. The Ch1 risk is OVER-claiming (the
> inverse of every other chapter). If a point here isn't delivered by a committed chapter, cut it.

---

## 1. THE PROBLEM (grounded, not hyped)
- Enterprise RAG makes a sensitive corpus (HR, medical, memos, system configs) conversationally
  accessible; the retriever and the model are built to be *helpful*, not *minimally informative*, and
  neither knows who is authorized to see what. [delivered: Ch3 threat model; Ch4 baseline]
- The stakes are privacy/GDPR: unauthorized disclosure of personal data. [Ch3 §formal/thresholds]
- Why hard: the retriever becomes an attacker-controllable channel (indirect injection, poisoning), and
  the worst leak — re-identification by linkage — is *emergent* (assembled from innocuous attributes),
  not a discrete field a filter can catch. [Ch2 SOTA (greshake2023ipi, carlini2021extracting); Ch7 through-line]
- Keep it grounded; cite SOTA for motivation, don't dramatize.

## 2. THE GAP (from Ch2's synthesis)
- Five active subfields — RAG attacks, PII leakage, prompt-injection taxonomies, defenses,
  LLM-as-judge — each mature within its bounds; NONE covers their intersection (RAG attacks × PII
  privacy metrics × formal threat taxonomy × layered defenses × automated adjudication). [→ Ch2 §synthesis, G1–G5 matrix]

## 3. THE CONTRIBUTION (stated HONESTLY — the anti-over-claim core of the framing)
- **Convergence, NOT invention.** Couples five capabilities no prior RAG work combined: the formal
  (L,S) metric pair (Ch3), a profile-dependent evaluation engine over 3 live attacker archetypes (Ch3),
  a systematic 8-family adversarial campaign (Ch4), layered defenses quantified with ΔS (Ch5/Ch6), and a
  validated LLM judge (Ch5). [→ Ch2 positioning + Ch3–6]
- **The methodological headline (sharpest contribution):** measuring a *defended* RAG system with a
  single instrument is wrong in a direction the analyst cannot see — the rule engine reports
  near-elimination, the validated judge shows 17.3%. **This is the thesis's central ARGUMENT** (the
  *direction* generalizes; the *magnitude* is this corpus). Frame as argument, not proven universal. [→ Ch5, Ch7 §1]
- **Explicit NON-claims (flag so the draft can't drift):** NOT a new attack technique; NOT a new defense
  mechanism (the layers are existing tools — Presidio, NeMo, etc.); NOT a deployable/certified product.

## 4. THE FIVE RQs (as the body answers them — not as PROJECT.md planned them)
- RQ1 — what leakage occurs in an undefended baseline, and which families dominate? [→ Ch4: F1 direct-PII 0.778 strongest, F2 linkability; 28.8%]
- RQ2 — how much do existing defenses reduce it? [→ Ch5: 28.8→17.3, redaction the decisive layer]
- RQ3 — can an LLM judge detect leakage reliably, with bounded false positives? [→ Ch5: validated κ=0.827 undefended, degrades to 0.306 defended; single validated judge — the multi-agent panel was abandoned as circular]
- RQ4 — which adversary is hardest, and which defense works per profile? [→ Ch6: insider hardest, because linkage]
- RQ5 — what residual risk remains after the full stack, and at what utility cost? [→ Ch6: 17.3% / S̄ 0.371; knee C01100; F2 the unreduced residual]
- NOTE: RQ3 is answered in its honest, single-judge form (reconciled in Ch2/Ch5) — the intro must NOT
  promise the multi-agent Arbitrator the original plan envisaged.

## 5. HONEST FINDINGS PREVIEW (one paragraph — load-bearing, the anti-hype core)
- 28.8% → 17.3%: a reduction of **≈40%, NOT near-elimination**. [Ch5]
- Re-identification by **linkage (F2) is the dominant UNREDUCED residual** — redaction defeats
  extraction, not linkage. [Ch5/Ch6]
- **Judge-calibration lesson:** validated on undefended text (κ=0.827, above the human ceiling) but
  degrades on defended text (κ=0.306); the headline is therefore **bounded, not airtight** — a wide
  honest interval that contains 17.3%, and the "true rate < 17.3%" reading is explicitly refused. [Ch5]
- **"A demonstration of a measurement methodology on a controlled corpus, not a certification of a
  deployable product."** [Ch5/Ch6/Ch7]

## 6. THESIS STRUCTURE (chapter map)
- Ch2 State of the Art → Ch3 Threat Model & Formal Foundations → Ch4 Attack Framework & Baseline (RQ1)
  → Ch5 Layered Defenses & Two-Instrument Measurement (RQ2, RQ3) → Ch6 Security–Utility Trade-off &
  Residual Risk (RQ5, RQ4) → Ch7 Discussion → Ch8 Conclusion.

---

### Promises-vs-deliveries discipline (the one check before the draft ships)
Every contribution/finding the intro states must trace to a committed chapter above. Specifically the
intro may claim: convergence (Ch2–6), the two-instrument methodological argument (Ch5/Ch7), 17.3%/≈40%
(Ch5), linkage residual (Ch5/Ch6), the κ-degradation lesson (Ch5). It may NOT claim: elimination, a
novel attack/defense, a deployable product, or a multi-agent Arbitrator. If the draft says
"solve/eliminate/novel defense," pull it back to what's measured.
