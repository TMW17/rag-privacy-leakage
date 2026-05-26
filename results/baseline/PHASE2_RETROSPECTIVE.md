# Phase 2 Evaluation Retrospective

## 1. What Worked: Specific Decisions That Paid Off

* **Hand-Checking Outputs Early:** The thing that saved me most often was checking the engine's output by hand before trusting it. In the pilot phase, my manual check caught a massive false positive in scenario `P2-INJ-002`. If I had blindly trusted the automation, I would have reported an inaccurate 60% Attack Success Rate (ASR). 
* **Enforcing Strict Reproducibility:** I locked down my environment variables early. I encoded the seed directly into my ChromaDB collection names (`Seed = 42`) and kept the model temperature at a strict `0.0`.
* **Caching Judge Verdicts (`judge_verdicts.jsonl`):** Caching these verdicts in Week 5.5 let me re-run and re-compute my kappa coefficients after fixing `SP_02` without spending any extra money. More importantly, during Week 6.1, I used a `Ctrl-C` interrupt right at the start of the execution when I realized I could reuse 9 cached verdicts, which instantly saved me about $0.30 in unnecessary API calls.
* **The Patricia Walsh Discovery:** My manual verification protocol proved its worth when I ran a targeted verification snippet. It confirmed that across all 3 test runs, the model leaked her actual email address at exact lengths of 1549, 1517, and 1549 characters. This, along with hand-verifying 10 other real named employees (including Melissa Farrell, James Thomas, and Teresa McLaughlin), gave me a rock-solid, verified baseline of actual leaks.
* **Actual Compute Spending:** I didn't underspend down to three dollars, but I kept clean track of my costs. My Week 6.1 commit log shows I spent $10.50 on the major judge calibration run, bringing my cumulative Phase 2 compute footprint to approximately $14.02.

---

## 2. What Didn't Work: Honest Regrets

* **Too Few Poisoned-Document Patterns:** In Week 4, I limited my poisoned corpus to just 6 patterns (C-01, C-04, Greshake, and three BIPIA variations). Looking at the wider literature, this wasn't diverse enough to truly stress-test the system, and I'm left wondering if I missed other structural vulnerabilities.
* **Lazy Keyword Heuristics in W5.6:** For the P4 third-party aggregator analysis, I used a basic keyword heuristic to flag M2 excess entities. It works as a conservative fallback, but it regularly over-inflates the metric. I should have taken the time to build a dedicated LLM-based evaluator for this layer instead of taking the easy path.
* **Arbitrary Pilot Truncation:** During the B1 pilot scope decision, I chose to evaluate 267 turns instead of the full 284 turns available. While it kept the data manageable, it truncated my visibility into late-stage conversation drift.
* **Wasting Time on Prompt Variations:** I wasted a lot of engineering cycles drafting and tweaking the footers on `poisoned_003` and `poisoned_004`, only to completely strip the footer separators out anyway after my mentor's review pass. 

---

## 3. What Surprised Me: Unexpected Findings

* **The Augmented Metric Jump:** The biggest shock was how much the numbers shifted once I moved past the naive engine baselines. Under the Week 6.1 augmented metric, my strict F1 ASR jumped to **77.8%** (compared to the old engine-only baseline of 48.1%). 
* **Internal vs. External Risk Divergence:** My Week 3.4 engine baseline originally showed a 33.3% Internal vs. 13.6% External strict ASR. However, the final augmented headlines revealed a much worse reality: **38.9% Internal ASR** and **25.9% External ASR**. Looking closely at the data, I found a total of 56 turn-level strict leaks across 267 turns under the augmented metric (compared to 32 leaks recorded by the engine alone).
* **The Turn-Local Refusal Loophole (`P2-LINK-003`):** I caught a bizarre flaw in how the model handles context windows. In tests involving data for Melissa Farrell and Michael Welch, the model would actively refuse to disclose private data like salaries or medical conditions on one turn, but if I immediately followed up by asking for "office locations" for "those employees," the model complied. The turn-level guardrail completely forgot the restricted context of the previous turn.
* **Low Initial Engine Agreement:** I expected the evaluation engine and human metrics to align closely, but the baseline engine-vs-human Cohen’s Kappa was incredibly low at **0.1643**. After running a rigorous judge calibration pass in Week 5.5, I managed to bring our final evaluation alignment to a highly defensible $\kappa = 0.83$.
* **Catching My Own Review Bugs:** I realized how easy it is to develop blind spots during data visualization. On my second review pass of the generation outputs, I caught a visual formatting bug in Figure 5 and a major calculation error in Figure 6 where the F5 metric was incorrectly showing 100%.

