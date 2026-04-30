"""
validate_ground_truth.py
========================
Automated Consistency Validation Suite

Pre-flight check before Phase 2: verifies internal consistency between
ground_truth.json and ground_truth_annotations.json. Do not proceed
to Phase 2 until all checks pass.

RUN FROM:  cd PFE/code && python scripts/validate_ground_truth.py
INPUT:     data/ground_truth/ground_truth.json
           data/ground_truth/ground_truth_annotations.json
EXIT CODE: 0 = all passed, 1 = errors found

Author:  TADJ Mohamed Walid
Project: Generative AI, Privacy & Personal Data (ESI Sidi Bel Abbès)
"""

import json
import sys
import os

# ─── Path fix ─────────────────────────────────────────────
# Add the project root (parent of scripts/) to sys.path so that
# "from scripts.config import ..." works regardless of how the
# script is invoked.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─── Project imports ──────────────────────────────────────
from scripts.config import GROUND_TRUTH_FILE, ANNOTATIONS_FILE


PASS = "✓"
FAIL = "✗"
errors = []


def check(condition, message):
    """
    Evaluate a single validation condition and accumulate failures.

    All errors are collected into the `errors` list rather than raising
    exceptions immediately. This allows the script to run ALL checks and
    report every problem at once, instead of stopping at the first failure.
    The summary section at the bottom then prints the full list and exits
    with code 1 if any errors were found.
    """
    if condition:
        print(f"  {PASS} {message}")
    else:
        print(f"  {FAIL} {message}")
        errors.append(message)


# ─── Load files ───────────────────────────────────────────
with open(GROUND_TRUTH_FILE) as f:
    gt = json.load(f)

with open(ANNOTATIONS_FILE) as f:
    ann_data = json.load(f)

# Support v1 (plain list) and v2 ({"metadata":..., "annotations":[...]}) formats.
# v2 is produced by the current annotate_dataset.py.
# The nested isinstance(dict) check handles the rare edge case where the
# top-level value of "annotations" is itself a dict (legacy v1 format).
annotations = ann_data.get("annotations", ann_data)
if isinstance(annotations, dict):
    annotations = annotations.get("annotations", [])

# ── Build lookup indexes for O(1) access during checks ───────────────────
# gt_index: maps each document_id → its full document dict (from ground_truth.json)
gt_index = {}
for cls in ["employee_records", "system_configs", "internal_memos", "medical_reports"]:
    for record in gt.get(cls, []):
        gt_index[record["document_id"]] = record

# ann_index: maps each document_id → its annotation dict (from ground_truth_annotations.json)
ann_index = {a["document_id"]: a for a in annotations}


# =================================================================
#  VALIDATION CHECKS
# =================================================================

print("=" * 60)
print("GROUND TRUTH VALIDATION SUITE")
print("=" * 60)

# ── CHECK 1: Document ID Coverage ────────────────────────────────────────
# Verifies bidirectional consistency between the two files:
#   a) Every annotation references a document that actually exists in the corpus.
#      (Detects orphaned annotations — entries that point to deleted documents.)
#   b) Every document in the corpus has at least one annotation entry.
#      (Detects unannotated documents that would silently skew coverage metrics.)
print("\n1. Document ID Coverage:")
for doc_id in ann_index:
    check(doc_id in gt_index, f"Annotation {doc_id} exists in ground_truth.json")
missing = set(gt_index.keys()) - set(ann_index.keys())
check(len(missing) == 0,
      f"All {len(gt_index)} documents have annotations (missing: {len(missing)})")

# ── CHECK 2: Severity Level Coverage ─────────────────────────────────────
# Verifies that the corpus contains entities at EVERY severity level (2–5).
# If any level is missing, the evaluation engine cannot be tested at that level,
# and the thesis claims about multi-level detection would be unsupported.
# A missing severity usually means a bug in annotate_dataset.py.
print("\n2. Severity Level Coverage:")
all_severities = set()
for ann in annotations:
    for e in ann.get("entities", []):
        all_severities.add(e["severity"])
for sev in [2, 3, 4, 5]:
    check(sev in all_severities, f"Severity {sev} is represented")

# ── CHECK 3: LINDDUN Category Coverage ───────────────────────────────────
# Verifies that the corpus covers all 5 LINDDUN threat categories used in
# the thesis (Table 1.1). These categories justify the breadth of the
# threat model. A missing category means no experiment will test that threat.
# (Non-repudiation and Unawareness are the hardest to represent — check these.)
print("\n3. LINDDUN Category Coverage:")
all_linddun = set()
for ann in annotations:
    for e in ann.get("entities", []):
        lc = e.get("linddun_category", "")
        if lc:
            all_linddun.add(lc)
