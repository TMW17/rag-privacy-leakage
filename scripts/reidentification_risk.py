"""
reidentification_risk.py
========================
Privacy Metrics — k-Anonymity and l-Diversity Analysis

Quantifies the re-identification risk (mosaic effect) in the synthetic
employee dataset. This maps to the LINKABILITY threat in the LINDDUN
framework (Table 1.1, row 1).

RUN FROM:  cd PFE/code && python scripts/reidentification_risk.py
INPUT:     data/ground_truth/ground_truth.json
OUTPUT:    results/reidentification_risk.json

Author:  TADJ Mohamed Walid
Project: Generative AI, Privacy & Personal Data (ESI Sidi Bel Abbès)
"""

from itertools import combinations
import json
import pandas as pd

# ─── Path fix ─────────────────────────────────────────────
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─── Project imports ──────────────────────────────────────
from scripts.config import GROUND_TRUTH_FILE, REIDENTIFICATION_RISK_FILE


# ─── Load the ground truth corpus ─────────────────────────
with open(GROUND_TRUTH_FILE) as f:
    data = json.load(f)

df = pd.DataFrame(data["employee_records"])

# ── Bin continuous variables into discrete ranges ─────────────────────────
# k-Anonymity requires quasi-identifiers to be DISCRETE (categorical) values.
# Continuous fields like salary and age must be bucketed into ranges before
# the groupby operation, otherwise each individual would be in their own group
# and k_min would always equal 1 — making the analysis meaningless.
#
# Salary bins: chosen to match typical HR pay bands (wide enough that multiple
# employees fall into each bin, narrow enough to remain informative).
df['salary_range'] = pd.cut(
    df['salary'],
    bins=[0, 50000, 70000, 90000, 110000, 150000],
    labels=['<50k', '50-70k', '70-90k', '90-110k', '>110k']
)
# Age bins: 10-year decades are the standard granularity used in privacy
# research and healthcare datasets (e.g. HIPAA Safe Harbor method).
df['age_range'] = pd.cut(
    df['age'],
    bins=[20, 30, 40, 50, 60, 70],
    labels=['20-30', '30-40', '40-50', '50-60', '60-70']
)

# Quasi-identifiers (QIs): fields that are NOT directly identifying alone,
# but can identify an individual when combined (the "mosaic effect").
# These correspond to LINDDUN Linkability threats.
quasi_identifiers = [
    "department", "salary_range", "medical_condition",
    "performance", "gender", "age_range", "office_location"
]

# Sensitive attributes: the fields we want to PROTECT.
# l-Diversity checks that within any equivalence class defined by the QIs,
# these attributes have at least l distinct values (so an attacker cannot
# infer a specific individual's sensitive value from the QI combination).
sensitive_attributes = ["name", "ssn", "salary"]


# =================================================================
#  PART 1: k-ANONYMITY
# =================================================================

print("=" * 65)
print("PART 1: k-ANONYMITY ANALYSIS")
print("=" * 65)
print()

risk_report = {}
high_risk_combos = []

# Iterate over all combinations of 2, 3, and 4 quasi-identifiers.
# We cap at 4 (not all 7) because with more QIs the groups become very small
# and the analysis becomes trivially "high risk" for all combinations.
for combo_size in range(2, min(len(quasi_identifiers) + 1, 5)):
    for combo in combinations(quasi_identifiers, combo_size):
        combo_list = list(combo)

        # Group the dataset by this combination of QIs.
        # observed=True suppresses pandas warnings about unused category combinations.
        # Each group is an "equivalence class": all employees with the same QI values.
        group_sizes = df.groupby(combo_list, observed=True).size()

        # k_min: the smallest equivalence class.
        # k-Anonymity requires k_min ≥ k (commonly k=5 for medical/HR data).
        # If k_min=1, one individual is UNIQUELY identified by this QI combination.
        k_min = group_sizes.min()
        k_mean = group_sizes.mean()  # average group size (higher = safer)

        # Count groups where only ONE person matches the QI values (unique records).
        # These individuals can be singled out by an attacker who knows their QI values.
        unique_records = (group_sizes == 1).sum()

        # Small groups (k ≤ 3) are also risky: attacker has a 1-in-3 chance or better.
        small_groups = (group_sizes <= 3).sum()

        # risk_percentage = % of the total dataset that can be uniquely identified
        # by this QI combination. >10% is a significant re-identification risk.
        risk_pct = (unique_records / len(df)) * 100

        entry = {
            "quasi_identifiers":    combo_list,
            "k_min":                int(k_min),
            "k_mean":               round(float(k_mean), 2),
            "unique_records":       int(unique_records),
            "small_groups_k_le_3":  int(small_groups),
            "risk_percentage":      round(risk_pct, 2),
            # k ≥ 5 is the threshold recommended by HIPAA Safe Harbor and
            # many EU data protection authorities for anonymized datasets.
            "k_anonymity_satisfied": k_min >= 5,
        }
        risk_report[str(combo)] = entry

        if risk_pct > 10:
            high_risk_combos.append(entry)
            print(f"  HIGH RISK: {combo}")
            print(f"    k_min = {k_min} | Unique: {unique_records}/100 ({risk_pct:.1f}%)")
            print(f"    Groups with k ≤ 3: {small_groups}")
            print()

