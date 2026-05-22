#!/usr/bin/env python3
"""
build_annotation_triage.py
===========================
Transforms sample_46.jsonl + annotation_template.csv into a triage-friendly
spreadsheet for faster hand-annotation.

CRITICAL CONSTRAINT
-------------------
L_human, leak_type_human, severity_human, and notes columns are LEFT BLANK.
This script must NOT pre-fill, suggest, or hint at values for those columns.
Inter-annotator agreement (Cohen's kappa) requires that the human annotator's
labels are independent of any AI-generated labels.

Row ordering: EASY → MEDIUM → HARD (build confidence, then tackle harder cases).
Within each tier: alphabetical by stratum then record_id.

Inputs
------
  results/judge_calibration/sample_46.jsonl
  results/judge_calibration/annotation_template.csv   (kept as-is, not modified)

Output
------
  results/judge_calibration/annotation_triage.csv

Cost: $0 (no API calls).
"""

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT    = Path(__file__).parent.parent
IN_DIR  = ROOT / "results" / "judge_calibration"
JSONL   = IN_DIR / "sample_46.jsonl"
OUT_CSV = IN_DIR / "annotation_triage.csv"

# ── Refusal-start keywords (case-insensitive prefix match on first 100 chars) ──
_REFUSAL_STARTS = [
    "i cannot",
    "i'm sorry",
    "i'm not able",
    "i won't",
    "i will not",
    "i am not able",
    "i am sorry",
    "unable to",
]

# ── Partial-info markers: doc IDs, dollar amounts, capitalised name-pairs ──────
# Used to distinguish MIXED (refusal + info) from pure REFUSAL.
# Searched only after the first 200 chars to skip the opening refusal clause.
_RE_DOC_ID  = re.compile(r'\b(?:hr_file|sys_config|med_report|memo)_\d+\b')
_RE_DOLLAR  = re.compile(r'\$[\d,]+')
_RE_NAME    = re.compile(r'\b[A-Z][a-z]{1,20} [A-Z][a-z]{1,20}\b')


# =============================================================================
# Helpers
# =============================================================================

def _has_refusal_start(response: str) -> bool:
    """True if the response opens with a recognised refusal phrase."""
    prefix = response.lower().strip()[:100]
    return any(prefix.startswith(kw) for kw in _REFUSAL_STARTS)


def _has_partial_info(response: str) -> bool:
    """True if substantive info tokens appear after the opening 200 chars."""
    body = response[200:]
    return (
        bool(_RE_DOC_ID.search(body))
        or bool(_RE_DOLLAR.search(body))
        or bool(_RE_NAME.search(body))
    )


def _has_list_structure(response: str) -> bool:
    """True if the response contains a bulleted or numbered list."""
    return bool(
        re.search(r'\n\s*[-*•]\s', response)
        or re.search(r'\n\s*\d+\.\s', response)
    )


def compute_response_signal(response: str) -> str:
    """
    Assign a 1-word reading-shape signal based solely on structural features.
    Order of precedence: MIXED > LIST > REFUSAL > ANSWER.

    This is NOT a leak signal.  It describes the surface shape of the response
    so the annotator can allocate attention without being guided toward a verdict.
    """
    has_refusal = _has_refusal_start(response)
    has_partial = _has_partial_info(response)
    has_list    = _has_list_structure(response)

    if has_refusal and has_partial:
        return "MIXED"
    if has_list and not has_refusal:
        return "LIST"
    if has_refusal:
        return "REFUSAL"
    return "ANSWER"


def compute_clarity_tier(response: str) -> str:
    """
    Assign a reading-difficulty tier based on response length and structure.
    Does NOT use L_engine or any leak-related feature.

      EASY   — very short (<300 chars) AND pure refusal OR pure disclosure
      MEDIUM — mid-length (300–1000 chars), not a mixed case
      HARD   — long (>1000 chars) OR mixes refusal with partial info
    """
    n           = len(response)
    has_refusal = _has_refusal_start(response)
    has_partial = _has_partial_info(response)

    if n > 1000 or (has_refusal and has_partial):
        return "HARD"
    if 300 <= n <= 1000:
        return "MEDIUM"
    # < 300 chars
    return "EASY"


def _tier_sort_key(tier: str) -> int:
    return {"EASY": 0, "MEDIUM": 1, "HARD": 2}.get(tier, 9)


# =============================================================================
# Main
# =============================================================================

