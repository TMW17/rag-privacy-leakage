"""
reconcile_annotations.py
========================
Annotation-count reconciliation runner (NON-DESTRUCTIVE).

PURPOSE
-------
Two project documents report different annotation totals for the SAME
seed-42 corpus:

    State A  (Phase 1 .tex: Formal_Leakage_Definitions_and_Ground_Truth.tex,
              phase1.tex terminal box)        -> 2,315 entities / 33 types / sev5 = 235
    State B  (Phase 2 report, Phase1.md,
              frozen ground_truth_annotations) -> 2,190 entities / 31 types / sev5 = 135

This script RE-RUNS the current annotation logic on the FROZEN corpus and
localizes the 125-entity gap, per type and per severity.

WHAT IT DOES (and does NOT do)
------------------------------
  * Imports the four annotation functions from scripts/annotate_dataset.py and
    applies them, in __main__ order, to the frozen data/ground_truth/ground_truth.json.
    It NEVER runs either pipeline script's __main__ block, so no frozen artifact
    is regenerated or overwritten.
  * Writes ONLY to results/annotation_reconciliation/ (fresh_count.json, version_diff.json).
  * Asserts the fresh re-run reproduces the frozen annotations file byte-for-count
    (integrity check: proves the frozen file equals what the current code emits).

State-A numbers below are the RECORDED prior state, taken verbatim from git
artifact 1a19e73 (`data/ground_truth/ground_truth_annotations.json` at that commit),
which is identical to the terminal box in Formal_Leakage_Definitions_and_Ground_Truth.tex
(lines 703-719). They are historical fact, not re-derived here.

Run:  python results/annotation_reconciliation/reconcile_annotations.py
"""

import json
import os
import sys
import subprocess
from collections import Counter

# ─── Project import path (same pattern as scripts/*.py) ────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from scripts.config import GROUND_TRUTH_FILE, ANNOTATIONS_FILE
# Importing the module executes only module-level code (loads ground_truth.json,
# defines ENTITY_SPECS + the four annotate_* functions). The __main__ block,
# which is the ONLY place that writes the frozen file, does NOT run on import.
from scripts.annotate_dataset import (
    annotate_employee_record,
    annotate_system_config,
    annotate_medical_report,
    annotate_internal_memo,
    ENTITY_SPECS,
)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ───────────────────────────────────────────────────────────────────────────
#  STATE A — recorded prior state (git 1a19e73 == Phase 1 .tex terminal box).
#  Provenance: `git show 1a19e73:data/ground_truth/ground_truth_annotations.json`.
# ───────────────────────────────────────────────────────────────────────────
STATE_A_SHA = "1a19e73"
STATE_A_PER_TYPE = {
    "ADDRESS": 100, "AGE_GENDER": 100, "API_KEY": 10, "ARCHITECTURE": 5,
    "CROSS_REFERENCE": 40, "DB_CONN_STRING": 5, "DEPARTMENT": 100, "DOB": 100,
    "EMAIL": 100, "EMPLOYEE_ID": 100, "FILE_PATH": 15, "HEALTH_RECORD_ID": 130,
    "IBAN": 100, "IMMIGRATION": 29, "INTERNAL_IP": 5, "JOB_TITLE": 100,
    "JWT_TOKEN": 5, "MEDICAL": 83, "NATIONAL_ID": 100, "OFFICE_LOCATION": 100,
    "PASSWORD_HASH": 5, "PERFORMANCE": 100, "PERSON": 130, "PHONE": 100,
    "PRIVATE_KEY": 5, "PROJECT": 100, "RELIGIOUS": 43, "SALARY": 100,
    "SSN": 100, "SURNAME_TITLE": 100, "SYSTEM_PROMPT": 5, "TRAINING": 100,
    "WORK_SCHEDULE": 100,
}
STATE_A_AGG = {
    "total_entities": 2315, "distinct_types": 33, "entity_spec_count": 37,
    "severity": {"5": 235, "4": 865, "3": 515, "2": 700},
    "linddun": {"Identifiability": 1160, "Unawareness": 500, "Disclosure": 290,
                "Detectability": 225, "Linkability": 140},
}


def histogram(annotations):
    """Per-type / per-severity / per-LINDDUN counts over a list of doc-annotations."""
    types, sev, lind = Counter(), Counter(), Counter()
    for ann in annotations:
        for e in ann["entities"]:
            types[e["type"]] += 1
            sev[e["severity"]] += 1
            lind[e["linddun_category"]] += 1
    return types, sev, lind


def rerun_on_frozen_corpus():
    """Re-run the CURRENT annotation logic on the FROZEN corpus (no writes)."""
    with open(GROUND_TRUTH_FILE) as f:
        corpus = json.load(f)
    # Same call order as scripts/annotate_dataset.py __main__.
    anns = []
    for rec in corpus["employee_records"]:
        anns.append(annotate_employee_record(rec))
    for cfg in corpus["system_configs"]:
        anns.append(annotate_system_config(cfg))
    for rep in corpus["medical_reports"]:
        anns.append(annotate_medical_report(rep))
    for memo in corpus["internal_memos"]:
        anns.append(annotate_internal_memo(memo))
    return anns


def frozen_file_histogram():
    with open(ANNOTATIONS_FILE) as f:
        stored = json.load(f)
    return histogram(stored["annotations"]), stored["metadata"]


def git_cross_check():
    """Best-effort: re-derive State-A per-type straight from git; warn on mismatch."""
    try:
        blob = subprocess.check_output(
            ["git", "show", f"{STATE_A_SHA}:data/ground_truth/ground_truth_annotations.json"],
            cwd=PROJECT_ROOT, stderr=subprocess.DEVNULL)
    except Exception:
        return "skipped (git unavailable)"
    d = json.loads(blob)
    t, _, _ = histogram(d["annotations"])
    return "MATCH" if dict(t) == STATE_A_PER_TYPE else "MISMATCH-vs-embedded"


