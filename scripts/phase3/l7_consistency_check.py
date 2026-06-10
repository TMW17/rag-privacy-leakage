"""
l7_consistency_check.py — Phase 6 / Stage 1 (FREE: pure-Python, no pandas, no API, no pipeline).

Two jobs, both offline:
  1. Define the L7 QI GENERALIZATION HIERARCHY (the data the stateful k-anonymity gate will use):
     for each pre-registered quasi-identifier, an ordered list of generalization levels
     (level 0 = the committed Phase-1 bucketing; higher = coarser; last = SUPPRESS).
  2. CONSISTENCY CHECK: recompute the committed re-identification headline numbers
     (k-anonymity worst-4-subset = 84/100 unique; l-diversity 3-subset = 40 of 63 groups
     vulnerable) from this hierarchy's LEVEL-0 buckets, using an INDEPENDENT reimplementation
     (no import of scripts/reidentification_risk.py, no pandas), and assert they match the
     committed results/reidentification_risk.json. If they DO NOT match, the QI definition has
     drifted between the thesis and the extension -> exit 1 (STOP; no pipeline, no spend).

Why independent (not importing the original): reproducing the committed numbers with a separate
implementation proves the hierarchy's base level *is* the committed QI universe, rather than
trivially re-running the same code. This is the QI pre-registration guard from the spine made
executable.
"""
import json
import os
import sys
from itertools import combinations

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CORPUS = os.path.join(ROOT, "data/ground_truth/ground_truth.json")
COMMITTED = os.path.join(ROOT, "results/reidentification_risk.json")

# ── committed Phase-1 bucketing (verbatim from scripts/reidentification_risk.py), pd.cut right=True ──
_AGE_BINS = [20, 30, 40, 50, 60, 70]
_AGE_LABELS = ["20-30", "30-40", "40-50", "50-60", "60-70"]
_SAL_BINS = [0, 50000, 70000, 90000, 110000, 150000]
_SAL_LABELS = ["<50k", "50-70k", "70-90k", "90-110k", ">110k"]


def _cut(x, bins, labels):
    """Replicate pandas.cut(right=True): label i iff bins[i] < x <= bins[i+1]; else None."""
    if x is None:
        return None
    for i in range(len(labels)):
        if bins[i] < x <= bins[i + 1]:
            return labels[i]
    return None


def age_range(a):
    return _cut(a, _AGE_BINS, _AGE_LABELS)


def salary_range(s):
    return _cut(s, _SAL_BINS, _SAL_LABELS)


# =============================================================================
# L7 QI GENERALIZATION HIERARCHY  (pre-registered; level 0 == committed Phase-1 buckets)
#   Each QI: ordered levels from most specific (0) to SUPPRESS (last).
#   The gate generalizes UP this ladder until the candidate-set size k >= threshold,
#   then SUPPRESSes. Level-0 is what the consistency check below reproduces.
#   L1 value-groupings are filled from the ACTUAL corpus value sets (printed at run time),
#   not invented — see audit_value_sets().
# =============================================================================
# Concrete ladders. L0 = committed Phase-1 bucket (functions above for age/salary; raw for the
# categoricals). l1_map (where present) groups L0 values upward; final step is always SUPPRESS.
# l1_map keys are EXACTLY the corpus value sets printed by audit_value_sets() — coverage asserted.
QI_HIERARCHY = {
    "age_range": {
        "source_field": "age", "l0": "decade",
        "l1_map": {"20-30": "<=40", "30-40": "<=40", "40-50": "40-60", "50-60": "40-60", "60-70": ">60"},
        "terminal": "SUPPRESS",
    },
    "salary_range": {
        "source_field": "salary", "l0": "HR band",
        "l1_map": {"<50k": "<70k", "50-70k": "<70k", "70-90k": "70-110k", "90-110k": "70-110k", ">110k": ">110k"},
        "terminal": "SUPPRESS",
    },
    "department": {
        "source_field": "department", "l0": "raw",
        "l1_map": {"Engineering": "Technical", "Finance": "Corporate Services", "HR": "Corporate Services",
                   "Legal": "Corporate Services", "Marketing": "Commercial"},
        "terminal": "SUPPRESS",
    },
    "office_location": {
        "source_field": "office_location", "l0": "raw (building+floor)",
        "l1_map": {"Building A, Floor 1": "Building A", "Building A, Floor 2": "Building A",
                   "Building B, Floor 1": "Building B", "Building B, Floor 3": "Building B",
                   "Building C, Floor 1": "Building C"},
        "l2": "all -> on-site", "terminal": "SUPPRESS",
    },
    "medical_condition": {
        "source_field": "medical_condition", "l0": "raw",
        "l1_map": {"anxiety": "mental-health", "asthma": "respiratory", "diabetes": "cardiometabolic",
                   "hypertension": "cardiometabolic", "none": "none"},
        "l2_map": {"anxiety": "has-condition", "asthma": "has-condition", "diabetes": "has-condition",
                   "hypertension": "has-condition", "none": "none"},
        "terminal": "SUPPRESS",
    },
    "performance": {
        "source_field": "performance", "l0": "raw",
        "l1_map": {"excellent": "meets", "satisfactory": "meets", "needs improvement": "below"},
        "terminal": "SUPPRESS",
    },
    "gender": {  # no meaningful generalization between L0 and suppression
        "source_field": "gender", "l0": "raw", "terminal": "SUPPRESS",
    },
}
QUASI_IDENTIFIERS = list(QI_HIERARCHY.keys())             # the 7 pre-registered QIs
SENSITIVE = ["name", "national_id", "salary"]             # protected attrs (l-diversity)
HIGH_RISK_QI = ["department", "salary_range", "medical_condition"]   # committed l-div 3-subset


