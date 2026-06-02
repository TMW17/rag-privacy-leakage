"""
l6_linkage.py — Task 3.5 DIAGNOSTIC artifact (Task 3.5 closed as a DIAGNOSIS, NOT a reduction).

STATUS: this is a diagnostic illustration of WHERE the F2 recall gap is — NOT a measured defense.
A FREE context pre-check confirmed it strips the L2-residual prose-salary/medical on F2 chunks
while sparing dept/office/schedule on benign chunks, but it was NEVER run end-to-end with spend:
**no judged ASR / no ASR reduction is claimed for it.** It is IN-SAMPLE by construction (see below)
and does not generalize. See results/phase3/linkability_diagnosis/FINDING.md. Headline unchanged:
17.3% judged-augmented (full stack) remains primary.

HONEST FRAMING (locked, per advisor review — do NOT relabel as k-anonymity):
This is **targeted RECALL-CLOSURE on the F2 attribute pathway**, NOT a k-anonymity / linkage
mechanism. The diagnosed F2 residual (judged ~0.6 under every redaction config) is dominated by
two SENSITIVE-ATTRIBUTE values that L2's Presidio MISSED and the judge then flagged as direct PII
tied to identifiable people/groups:
  (a) salary figures in PROSE ("compensation of $106,307", "120,000 DA") — Presidio's structured
      SALARY recognizer misses prose money;
  (b) medical conditions ("anxiety") — open-vocabulary, which Presidio misses.
L6 suppresses these two attribute values in the assembled context (post-L2, pre-generation) via a
money regex + a medical gazetteer.

STRUCTURAL OVERFITTING DISCLOSURE (this is in-sample BY CONSTRUCTION, not merely disclosable):
  * the medical gazetteer = the corpus's OWN `medical_condition` values -> perfect recall by
    construction on this closed synthetic corpus. That closedness is the very reason the real
    MEDICAL blind spot exists (open vocabulary). It does NOT generalize.
  * the money regex was built from the salary formats observed in the F2 judge rationales.
  * developed AND evaluated on the same F2 set (test-set tuning).
So L6 closes the *observed, corpus-specific* recall leaks IN-SAMPLE; it does **not** generalize,
and it does **not** address the genuine attribute-to-group LINKAGE cases (e.g. performance
"excellent" -> Finance dept, P1-LINK-006 / P2-LINK-002), which need true entity-resolution.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# money in prose: $1,234 / $1,234.56 / 120,000 DA / 95,000 DZD / 1,000 dinars
_MONEY = re.compile(
    r"\$\s?\d{1,3}(?:,\d{3})+(?:\.\d+)?"
    r"|\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\s?(?:DA|DZD|dinars?)\b", re.IGNORECASE)
_GAZ = None


def _gazetteer():
    """Medical-condition terms = the corpus's own medical_condition values (IN-SAMPLE by design)."""
    global _GAZ
    if _GAZ is None:
        emp = json.load(open(os.path.join(ROOT, "data/ground_truth/ground_truth.json")))["employee_records"]
        terms = set()
        for e in emp:
            m = str(e.get("medical_condition", "")).strip().lower()
            if m and m not in ("none", "n/a", "healthy", ""):
                terms.add(m)
        _GAZ = sorted(terms, key=len, reverse=True)   # longest-first to avoid partial overlaps
    return _GAZ


def redact_linkage(text):
    """Suppress the F2 linking attributes L2 missed: prose salary -> <SALARY>, medical -> <MEDICAL>.
    Returns (redacted_text, {n_salary, n_medical}). Free (regex + gazetteer; no API)."""
    n = {"n_salary": 0, "n_medical": 0}

    def _sal(_m):
        n["n_salary"] += 1
        return "<SALARY>"
    out = _MONEY.sub(_sal, text)
    for term in _gazetteer():
        out, k = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE).subn("<MEDICAL>", out)
        n["n_medical"] += k
    return out, n