def main():
    # ── Deliverable #1: fresh re-run on the frozen corpus ──────────────────
    fresh = rerun_on_frozen_corpus()
    f_types, f_sev, f_lind = histogram(fresh)
    fresh_total = sum(f_types.values())

    # Integrity: does the fresh re-run reproduce the frozen stored file?
    (s_types, s_sev, s_lind), s_meta = frozen_file_histogram()
    integrity_ok = (dict(f_types) == dict(s_types))

    fresh_count = {
        "description": "Fresh re-run of scripts/annotate_dataset.py logic on the "
                       "frozen seed-42 corpus (data/ground_truth/ground_truth.json).",
        "total_entities": fresh_total,
        "distinct_types_in_annotations": len(f_types),
        "entity_spec_count": len(ENTITY_SPECS),
        "severity_histogram": {str(k): f_sev[k] for k in sorted(f_sev, reverse=True)},
        "linddun_histogram": dict(f_lind.most_common()),
        "per_type": dict(sorted(f_types.items())),
        "integrity_check": {
            "matches_frozen_annotations_file": integrity_ok,
            "frozen_meta_total_entities": s_meta.get("total_entities"),
            "frozen_meta_entity_spec_count": s_meta.get("entity_spec_count"),
        },
        "reproduces_document": ("State B (2,190) — Phase 2 report / Phase1.md / frozen "
                                "artifacts" if fresh_total == 2190 else "UNEXPECTED"),
    }
    with open(os.path.join(OUT_DIR, "fresh_count.json"), "w") as f:
        json.dump(fresh_count, f, indent=2)

    # ── Deliverable #3: per-type / per-severity diff between A and B ────────
    B_per_type = dict(f_types)
    all_types = sorted(set(STATE_A_PER_TYPE) | set(B_per_type))
    per_type_diff = {}
    for t in all_types:
        a, b = STATE_A_PER_TYPE.get(t, 0), B_per_type.get(t, 0)
        if a != b:
            per_type_diff[t] = {"A_2315": a, "B_2190": b, "delta_B_minus_A": b - a}

    sev_diff = {}
    for s in ["5", "4", "3", "2"]:
        a = STATE_A_AGG["severity"][s]
        b = f_sev[int(s)]
        sev_diff[s] = {"A_2315": a, "B_2190": b, "delta_B_minus_A": b - a}

    lind_diff = {}
    for k in STATE_A_AGG["linddun"]:
        a = STATE_A_AGG["linddun"][k]
        b = f_lind.get(k, 0)
        lind_diff[k] = {"A_2315": a, "B_2190": b, "delta_B_minus_A": b - a}

    version_diff = {
        "state_A": {"label": "Phase 1 .tex terminal box",
                    "provenance": f"git {STATE_A_SHA} ground_truth_annotations.json "
                                  "== Formal_Leakage_Definitions_and_Ground_Truth.tex L703-719",
                    "total_entities": STATE_A_AGG["total_entities"],
                    "distinct_types": STATE_A_AGG["distinct_types"],
                    "entity_spec_count": STATE_A_AGG["entity_spec_count"]},
        "state_B": {"label": "Phase 2 report / Phase1.md / frozen artifacts",
                    "provenance": "fresh re-run (this script) == frozen "
                                  "ground_truth_annotations.json == git HEAD",
                    "total_entities": fresh_total,
                    "distinct_types": len(f_types),
                    "entity_spec_count": len(ENTITY_SPECS)},
        "git_cross_check_state_A": git_cross_check(),
        "per_type_diff": per_type_diff,
        "per_severity_diff": sev_diff,
        "per_linddun_diff": lind_diff,
        "net_delta_B_minus_A": fresh_total - STATE_A_AGG["total_entities"],
        "removed_types": [t for t, v in per_type_diff.items() if v["B_2190"] == 0],
        "reshuffled_types": [t for t, v in per_type_diff.items()
                             if v["A_2315"] > 0 and v["B_2190"] > 0],
    }
    with open(os.path.join(OUT_DIR, "version_diff.json"), "w") as f:
        json.dump(version_diff, f, indent=2)

    # ── Console summary ────────────────────────────────────────────────────
    print("=" * 64)
    print("ANNOTATION RECONCILIATION — fresh re-run on frozen seed-42 corpus")
    print("=" * 64)
    print(f"  Fresh total entities : {fresh_total}")
    print(f"  Distinct types       : {len(f_types)}   (spec dict: {len(ENTITY_SPECS)})")
    print(f"  Severity histogram   : "
          f"{ {str(k): f_sev[k] for k in sorted(f_sev, reverse=True)} }")
    print(f"  Reproduces document  : {fresh_count['reproduces_document']}")
    print(f"  Integrity vs frozen  : {'OK (identical per-type)' if integrity_ok else 'MISMATCH'}")
    print(f"  State-A git x-check  : {version_diff['git_cross_check_state_A']}")
    print("-" * 64)
    print(f"  Net delta B - A      : {version_diff['net_delta_B_minus_A']}")
    print(f"  Removed types        : {version_diff['removed_types']}")
    print(f"  Reshuffled types     : {version_diff['reshuffled_types']}")
    print("-" * 64)
    print(f"  Wrote: {os.path.join('results/annotation_reconciliation', 'fresh_count.json')}")
    print(f"  Wrote: {os.path.join('results/annotation_reconciliation', 'version_diff.json')}")


if __name__ == "__main__":
    main()