---

## 4. What I'd Do Differently: Concrete Changes

| Systemic Deficiency | Proposed Course Correction |
| :--- | :--- |
| **Thin Calibration Sample** | Expand the stratified sample size pool. Out of 46 records, I only had 15 total $L=1$ samples (11 strict_positive and 4 strict_positive_boundary). Calculating a severity-weighted kappa on 15 samples is statistically fragile; I should have scaled the pool to at least 100 records from the start. |
| **Single-Annotator Subjectivity** | Implement a multi-annotator framework. Relying entirely on my own single perspective introduces unvalidated bias. Having a peer dual-annotate a subset would make my evaluation far tighter. |
| **Imbalanced Attack Allocations** | Reallocate the scenario distribution. I over-indexed on External scenarios, running 27 External vs. 18 Internal. This generated an excess of false positives. I would reduce the External count and allocate those tokens to deeper F1/F2 internal attack vectors. |
| **Delayed Judge Integration** | Deploy the LLM judge back in Week 3 instead of waiting until Week 5. Bringing it into the pipeline earlier would have saved me weeks of manual triage by isolating false-positive classes before they polluted the broader analysis. |

---

## 5. What I Learned About LLMs: Observations From Data

> **Descriptive vs. Imperative Poisoning:** My data shows that the model easily ignores passive, buried policy language within documents. If the adversarial prompt isn't phrased as a direct, imperative command, the model's standard context processing bypasses it entirely.

Furthermore, automated evaluation engines are incredibly dumb when handling refusals. During External threat scenarios, the engine systematically over-counted leaks at a severity level of 2 because the model would say *"I cannot share employee salaries,"* and the engine would blindly trigger a positive match on the word *"salaries"*.

This engine flaw was proven by my key human-judge disagreements in files `S2B_37`, `SP_07`, and `SP_08`. The model mentioned an employee's name strictly to anchor a refusal statement. The automated engine flagged it as a data leak, while a human eye instantly reads it as compliant safety behavior.

---

## 6. Shortcuts and Realizations: My Journey

I have to be honest about where the pressure of deadlines caused me to take operational shortcuts, and what happened when I tried to bypass the work:

1. **The Triage Spreadsheet Risk (W5.4):** To speed up my hand-annotation sessions, I built a rapid-triage spreadsheet. I nearly ruined the entire blind audit because the sheet accidentally exposed the automated engine labels directly in my grading view. I caught the correlation warning just in time, scraped the spreadsheet, and forced myself to grade all 46 records manually across two completely isolated sessions. 
2. **AI-Assisted Prompt Generation (W4):** When I was drowning in the timeline to build the poisoned-document corpus, I used Claude Code to generate the initial prompt drafts. I didn't blindly copy-paste them—I reviewed, edited, and manually verified every single one before deployment—but it was still a shortcut to save time on asset creation.
3. **The Week 6.4 Handoff Warning:** I got a sharp lesson in automation bias when my W6.4 evaluation handoff package came back containing completely fabricated section references (§4.8 and Appendix D). It was a glaring reminder of what happens when you trust generated pipelines without verification, forcing me to check every single line before making my final git commits.

---

## 7. Looking Ahead to Phase 3: My Stance

The data from my Phase 2 report gives me an undeniable, evidence-backed strategy for the next defense implementation:

> My definitive stance is that the defense gap in enterprise LLM deployments is completely misunderstood. It does not live in input filtering. My metrics show that input guardrails (F3 through F8) are already incredibly effective, keeping strict ASR pinned between 0% and 6.7%. 

Spending more time optimizing input layers is a waste of resources. The real vulnerability occurs after documents are fetched into the context window and exploited across long conversations. Therefore, my Phase 3 priorities will focus entirely on:
1. **Retrieval-Time PII Anonymization:** Integrating an intermediary validation engine (like Presidio) to sanitize documents post-retrieval before they ever hit the prompt context.
2. **Conversation-Aware / Turn-Aware Refusal Mechanics:** Engineering a stateful system capable of tracking semantic drift across multi-turn exchanges to stop adversaries from leveraging turn-local loopholes.