def main() -> int:
    # ── Load JSONL ──────────────────────────────────────────────────────────────
    if not JSONL.exists():
        print(f"ERROR: {JSONL} not found.", file=sys.stderr)
        return 1

    records = []
    with JSONL.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    if len(records) != 46:
        print(f"WARNING: expected 46 records, got {len(records)}", file=sys.stderr)

    # ── Build output rows ───────────────────────────────────────────────────────
    rows = []
    for r in records:
        response        = r.get("response", "")
        clarity_tier    = compute_clarity_tier(response)
        response_signal = compute_response_signal(response)

        # response_excerpt: collapse newlines, truncate to 600 chars
        excerpt = response.replace("\n", " ").replace("\r", "")
        if len(excerpt) > 600:
            excerpt = excerpt[:600] + "..."

        row = {
            # ── Context columns ──────────────────────────────────────────────
            "record_id":          r.get("record_id", ""),
            "stratum":            r.get("stratum", ""),
            "clarity_tier":       clarity_tier,
            "scenario_id":        r.get("scenario_id", ""),
            "attack_family":      r.get("attack_family", ""),
            "attacker_profile":   r.get("attacker_profile", ""),
            "query_one_line":     r.get("query", "")[:150].replace("\n", " ").replace("\r", ""),
            "response_signal":    response_signal,
            "response_excerpt":   excerpt,
            "full_response_link": f"see sample_46.jsonl record_id={r.get('record_id', '')}",
            # ── Human-annotation columns (BLANK) ──────────────────────────────
            "L_human":            "",
            "leak_type_human":    "",
            "severity_human":     "",
            "notes":              "",
            # ── Engine labels (at the end — hide while annotating) ────────────
            "L_engine":           r.get("L_engine", ""),
            "leak_type_engine":   r.get("leak_type_engine", ""),
        }
        rows.append(row)

    # ── Sort: EASY → MEDIUM → HARD, then stratum, then record_id ───────────────
    rows.sort(key=lambda r: (
        _tier_sort_key(r["clarity_tier"]),
        r["stratum"],
        r["record_id"],
    ))

    # ── Write CSV ───────────────────────────────────────────────────────────────
    fieldnames = [
        "record_id", "stratum", "clarity_tier",
        "scenario_id", "attack_family", "attacker_profile",
        "query_one_line", "response_signal", "response_excerpt",
        "full_response_link",
        "L_human", "leak_type_human", "severity_human", "notes",
        "L_engine", "leak_type_engine",
    ]

    IN_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # ==========================================================================
    # VERIFICATION
    # ==========================================================================
    print()
    print("=" * 65)
    print("VERIFICATION — annotation_triage.csv")
    print("=" * 65)

    # 1. Row count and tier breakdown
    tier_counts: dict = defaultdict(int)
    for row in rows:
        tier_counts[row["clarity_tier"]] += 1

    print(f"\n1. Total rows : {len(rows)}  (target: 46)")
    for tier in ["EASY", "MEDIUM", "HARD"]:
        print(f"   {tier:<7}: {tier_counts[tier]}")

    # 2. Blank-column check
    blank_cols   = ["L_human", "leak_type_human", "severity_human", "notes"]
    all_blank    = all(
        row[col] == ""
        for row in rows
        for col in blank_cols
    )
    print(f"\n2. Human annotation columns blank : {'YES — OK' if all_blank else 'NO — CRITICAL ERROR'}")
    if not all_blank:
        print("   CRITICAL: the following cells are non-blank:", file=sys.stderr)
        for col in blank_cols:
            violations = [row["record_id"] for row in rows if row[col] != ""]
            if violations:
                print(f"     {col}: {violations}", file=sys.stderr)

    # 3. Response-signal / L_engine correlation check
    #    For each signal value, compute P(L_engine=1 | signal).
    #    Warn if any P > 0.70 — the signal would then leak verdict information.
    print("\n3. Response-signal / L_engine correlation:")
    sig_total : dict = defaultdict(int)
    sig_pos   : dict = defaultdict(int)
    for row in rows:
        sig = row["response_signal"]
        sig_total[sig] += 1
        if str(row["L_engine"]) == "1":
            sig_pos[sig] += 1

    any_warn = False
    for sig in ["REFUSAL", "ANSWER", "MIXED", "LIST"]:
        total = sig_total.get(sig, 0)
        pos   = sig_pos.get(sig, 0)
        pct   = pos / total if total > 0 else 0.0
        warn  = "*** WARN >70% ***" if pct > 0.70 else "ok"
        print(f"   {sig:<10}: {pos}/{total} L=1  ({pct:.0%})  {warn}")
        if pct > 0.70:
            any_warn = True

    if any_warn:
        print("   NOTE: signal categories above 70% may subtly bias annotator.")
        print("   They are included as reading-shape helpers; annotator should")
        print("   be aware and focus on the response text itself.")

    # 4. Column order
    print(f"\n4. Column order ({len(fieldnames)} columns):")
    for i, col in enumerate(fieldnames, 1):
        tag = " ← BLANK" if col in blank_cols else (" ← engine (hide)" if col in ("L_engine", "leak_type_engine") else "")
        print(f"   {i:>2}. {col}{tag}")

    print(f"\n   → {OUT_CSV}")
    print("=" * 65)

    return 0 if (len(rows) == 46 and all_blank) else 1


if __name__ == "__main__":
    sys.exit(main())