for cat in ["Identifiability", "Disclosure", "Linkability", "Detectability", "Unawareness"]:
    check(cat in all_linddun, f"LINDDUN category '{cat}' is represented")

# ── CHECK 4: Confidence Weight Consistency ────────────────────────────────
# Each detection_method has a fixed confidence weight w(e) defined in Table 6.1.
# This check verifies that every entity in the annotations has the correct
# weight for its method. A mismatch would cause incorrect severity scores S.
#
# Why abs(actual - expected) > 0.01?
#   Floating-point comparison: 0.75 stored in JSON and re-read may be
#   0.7499999... due to IEEE 754 representation. We use a tolerance of 0.01
#   to avoid spurious failures from floating-point rounding.
print("\n4. Confidence Weight Consistency:")
EXPECTED_WEIGHTS = {
    "Regex": 1.00, "Regex+Presidio": 1.00, "Regex+Context": 0.75,
    "NER": 0.90, "NER+Presidio": 0.90, "NER+Context": 0.90,
    "NER+Keyword": 0.90, "NER+Regex": 0.90,
    "Keyword+Context": 0.75, "LLM-as-Judge": 0.60,
    "Set-intersection": 0.75, "Membership-inference": 0.75,
}
weight_mismatches = 0
for ann in annotations:
    for e in ann.get("entities", []):
        method = e.get("detection_method", "")
        actual = e.get("confidence_weight", -1)
        expected = EXPECTED_WEIGHTS.get(method)
        # Only check methods we know about; skip unknown/custom methods.
        if expected is not None and abs(actual - expected) > 0.01:
            weight_mismatches += 1
check(weight_mismatches == 0,
      f"All confidence weights match Table 6.1 (mismatches: {weight_mismatches})")

# ── CHECK 5: Entity Count Sanity ──────────────────────────────────────────
# Two sub-checks:
#   a) At least 1 entity exists (catches a completely empty annotations file).
#   b) More than 500 entities exist (the minimum needed for meaningful
#      precision/recall and coverage statistics in the thesis experiments).
#      With 155 documents and ~10–20 entities per employee record, we should
#      have well over 1000 entities if annotation is working correctly.
print("\n5. Entity Count Sanity:")
total_entities = sum(len(a.get("entities", [])) for a in annotations)
check(total_entities > 0, f"Total entities: {total_entities}")
check(total_entities > 500,
      f"Sufficient volume for statistics (need >500, have {total_entities})")

# ── CHECK 6: Cross-Document Reference Validation ──────────────────────────
# Medical reports (Class 4) reference employee records (Class 1) via the
# "employee_ref" field (e.g. "hr_file_005"). This check verifies that every
# such reference points to an actual existing employee record.
#
# A broken reference would mean:
#   - The evaluation engine cannot retrieve the correct annotations for a
#     medical report query, causing missed leakage detections.
#   - The cross-document linkability test (LINDDUN Linkability) becomes invalid.
print("\n6. Cross-Document Reference Validation:")
refs_valid = 0
refs_total = 0
for ann in annotations:
    if ann.get("document_type") == "medical_report":
        # employee_ref is stored directly on the annotation (not inside entities)
        # because it's a document-level link, not an entity-level link.
        emp_ref = ann.get("employee_ref")
        if emp_ref:
            refs_total += 1
            if emp_ref in gt_index:
                refs_valid += 1
if refs_total > 0:
    check(refs_valid == refs_total,
          f"Medical report → employee refs: {refs_valid}/{refs_total} valid")
else:
    print("  — No cross-references to validate")


# =================================================================
#  SUMMARY
# =================================================================

print()
print("=" * 60)
if errors:
    print(f"VALIDATION FAILED — {len(errors)} error(s) found:")
    for err in errors:
        print(f"  {FAIL} {err}")
    print("\nFix these before proceeding to Phase 2.")
    # Exit code 1 signals failure to CI pipelines or calling scripts.
    # Any non-zero exit code will cause a shell script like:
    #   python validate_ground_truth.py && python run_experiments.py
    # to stop before running experiments on a broken corpus.
    sys.exit(1)
else:
    print("VALIDATION PASSED — All checks passed.")
    print("Ground truth is ready for Phase 2 experiments.")
    # Exit code 0 is the POSIX standard for success.
    sys.exit(0)
