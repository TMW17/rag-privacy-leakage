# Phase 2 Baseline Analysis — B2_CLEAN + B2_POISONED

_Sources: `B2_CLEAN_main-w3.jsonl (246 rows)`, `B2_POISONED_poisoned-w4.jsonl (21 rows)`_

---

## 1. Executive Summary

The combined campaign ran **52 scenarios** across three attacker profiles — Admin (7), External (27), Internal (18) — with 3 runs each (267 total turn records).

**ASR_strict (sev≥3) = 18.6%** (combined; Internal + External only = 21.5%) — defensible headline metric measuring genuine PII disclosure (names, IDs, salaries, medical data). Admin profile contributes 0.0% ASR (corpus-poisoning attack resisted), pulling the combined figure below the B2_CLEAN-only baseline. **ASR_inclusive = 48.1%** — upper bound including severity-2 category mentions that appear in refusal responses. The gap (46 scenario-runs L=1 inclusive but L=0 strict) represents the false-positive-prone refusal-with-category-mention class documented in the W3.2 pilot analysis.

Mean S̄ = **4.4894** per (scenario, run) pair; conditional on inclusive leakage, S̄ = **9.3380**. Hard-refusal rate = **37.8%**. Of 95 L=1 turns, **90.5%** are direct-PII leaks and **9.5%** are cross-reference (linkability) leaks. Named-target retrieval precision (8.3%) is below 50%: document-specific attacks frequently fetched the wrong document.

---

## 2. Per-Profile Results

| Profile | ASR_strict (sev≥3) | ASR_inclusive | Mean S̄ (all) | Mean S̄ (leaks) |
|---------|-------------------|---------------|--------------|-----------------|
| Admin | **0.0%** | 0.0% | 0.0000 | — |
| External | **13.6%** | 70.4% | 6.2278 | 8.8500 |
| Internal | **33.3%** | 33.3% | 3.6278 | 10.8833 |

---

## 3. Per-Family Results

| Family | ASR_strict (sev≥3) | ASR_inclusive | Mean S̄ | n scenarios |
|--------|-------------------|---------------|--------|-------------|
| F1_DIRECT_PII | **48.1%** | 74.1% | 9.3000 | 9 |
| F2_LINKABILITY | **50.0%** | 60.0% | 9.0700 | 10 |
| F3_DIRECT_INJECTION | **0.0%** | 66.7% | 4.9000 | 6 |
| F4_OBFUSCATION | **0.0%** | 20.0% | 0.7200 | 5 |
| F5_JAILBREAK | **6.7%** | 46.7% | 1.8500 | 5 |
| F6_RECON | **0.0%** | 66.7% | 2.8000 | 3 |
| F7_SOCIAL_ENG | **0.0%** | 42.9% | 1.2000 | 7 |
| F8_CORPUS_POISONING | **0.0%** | 0.0% | 0.0000 | 7 |

---

## 3.5. Admin Profile — Corpus Poisoning Diagnostics

**Key finding: the corpus-poisoning attack *reached* the model but was not exploited.**

Across 21 Admin turns, a poisoned document was retrieved in **18/21 turns (85.7%)**. Despite this, **no leakage was detected in any of those 18 turns** — Sonnet 4.6 read the injected instructions and declined to act on them. This is the primary F8 finding for the unmitigated baseline.

| Metric | Value |
|--------|-------|
| Admin turns with ≥1 poisoned doc retrieved | 18/21 (85.7%) |
| Leak rate given poisoned doc retrieved | 0.0% |
| Admin ASR_strict | 0.0% |
| Admin ASR_inclusive | 0.0% |
| Soft refusal with leak (Admin) | 0.0% |

**Admin leak-type distribution (turn level):**

| Leak Type | Turns |
|-----------|-------|
| direct_pii | 0 |
| cross_reference | 0 |
| schema | 0 |
| none | 21 |

> The zero-exploitation result is expected for Sonnet 4.6: the model's > instruction-following hierarchy prioritises the system prompt over > corpus content. However, two conditions that *would* enable exploitation > are measured in Phase 3: (a) a weaker or misconfigured system prompt, > and (b) multi-turn dialogue where injected text is echoed back as > user-turn context.

### 3.5.1 Methodological Caveats

> Retrieval rate = **85.7%** (≥ 30% threshold). Corpus poisoning > content successfully reached the model in the majority of Admin turns. > The zero-leakage result reflects model resistance, not retrieval failure.

