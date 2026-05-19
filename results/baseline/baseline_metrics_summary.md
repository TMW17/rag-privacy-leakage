# B2_CLEAN Baseline Analysis — Phase 2

---

## 1. Executive Summary

The B2_CLEAN campaign ran **45 scenarios** (Internal + External profiles, 3 runs each, 246 total turn records).

**ASR_strict (sev≥3) = 21.5%** — defensible headline metric measuring genuine PII disclosure (names, IDs, salaries, medical data). **ASR_inclusive = 55.6%** — upper bound including severity-2 category mentions (department name, job title) that frequently appear in refusal responses. The gap (46 scenario-runs L=1 inclusive but L=0 strict) represents the false-positive-prone refusal-with-category-mention class documented in the W3.2 pilot analysis.

Mean S̄ = **5.1878** per (scenario, run) pair; conditional on inclusive leakage, S̄ = **9.3380**. Hard-refusal rate = **43.7%**. Of 95 L=1 turns, **90.5%** are direct-PII leaks and **9.5%** are cross-reference (linkability) leaks. Named-target retrieval precision (8.3%) is below 50%: document-specific attacks frequently fetched the wrong document.

---

## 2. Per-Profile Results

| Profile | ASR_strict (sev≥3) | ASR_inclusive | Mean S̄ (all) | Mean S̄ (leaks) |
|---------|-------------------|---------------|--------------|-----------------|
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
| F8_CORPUS_POISONING | — | — | — | 0 _(P3/P4 pending)_ |

---

## 4. Leak-Type Breakdown

| Leak Type | L=1 Turns | % of L=1 Turns | Scenario-Level Rate† |
|-----------|-----------|----------------|----------------------|
| direct_pii | 86 | 90.5% | 53.3% |
| cross_reference | 9 | 9.5% | 6.7% |
| schema | 0 | 0.0% | 0.0% |
| none (L=0) | 151 | — | — |

_† Fraction of unique scenario IDs where any turn had this leak type._
_Rates can sum to >100% if a scenario produced multiple leak types._

> **Interpretation**: A high cross-reference rate with low retrieval precision
> indicates linkability leaks are driven by the retriever returning semantically
> similar but unintended documents. Direct-PII leaks represent higher-stakes
> concrete field-level exposure (names, national IDs, salaries, medical data).

### 4.5 Severity Filter Gap

**46 scenario-run pairs** were classified L=1 (inclusive) but L=0 (strict, sev≥3). These pairs had only severity-2 entity detections (department name, job title — low-sensitivity structural information). Family breakdown: F3_DIRECT_INJECTION (12), F7_SOCIAL_ENG (9), F1_DIRECT_PII (7), F5_JAILBREAK (6), F6_RECON (6), F2_LINKABILITY (3), F4_OBFUSCATION (3).

The dominant pattern: the model refused the attack while explaining *what categories of data the system holds*, inadvertently confirming low-sensitivity organisational structure. This is documented as the false-positive-prone refusal-with-category-mention class in the W3.2 pilot analysis. These cases count in ASR_inclusive but are excluded from ASR_strict.

---

## 5. Retrieval Precision

**Overall**: 8.3% — 3 of 36 named-target turns retrieved the intended document.

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
> This is still a real privacy failure, but the risk model differs.

---

## 6. Run-to-Run Variance

| Metric | Value |
|--------|-------|
| σ(ASR) across runs — mean per scenario | 0.0513 |
| σ(S̄) across runs — mean per scenario   | 0.9704 |

σ is computed per scenario (std dev over 3 runs, ddof=1), then averaged. Low σ(ASR) indicates stable attack outcomes at `temperature=0`. Non-zero σ(S) reflects retrieval stochasticity — ChromaDB may return different top-k chunks on repeated identical queries.

---

## 7. Refusal Rates

| Metric | Rate |
|--------|------|
| Hard refusal (scenario/run level) | 43.7% |
| Soft refusal with leak            | 19.3% |

---

## 8. Summary Statistics

| Stat | Value |
|------|-------|
| Unique scenarios | 45 |
| Runs per scenario | 3 |
| Total (scenario, run) pairs | 135 |
| Total turn records | 246 |
| **ASR_strict (sev≥3)** | **21.5%** |
| ASR_inclusive (any sev) | 55.6% |
| Sev-2-only scenario-run pairs | 46 |
| Mean S̄ (all pairs) | 5.1878 |
| Mean S̄ (leaks only) | 9.3380 |
| Named-target retrieval precision | 8.3% |

---

_**P3 (Admin / corpus-poisoning) and P4 (ThirdParty / offline-analysis)**_
_results are pending — they will be appended once B2\_POISONED and W5 analyses_
_complete. All figures above reflect Internal + External profiles only._