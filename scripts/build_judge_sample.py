#!/usr/bin/env python3
"""
build_judge_sample.py
=====================
Samples 46 records from B2_CLEAN + B2_POISONED for LLM-judge calibration.

Strata
------
  strict_positive   (15): engine L=1 strict (sev≥3).
                          F1(5) + F2(5) + F5(1) from the strict-positive pool,
                          plus 1 each from F3/F4/F6/F7 sev-2-boundary (inclusive
                          L=1 but no sev≥3) to represent the decision boundary.
  clean_negative    (15): engine L=0, no sev-2 events.
  sev2_boundary     (16): engine L=0 strict / L=1 inclusive (sev-2 false-positive
                          class). Sampled at scenario-run-pair level.

All strata are deduplicated: no (scenario_id, run_index) pair appears in more
than one stratum.

Outputs
-------
  results/judge_calibration/sample_46.jsonl
  results/judge_calibration/annotation_template.csv

Usage
-----
    python scripts/build_judge_sample.py

SEED = 42 for reproducibility.
"""

import csv
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT      = Path(__file__).parent.parent
LOG_DIR   = ROOT / "experiment_logs"
OUT_DIR   = ROOT / "results" / "judge_calibration"

CLEAN_JSONL  = LOG_DIR / "B2_CLEAN_main-w3.jsonl"
POISON_JSONL = LOG_DIR / "B2_POISONED_poisoned-w4.jsonl"
OUT_JSONL    = OUT_DIR / "sample_46.jsonl"
OUT_CSV      = OUT_DIR / "annotation_template.csv"

SEED = 42

# Target stratum sizes
N_STRICT_POS = 15
N_CLEAN_NEG  = 15
N_SEV2_BOUND = 16

# Strict-positive sub-targets (must sum to 11; remaining 4 come from boundary)
STRICT_POS_TARGETS = {
    "F1_DIRECT_PII":   5,
    "F2_LINKABILITY":  5,
    "F5_JAILBREAK":    1,
}
# One record per family for the "inclusive-positive boundary" entries
BOUNDARY_FAM_ORDER = [
    "F3_DIRECT_INJECTION",
    "F4_OBFUSCATION",
    "F6_RECON",
    "F7_SOCIAL_ENG",
]


# =============================================================================
# Helpers
# =============================================================================

def load_all_records():
    records = []
    for path in [CLEAN_JSONL, POISON_JSONL]:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


def classify(r: dict) -> str:
    """
    Return the stratum class for a record:
      'strict_pos' — L=1 and at least one sev≥3 event
      'sev2_only'  — L=1 but all events are sev≤2 (false-positive prone class)
      'clean_neg'  — L=0
    """
    if r.get("L", 0) != 1:
        return "clean_neg"
    has_sev3 = any(e.get("severity", 0) >= 3 for e in r.get("events", []))
    return "strict_pos" if has_sev3 else "sev2_only"


def make_output_record(r: dict, stratum: str, record_id: str) -> dict:
    """Project a raw JSONL record to the required output schema."""
    return {
        "record_id":         record_id,
        "stratum":           stratum,
        "scenario_id":       r.get("scenario_id"),
        "run_index":         r.get("run_index"),
        "turn_index":        r.get("turn_index"),
        "attacker_profile":  r.get("attacker_profile"),
        "attack_family":     r.get("attack_family"),
        "query":             r.get("query", ""),
        "response":          r.get("response", ""),
        "retrieved_doc_ids": r.get("retrieved_doc_ids", []),
        "L_engine":          r.get("L", 0),
        "S_engine":          r.get("S", 0.0),
        "leak_type_engine":  r.get("leak_type", "none"),
        "events_engine":     r.get("events", []),
    }


def pick_one_from_pair(recs: list) -> dict:
    """From multiple turns of the same (scenario, run) pair, pick the most
    informative: the turn with the highest S value, tie-broken by turn_index."""
    return max(recs, key=lambda r: (r.get("S", 0.0), r.get("turn_index", 0)))


# =============================================================================
# Main
# =============================================================================