def load_records():
    recs = json.load(open(CORPUS))["employee_records"]
    out = []
    for r in recs:
        out.append({
            "department": r.get("department"),
            "salary_range": salary_range(r.get("salary")),
            "medical_condition": r.get("medical_condition"),
            "performance": r.get("performance"),
            "gender": r.get("gender"),
            "age_range": age_range(r.get("age")),
            "office_location": r.get("office_location"),
            # sensitive (raw):
            "name": r.get("name"), "national_id": r.get("national_id"), "salary": r.get("salary"),
        })
    return out


def groups_by(records, keys):
    """Group records by the tuple of `keys`; drop any record with None in a key (== pandas
    groupby observed=True, which omits NaN-keyed rows)."""
    g = {}
    for r in records:
        vals = tuple(r[k] for k in keys)
        if any(v is None for v in vals):
            continue
        g.setdefault(vals, []).append(r)
    return g


def k_anon_unique(records, combo):
    g = groups_by(records, list(combo))
    return sum(1 for members in g.values() if len(members) == 1)   # equivalence classes of size 1


def audit_value_sets(records):
    print("\n-- corpus value sets (for grounding the hierarchy's L1 groupings) --")
    for q in ["department", "medical_condition", "office_location", "performance", "gender"]:
        vals = sorted({r[q] for r in records if r[q] is not None})
        print(f"   {q} ({len(vals)}): {vals}")


def main():
    recs = load_records()
    n = len(recs)
    print(f"corpus: {n} employee records | QIs: {QUASI_IDENTIFIERS}")

    # ── recompute k-anonymity over all 2/3/4-QI subsets; find the worst (max unique) ──
    best_combo, best_unique = None, -1
    for size in (2, 3, 4):
        for combo in combinations(QUASI_IDENTIFIERS, size):
            u = k_anon_unique(recs, combo)
            if u > best_unique:
                best_unique, best_combo = u, combo
    print(f"\n[k-anon] worst subset: {best_combo}\n         unique_records = {best_unique}/{n}")

    # ── recompute l-diversity on the committed 3-subset ──
    ldiv_groups = groups_by(recs, HIGH_RISK_QI)
    vulnerable = 0
    for members in ldiv_groups.values():
        min_l = min(len({m[a] for m in members}) for a in SENSITIVE)
        if min_l == 1:
            vulnerable += 1
    print(f"[l-div] {HIGH_RISK_QI}: {len(ldiv_groups)} groups, {vulnerable} vulnerable (l=1)")

    # ── cross-check against committed results/reidentification_risk.json ──
    committed = json.load(open(COMMITTED))
    c_unique = max(v["unique_records"] for v in committed["k_anonymity_analysis"].values())
    c_worst = max(committed["k_anonymity_analysis"].values(), key=lambda v: v["unique_records"])
    c_ldiv_groups = len(committed["l_diversity_analysis"])
    c_ldiv_vuln = sum(1 for g in committed["l_diversity_analysis"] if g.get("vulnerable"))

    print("\n-- committed (results/reidentification_risk.json) --")
    print(f"   k-anon worst unique = {c_unique}/100  combo = {c_worst['quasi_identifiers']}")
    print(f"   l-div groups = {c_ldiv_groups}  vulnerable = {c_ldiv_vuln}")

    # hierarchy coverage: every observed value of each categorical QI with an l1_map is mapped
    cover_ok, uncovered = True, {}
    for q, spec in QI_HIERARCHY.items():
        m = spec.get("l1_map")
        if not m:
            continue
        miss = sorted({r[q] for r in recs if r[q] is not None} - set(m))
        if miss:
            cover_ok = False
            uncovered[q] = miss

    checks = {
        "k_anon_unique == committed (84)": best_unique == c_unique == 84,
        "k_anon worst combo == committed": set(best_combo) == set(c_worst["quasi_identifiers"]),
        "l_div groups == committed (63)": len(ldiv_groups) == c_ldiv_groups == 63,
        "l_div vulnerable == committed (40)": vulnerable == c_ldiv_vuln == 40,
        "hierarchy L1 maps cover all corpus values": cover_ok,
    }
    if uncovered:
        print(f"\n   UNCOVERED hierarchy values: {uncovered}")
    audit_value_sets(recs)
    print("\n== CONSISTENCY CHECK ==")
    for name, ok in checks.items():
        print(f"   [{'PASS' if ok else 'MISMATCH'}] {name}")
    allok = all(checks.values())
    print(f"\n{'PASS — hierarchy L0 reproduces the committed re-id numbers; no QI drift.' if allok else 'MISMATCH — QI definition drifted. STOP. Do not build the gate.'}")
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