if not high_risk_combos:
    print("  No high-risk combinations found (all below 10% uniqueness).")
    print()


# =================================================================
#  PART 2: l-DIVERSITY
# =================================================================

print("=" * 65)
print("PART 2: l-DIVERSITY ANALYSIS")
print("=" * 65)
print()

# Use the 3-attribute combination most likely to produce high-risk groups.
# This is a realistic attacker scenario: an adversary who knows an employee's
# department, salary range, and medical condition can narrow the candidate pool.
high_risk_qi = ["department", "salary_range", "medical_condition"]
diversity_results = []

for group_name, group_df in df.groupby(high_risk_qi, observed=True):
    l_values = {}
    for attr in sensitive_attributes:
        # l-Diversity for this attribute = number of DISTINCT values in this group.
        # l=1 means every person in the group has the SAME value for this attribute —
        # an attacker who can place someone in this group knows their exact salary or SSN.
        l_values[attr] = group_df[attr].nunique()

    diversity_results.append({
        "group": str(group_name), "group_size": len(group_df),
        "l_values": l_values,
        # min_l is the worst-case diversity across all sensitive attributes.
        "min_l": min(l_values.values()),
        # "vulnerable" groups (l=1) completely fail l-diversity:
        # one sensitive attribute is the same for every member of the group.
        "vulnerable": min(l_values.values()) == 1,
    })

vulnerable_groups = [d for d in diversity_results if d["vulnerable"]]
print(f"  Quasi-identifiers: {high_risk_qi}")
print(f"  Total groups: {len(diversity_results)}")
print(f"  Vulnerable groups (l=1): {len(vulnerable_groups)}")
print()
# Show only the first 5 vulnerable groups to keep output readable.
for vg in vulnerable_groups[:5]:
    print(f"    Group {vg['group']} (size={vg['group_size']})")
    print(f"      l-diversity: {vg['l_values']}")
    print()


# =================================================================
#  PART 3: RISK MATRIX
# =================================================================

print("=" * 65)
print("PART 3: RISK MATRIX (for Chapter 2)")
print("=" * 65)
print()

# Sort QI combinations by uniqueness percentage (descending) to show the
# most dangerous combinations first. Top 15 is enough to cover the major risks.
sorted_risks = sorted(risk_report.values(), key=lambda x: -x["risk_percentage"])
print(f"  {'Quasi-Identifiers':<55} {'k_min':>5} {'Unique%':>8} {'Risk':>8}")
print(f"  {'─' * 55} {'─' * 5} {'─' * 8} {'─' * 8}")
for entry in sorted_risks[:15]:
    qi_str = " + ".join(entry["quasi_identifiers"])[:55]
    pct = entry["risk_percentage"]
    # Risk thresholds for the report (chosen to match common privacy standards):
    #   CRITICAL (>25%): more than 1 in 4 employees can be uniquely identified
    #   HIGH     (>10%): more than 1 in 10 employees are at risk
    #   MEDIUM   (>5%):  more than 1 in 20 employees are at risk
    #   LOW      (≤5%):  acceptable for research datasets
    risk_label = ("CRITICAL" if pct > 25 else "HIGH" if pct > 10
                  else "MEDIUM" if pct > 5 else "LOW")
    print(f"  {qi_str:<55} {entry['k_min']:>5} {pct:>7.1f}% {risk_label:>8}")


# =================================================================
#  SAVE REPORT
# =================================================================

full_report = {
    "k_anonymity_analysis": risk_report,
    "l_diversity_analysis": diversity_results,
    "summary": {
        "total_records": len(df),
        "quasi_identifiers_tested": quasi_identifiers,
        "high_risk_combinations": len(high_risk_combos),
        "vulnerable_l_diversity_groups": len(vulnerable_groups),
        "max_risk_percentage": sorted_risks[0]["risk_percentage"] if sorted_risks else 0,
    }
}

# Save to results/reidentification_risk.json
with open(REIDENTIFICATION_RISK_FILE, 'w') as f:
    json.dump(full_report, f, indent=2, default=str)

print(f"\n  Saved to: {REIDENTIFICATION_RISK_FILE}")
