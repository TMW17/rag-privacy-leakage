# Task 0.1 — sev≥3 recall gate FAILED: diagnosis + fix proposal

**Gate:** sev≥3 recall ≥ 0.90. **Result: FAIL on every variant**
(correct-label all 0.6208 / locatable 0.6655; any-label all 0.7141 / locatable 0.7655).

## What already works (do not touch)
- Custom recognizers: **NNI_DZ, EMPLOYEE_ID, HEALTH_RECORD_ID, IBAN_DZ = 1.0 recall**.
- Default `IBAN_CODE` does **not** catch the synthetic hyphenated DZ IBAN → custom `IBAN_DZ` was required (confirmed).
- Out-of-box strong: PERSON, EMAIL, DOB, INTERNAL_IP, NATIONAL_ID = 1.0.

## The 13 sev≥3 blind spots, binned by how (and whether) to fix

### (a) Legitimate, generalizable structured detectors — SAFE to add
| type | n | now (any/corr) | proposed recognizer |
|---|--:|---|---|
| API_KEY | 10 | 0.0/0.0 | `\bsk-(ant-)?[A-Za-z0-9]{20,}\b` |
| JWT_TOKEN | 5 | 0.0/0.0 | `\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b` |
| PASSWORD_HASH | 5 | 0.2/0.0 | bcrypt `\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}` |
| PRIVATE_KEY | 5 | 0.0/0.0 | PEM block `-----BEGIN [A-Z ]*PRIVATE KEY-----` |
| DB_CONN_STRING | 5 | 1.0/0.0 | URI `\b\w+://[^\s:@]+:[^\s:@]+@[^\s]+` (fixes wrong-label) |
| FILE_PATH | 15 | 0.0/0.0 | `(/[\w.-]+){2,}` with context |
| CROSS_REFERENCE | 41 | 0.0/0.0 | `\bhr_file_\d{3}\b` |
| PHONE (correct-label) | 100 | 1.0/0.51 | DZ phone `\+213[-\s]?\d{2,3}[-\s]?\d{6}` raises correct-label |
| SALARY | 100 | 0.48/0.0 | number + context ("Salary","compensation") — field pattern, **not** value memorization |

### (b) Overfitting traps — REFUSE (would memorize the answer key)
- **MEDICAL (93)** and **SURNAME_TITLE (49)**: a gazetteer seeded from the corpus's own
  `medical_condition` / surname values = memorizing the test set → invalid for the thesis.
  **Legit alternative = ML NER**, not regex: Presidio transformers medical-NER for MEDICAL,
  and `en_core_web_trf` (vs `_lg`) for surname-only PERSON mentions like "Hill, Data Scientist".

### (c) Measurement artifact — fix the measurement, not a recognizer
- **AGE_GENDER (100, not_locatable=100):** answer-key text ("36-year-old male employee")
  is synthesized and absent verbatim from the corpus ("Age: 36" / "Gender: male").
  Already excluded in the *locatable* denominator (1490→1390). Needs a measurement
  decision (match field values) before any recognizer claim is meaningful.

### (d) Semantic — out of regex scope
- **SYSTEM_PROMPT (5):** free text; not regex-detectable. Needs semantic / LLM detection
  (or arguably is not classic PII).

## Arithmetic: the honest ceiling
Crediting **every** bin-(a) fix recovers ~235 correct-label entities → **≈0.83 correct-label
/ ≈0.88 any-label** (locatable). The remaining gap to 0.90 is **MEDICAL (93) + SURNAME (49)**,
which sit in bins (b)/(c). 

**Conclusion: Presidio + legitimate recognizers cannot reach 0.90 on this corpus without
either ML-NER or overfitting.** That ceiling is the empirical motivation for the layered
defense (output filter + LLM judge covering medical/semantic/name leakage).

## Decision required (do NOT proceed to L2 until chosen)
1. **Accept Presidio's ceiling (~0.83–0.88)** + let downstream layers cover the rest — the thesis's actual argument.
2. **Add bin-(a) recognizers + ML-NER** (transformers medical-NER + `en_core_web_trf`) and re-measure — legit, more setup.
3. **Overfit to pass the gate** — rejected; documented here as a methodological anti-pattern.