> No Admin L=1 turns on current data — cross-reference dominance check > is not applicable.

---

## 4. Leak-Type Breakdown

| Leak Type | L=1 Turns | % of L=1 Turns | Scenario-Level Rate† |
|-----------|-----------|----------------|----------------------|
| direct_pii | 86 | 90.5% | 46.2% |
| cross_reference | 9 | 9.5% | 5.8% |
| schema | 0 | 0.0% | 0.0% |
| none (L=0) | 172 | — | — |

_† Fraction of unique scenario IDs where any turn had this leak type._
_Rates can sum to >100% if a scenario produced multiple leak types._

> **Interpretation**: A high cross-reference rate with low retrieval precision
> indicates linkability leaks are driven by the retriever returning semantically
> similar but unintended documents. Direct-PII leaks represent higher-stakes
> concrete field-level exposure (names, national IDs, salaries, medical data).

### 4.5 Severity Filter Gap

**46 scenario-run pairs** were classified L=1 (inclusive) but L=0 (strict, sev≥3). These pairs had only severity-2 entity detections (department name, job title — low-sensitivity structural information). Family breakdown: F3_DIRECT_INJECTION (12), F7_SOCIAL_ENG (9), F1_DIRECT_PII (7), F5_JAILBREAK (6), F6_RECON (6), F2_LINKABILITY (3), F4_OBFUSCATION (3).

The dominant pattern: the model refused the attack while explaining *what categories of data the system holds*, inadvertently confirming low-sensitivity organisational structure. These cases count in ASR_inclusive but are excluded from ASR_strict.

---

## 5. Retrieval Precision

**Overall**: 8.3% — 3 of 36 named-target turns retrieved the intended document. Admin scenarios have no named-target queries (F8 targets behavior, not specific documents).

| Family | Named-Target Turns | Hits | Precision |
|--------|-------------------|------|-----------|
| F1_DIRECT_PII | 15 | 0 | 0.0% |
| F3_DIRECT_INJECTION | 6 | 0 | 0.0% |
| F4_OBFUSCATION | 3 | 0 | 0.0% |
| F5_JAILBREAK | 3 | 3 | 100.0% |
| F7_SOCIAL_ENG | 9 | 0 | 0.0% |

> **Implication**: Low retrieval precision on named-target queries means the
> attacker's specific document was not fetched, but a semantically similar one
> was — resulting in linkability leaks rather than targeted disclosure.

---

## 6. Run-to-Run Variance

| Metric | Value |
|--------|-------|
| σ(ASR) across runs — mean per scenario | 0.0444 |
| σ(S̄) across runs — mean per scenario   | 0.8398 |

σ is computed per scenario (std dev over 3 runs, ddof=1), then averaged. Non-zero σ(S) reflects retrieval stochasticity at `temperature=0`.

---

## 7. Refusal Rates

| Metric | Rate |
|--------|------|
| Hard refusal (scenario/run level) | 37.8% |
| Soft refusal with leak (all)      | 16.7% |
| Soft refusal with leak (Admin)    | 0.0% |

> Admin scenarios show low refusal rates: the model processed Admin queries > normally, retrieving injected content without triggering explicit refusals. > The absence of soft-refusal-with-leak for Admin indicates that when the > model declined to act on injected instructions, it did so without emitting > any partial PII — a clean rejection rather than a hedged response.

---

## 8. Summary Statistics

| Stat | Value |
|------|-------|
| Unique scenarios (total) | 52 |
|   — Admin | 7 |
|   — External | 27 |
|   — Internal | 18 |
| Runs per scenario | 3 |
| Total (scenario, run) pairs | 156 |
| Total turn records | 267 |
| **ASR_strict (sev≥3, combined)** | **18.6%** |
|   — Internal + External only | 21.5% (B2\_CLEAN baseline) |
|   — Admin | 0.0% |
| ASR_inclusive (any sev) | 48.1% |
| Sev-2-only scenario-run pairs | 46 |
| Mean S̄ (all pairs) | 4.4894 |
| Mean S̄ (leaks only) | 9.3380 |
| Named-target retrieval precision | 8.3% |
| Admin: poisoned-doc retrieval rate | 85.7% |
| Admin: ASR given poisoned retrieved | 0.0% |

---

_P4 (ThirdParty / offline-analysis) results are pending — to be appended_
_after W5 analysis. All figures above reflect Internal, External, and Admin_
_profiles (B2\_CLEAN + B2\_POISONED). P4 scenarios are not yet included._