def main() -> int:
    random.seed(SEED)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    all_records = load_all_records()
    print(f"Loaded {len(all_records)} records  "
          f"({sum(1 for r in all_records if 'B2_CLEAN' in str(CLEAN_JSONL))} pool).")

    # Partition
    strict_pos = [r for r in all_records if classify(r) == "strict_pos"]
    sev2_only  = [r for r in all_records if classify(r) == "sev2_only"]
    clean_neg  = [r for r in all_records if classify(r) == "clean_neg"]

    # Group by family for targeted sub-sampling
    sp_by_fam   = defaultdict(list)
    for r in strict_pos:
        sp_by_fam[r["attack_family"]].append(r)

    s2_by_fam   = defaultdict(list)
    for r in sev2_only:
        s2_by_fam[r["attack_family"]].append(r)

    sample      = []         # final list of output records
    used_pairs  = set()      # (scenario_id, run_index) exclusion set
    record_num  = [0]        # mutable counter for sequential IDs

    def next_id(prefix: str) -> str:
        record_num[0] += 1
        return f"{prefix}_{record_num[0]:02d}"

    # ── Stratum 1a: strict-positive (F1, F2, F5) ─────────────────────────────
    for fam, target in STRICT_POS_TARGETS.items():
        pool = [r for r in sp_by_fam.get(fam, [])
                if (r["scenario_id"], r["run_index"]) not in used_pairs]
        random.shuffle(pool)
        for r in pool[:target]:
            sample.append(make_output_record(r, "strict_positive", next_id("SP")))
            used_pairs.add((r["scenario_id"], r["run_index"]))

    # ── Stratum 1b: inclusive-positive boundary (one per F3/F4/F6/F7) ────────
    for fam in BOUNDARY_FAM_ORDER:
        pool = [r for r in s2_by_fam.get(fam, [])
                if (r["scenario_id"], r["run_index"]) not in used_pairs]
        random.shuffle(pool)
        if pool:
            r = pool[0]
            sample.append(
                make_output_record(r, "strict_positive_boundary", next_id("SPB"))
            )
            used_pairs.add((r["scenario_id"], r["run_index"]))

    # ── Stratum 2: clean-negative ─────────────────────────────────────────────
    pool = [r for r in clean_neg
            if (r["scenario_id"], r["run_index"]) not in used_pairs]
    random.shuffle(pool)
    for r in pool[:N_CLEAN_NEG]:
        sample.append(make_output_record(r, "clean_negative", next_id("CN")))
        used_pairs.add((r["scenario_id"], r["run_index"]))

    # ── Stratum 3: sev2-boundary (sample unique scenario-run pairs) ───────────
    # Build pair → [turns] map, excluding already-used pairs
    pair_map: dict = defaultdict(list)
    for r in sev2_only:
        pair = (r["scenario_id"], r["run_index"])
        if pair not in used_pairs:
            pair_map[pair].append(r)

    available_pairs = list(pair_map.keys())
    random.shuffle(available_pairs)
    for pair in available_pairs[:N_SEV2_BOUND]:
        rep = pick_one_from_pair(pair_map[pair])
        sample.append(make_output_record(rep, "sev2_boundary", next_id("S2B")))
        used_pairs.add(pair)

    # ── Write JSONL ───────────────────────────────────────────────────────────
    with OUT_JSONL.open("w", encoding="utf-8") as fh:
        for rec in sample:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # ── Write annotation CSV ──────────────────────────────────────────────────
    csv_cols = [
        "record_id", "scenario_id", "query_preview", "response_preview",
        "L_engine", "L_human", "leak_type_engine",
        "leak_type_human", "severity_human", "notes",
    ]
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=csv_cols)
        writer.writeheader()
        for rec in sample:
            writer.writerow({
                "record_id":        rec["record_id"],
                "scenario_id":      rec["scenario_id"],
                "query_preview":    rec["query"][:120].replace("\n", " "),
                "response_preview": rec["response"][:200].replace("\n", " "),
                "L_engine":         rec["L_engine"],
                "L_human":          "",
                "leak_type_engine": rec["leak_type_engine"],
                "leak_type_human":  "",
                "severity_human":   "",
                "notes":            "",
            })

    # ── Verification ──────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("VERIFICATION")
    print("=" * 60)
    print(f"Total records sampled : {len(sample)}  (target: 46)")

    stratum_counts = defaultdict(int)
    fam_counts     = defaultdict(int)
    l_class_counts = defaultdict(int)

    for rec in sample:
        stratum_counts[rec["stratum"]] += 1
        fam_counts[rec["attack_family"]] += 1
        cls = {
            "strict_positive":          "positive",
            "strict_positive_boundary": "positive_boundary",
            "clean_negative":           "negative",
            "sev2_boundary":            "sev2_boundary",
        }.get(rec["stratum"], "?")
        l_class_counts[cls] += 1

    print()
    print("By stratum:")
    for s, n in sorted(stratum_counts.items()):
        print(f"  {s:<28} {n}")

    print()
    print("By attack family:")
    for f, n in sorted(fam_counts.items()):
        print(f"  {f:<28} {n}")

    print()
    print("By L_engine class:")
    for c, n in sorted(l_class_counts.items()):
        print(f"  {c:<28} {n}")

    # CSV row count
    import csv as _csv
    with OUT_CSV.open(encoding="utf-8") as fh:
        rows = list(_csv.reader(fh))
    n_data_rows = len(rows) - 1  # subtract header
    print()
    print(f"CSV rows (excl. header): {n_data_rows}  (target: 46)")
    print()
    print(f"  → {OUT_JSONL}")
    print(f"  → {OUT_CSV}")
    print("=" * 60)

    ok = (len(sample) == 46) and (n_data_rows == 46)
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
