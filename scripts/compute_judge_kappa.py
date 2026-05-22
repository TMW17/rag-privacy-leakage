#!/usr/bin/env python3
"""
compute_judge_kappa.py
======================
Computes Cohen's kappa between three label sources for the 46
hand-annotated calibration records:

  1. Engine  — evaluation_engine.py (regex/NER pipeline)
  2. Judge   — LLMJudge(prompt_version="v2") / Claude Opus 4.7
  3. Human   — annotation_triage.csv (hand labels)

Outputs
-------
  results/judge_calibration/kappa_results.json
  results/judge_calibration/kappa_summary.md
  results/judge_calibration/disagreement_matrix.csv
  results/judge_calibration/judge_verdicts.jsonl  (API call cache)

Usage
-----
    python scripts/compute_judge_kappa.py

API cost estimate: ~$1.25 for 46 fresh judge calls.
Re-runs are free if judge_verdicts.jsonl cache is present.
"""

import csv
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

# ── .env load must precede any os.environ access ───────────────────────────────
from dotenv import load_dotenv
load_dotenv()

# ── Path bootstrap ─────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from sklearn.metrics import cohen_kappa_score

from scripts.llm_judge import LLMJudge
from scripts.evaluation_engine import AttackerProfile

# =============================================================================
# Paths
# =============================================================================

_CALIB_DIR    = ROOT / "results" / "judge_calibration"
_JSONL_PATH   = _CALIB_DIR / "sample_46.jsonl"
_TRIAGE_PATH  = _CALIB_DIR / "annotation_triage.csv"
_KAPPA_JSON   = _CALIB_DIR / "kappa_results.json"
_KAPPA_MD     = _CALIB_DIR / "kappa_summary.md"
_DISAGREE_CSV = _CALIB_DIR / "disagreement_matrix.csv"
_VERDICTS     = _CALIB_DIR / "judge_verdicts.jsonl"

_PROFILE_MAP = {
    "Internal":   AttackerProfile.INTERNAL,
    "External":   AttackerProfile.EXTERNAL,
    "Admin":      AttackerProfile.ADMIN,
    "ThirdParty": AttackerProfile.THIRD_PARTY,
}

# Opus 4.7 pricing
_IN_RATE  = 15.0 / 1_000_000
_OUT_RATE = 75.0 / 1_000_000

KAPPA_PASS = 0.60

_KAPPA_LABELS = [
    (0.80, "Almost perfect"),
    (0.61, "Substantial"),
    (0.41, "Moderate"),
    (0.21, "Fair"),
    (0.00, "Poor"),
]


# =============================================================================
# Helpers
# =============================================================================

def _interp(k: float) -> str:
    if k != k:   # NaN guard
        return "undefined"
    for threshold, label in _KAPPA_LABELS:
        if k >= threshold:
            return label
    return "Poor"


def _safe_kappa(y1, y2, weights=None) -> float:
    """cohen_kappa_score with NaN fallback on degenerate inputs."""
    try:
        return float(cohen_kappa_score(y1, y2, weights=weights))
    except Exception as exc:
        print(f"  WARNING kappa({weights}): {exc}", file=sys.stderr)
        return float("nan")


# =============================================================================
# Step 1 — Load human annotations
# =============================================================================

def load_human(path: Path) -> dict:
    """Return {record_id: {L_human, leak_type_human, severity_human, notes}}."""
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    result = {}
    blanks = []

    for row in rows:
        rid  = row["record_id"].strip()
        l_h  = row.get("L_human", "").strip()
        lt_h = row.get("leak_type_human", "").strip()
        sv_h = row.get("severity_human", "").strip()

        if not l_h or not lt_h or not sv_h:
            blanks.append(rid)
            continue

        result[rid] = {
            "L_human":         int(l_h),
            "leak_type_human": lt_h,
            "severity_human":  int(sv_h),
            "notes":           row.get("notes", "").strip(),
        }

    if blanks:
        print(
            f"ABORT: {len(blanks)} rows in {path.name} have blank annotations:\n"
            f"  {blanks[:10]}",
            file=sys.stderr,
        )
        sys.exit(1)

    return result


# =============================================================================
# Step 2 — Load engine labels
# =============================================================================

def load_engine(path: Path) -> dict:
    """Return {record_id: engine metadata + labels}."""
    result = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r   = json.loads(line)
            rid = r["record_id"]
            events = r.get("events_engine") or []
            sev = max((e.get("severity", 0) for e in events), default=0)
            result[rid] = {
                "record_id":        rid,
                "stratum":          r.get("stratum", ""),
                "scenario_id":      r.get("scenario_id", ""),
                "attack_family":    r.get("attack_family", ""),
                "attacker_profile": r.get("attacker_profile", ""),
                "response":         r.get("response", ""),
                "L_engine":         int(r.get("L_engine", 0)),
                "leak_type_engine": r.get("leak_type_engine", "none"),
                "severity_engine":  sev,
            }
    return result


# =============================================================================
# Step 3 — Run LLM judge (with file cache)
# =============================================================================

def _load_cache() -> dict:
    if not _VERDICTS.exists():
        return {}
    cache = {}
    with _VERDICTS.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                obj = json.loads(line)
                cache[obj["record_id"]] = obj
    return cache


def run_judge(engine_records: dict, cache: dict) -> dict:
    """Run LLMJudge(v2) on all records; use cache where available."""
    judge      = LLMJudge(prompt_version="v2")
    verdicts   = {}
    new_cache  = []
    cost_total = 0.0
    rids       = sorted(engine_records.keys())
    total      = len(rids)

    print(f"  Running judge on {total} records "
          f"({len(cache)} cached, {total - len(cache)} fresh API calls)...")

    for i, rid in enumerate(rids, 1):
        # ── Cache hit ──────────────────────────────────────────────────────────
        if rid in cache:
            verdicts[rid] = cache[rid]
            print(f"  [{i:2d}/{total}] {rid}  [cached]")
            continue

        # ── Fresh API call ─────────────────────────────────────────────────────
        rec         = engine_records[rid]
        profile_str = rec["attacker_profile"]
        profile     = _PROFILE_MAP.get(profile_str)

        if profile is None:
            print(f"  WARNING: unknown profile {profile_str!r} for {rid}", file=sys.stderr)
            entry = {
                "record_id":       rid,
                "L_judge":         0,
                "leak_type_judge": "none",
                "severity_judge":  0,
                "error":           f"unknown_profile:{profile_str}",
            }
            verdicts[rid] = entry
            new_cache.append(entry)
            continue

        verdict = judge.judge(response_text=rec["response"], profile=profile)

        # Severity: use entities only when leak_detected=True (edge case from spec)
        entities = verdict.disclosed_entities if verdict.leak_detected else []
        sev_j    = max((e.get("severity", 0) for e in entities), default=0)

        # JSON-parse-fail guard: llm_judge already returns a safe fallback verdict
        # with rationale="json_parse_failed".  We log and accept.
        if "json_parse_failed" in verdict.rationale:
            print(f"  WARNING: JSON parse failed for {rid}", file=sys.stderr)

        entry = {
            "record_id":       rid,
            "L_judge":         1 if verdict.leak_detected else 0,
            "leak_type_judge": verdict.leak_type,
            "severity_judge":  sev_j,
            "latency_ms":      verdict.latency_ms,
            "input_tokens":    verdict.input_tokens,
            "output_tokens":   verdict.output_tokens,
            "rationale":       verdict.rationale,
        }
        verdicts[rid] = entry
        new_cache.append(entry)

        call_cost   = verdict.input_tokens * _IN_RATE + verdict.output_tokens * _OUT_RATE
        cost_total += call_cost

        print(f"  [{i:2d}/{total}] {rid}  L_judge={entry['L_judge']} "
              f"type={entry['leak_type_judge']!r} sev={entry['severity_judge']} "
              f"latency={verdict.latency_ms}ms  cost≈${call_cost:.4f}")

        time.sleep(0.2)   # gentle rate limiting

    # ── Persist new cache entries ──────────────────────────────────────────────
    if new_cache:
        _CALIB_DIR.mkdir(parents=True, exist_ok=True)
        with _VERDICTS.open("a", encoding="utf-8") as fh:
            for entry in new_cache:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        print(f"  → {len(new_cache)} new verdicts cached → {_VERDICTS.name}")

    if cost_total > 0:
        print(f"  → API cost this run: ≈${cost_total:.4f}")

    return verdicts


# =============================================================================
# Step 4 — Aligned vectors
# =============================================================================

def build_vectors(engine: dict, judge: dict, human: dict, rids: list) -> dict:
    """
    Return aligned lists for kappa computation.
    Severity rule: use 0 when L=0 for the rater in question (consistent baseline).
    """
    l_e, l_j, l_h   = [], [], []
    lt_e, lt_j, lt_h = [], [], []
    sv_e, sv_j, sv_h = [], [], []

    for rid in rids:
        e = engine[rid]; jv = judge[rid]; h = human[rid]

        le = e["L_engine"]; lj = jv["L_judge"]; lh = h["L_human"]
        l_e.append(le); l_j.append(lj); l_h.append(lh)

        lt_e.append(e["leak_type_engine"])
        lt_j.append(jv["leak_type_judge"])
        lt_h.append(h["leak_type_human"])

        sv_e.append(e["severity_engine"] if le == 1 else 0)
        sv_j.append(jv["severity_judge"]  if lj == 1 else 0)
        sv_h.append(h["severity_human"]   if lh == 1 else 0)

    return {
        "l_e": l_e, "l_j": l_j, "l_h": l_h,
        "lt_e": lt_e, "lt_j": lt_j, "lt_h": lt_h,
        "sv_e": sv_e, "sv_j": sv_j, "sv_h": sv_h,
    }


def compute_all_kappas(v: dict) -> dict:
    binary = {
        "engine_vs_human": _safe_kappa(v["l_e"],  v["l_h"]),
        "judge_vs_human":  _safe_kappa(v["l_j"],  v["l_h"]),
        "engine_vs_judge": _safe_kappa(v["l_e"],  v["l_j"]),
    }
    severity = {
        "engine_vs_human": _safe_kappa(v["sv_e"], v["sv_h"], weights="quadratic"),
        "judge_vs_human":  _safe_kappa(v["sv_j"], v["sv_h"], weights="quadratic"),
        "engine_vs_judge": _safe_kappa(v["sv_e"], v["sv_j"], weights="quadratic"),
    }
    categorical = {
        "engine_vs_human": _safe_kappa(v["lt_e"], v["lt_h"]),
        "judge_vs_human":  _safe_kappa(v["lt_j"], v["lt_h"]),
        "engine_vs_judge": _safe_kappa(v["lt_e"], v["lt_j"]),
    }
    return {"binary": binary, "severity": severity, "categorical": categorical}


# =============================================================================
# Step 5 — Disagreement matrix
# =============================================================================

_DIS_FIELDS = [
    "record_id", "scenario_id", "attack_family",
    "L_engine", "L_judge", "L_human",
    "leak_type_engine", "leak_type_judge", "leak_type_human",
    "severity_engine", "severity_judge", "severity_human",
    "all_three_agree", "judge_matches_human", "engine_matches_human",
]


def build_disagreement(engine: dict, judge: dict, human: dict, rids: list) -> list:
    rows = []
    for rid in rids:
        e = engine[rid]; jv = judge[rid]; h = human[rid]
        le = e["L_engine"]; lj = jv["L_judge"]; lh = h["L_human"]
        rows.append({
            "record_id":            rid,
            "scenario_id":          e["scenario_id"],
            "attack_family":        e["attack_family"],
            "L_engine":             le,
            "L_judge":              lj,
            "L_human":              lh,
            "leak_type_engine":     e["leak_type_engine"],
            "leak_type_judge":      jv["leak_type_judge"],
            "leak_type_human":      h["leak_type_human"],
            "severity_engine":      e["severity_engine"] if le == 1 else 0,
            "severity_judge":       jv["severity_judge"]  if lj == 1 else 0,
            "severity_human":       h["severity_human"]   if lh == 1 else 0,
            "all_three_agree":      int(le == lj == lh),
            "judge_matches_human":  int(lj == lh),
            "engine_matches_human": int(le == lh),
        })
    return rows


# =============================================================================
# Step 6 — kappa_summary.md
# =============================================================================

def _kappa_table(kappas: dict, title: str) -> str:
    lines = [f"### {title}", ""]
    lines.append("| Comparison           | κ       | Interpretation  | PASS (≥0.60) |")
    lines.append("|----------------------|---------|-----------------|--------------|")
    for comp, k in kappas.items():
        if k != k:   # NaN
            kstr, flag, interp = "   NaN", "—", "undefined"
        else:
            kstr  = f"{k:+.4f}"
            flag  = "✓ PASS" if k >= KAPPA_PASS else "✗ FAIL"
            interp = _interp(k)
        lines.append(f"| {comp:<20} | {kstr} | {interp:<15} | {flag:<12} |")
    return "\n".join(lines)


def build_summary_md(kappas: dict, vectors: dict, dis_rows: list) -> str:
    n = len(vectors["l_e"])
    le_dist  = Counter(vectors["l_e"])
    lj_dist  = Counter(vectors["l_j"])
    lh_dist  = Counter(vectors["l_h"])

    b = kappas["binary"]
    s = kappas["severity"]
    c = kappas["categorical"]

    all_agree   = sum(1 for r in dis_rows if r["all_three_agree"])
    jh_agree    = sum(1 for r in dis_rows if r["judge_matches_human"])
    eh_agree    = sum(1 for r in dis_rows if r["engine_matches_human"])

    # Top 5 judge–human disagreements
    disagree = sorted(
        (r for r in dis_rows if not r["judge_matches_human"]),
        key=lambda r: (r["scenario_id"], r["record_id"]),
    )[:5]

    evh = b["engine_vs_human"]
    jvh = b["judge_vs_human"]

    lines = [
        "# W5 LLM-Judge Calibration — Kappa Results",
        "",
        "## 1. Sample Description",
        "",
        f"- **Records:** {n} (stratified sample from `sample_46.jsonl`)",
        f"- **Engine (L=1):** {le_dist[1]}/{n}  |  "
          f"**Judge (L=1):** {lj_dist[1]}/{n}  |  "
          f"**Human (L=1):** {lh_dist[1]}/{n}",
        "",
        "---",
        "",
        "## 2. Cohen's Kappa",
        "",
        _kappa_table(b, "2.1 Binary Kappa (L value)"),
        "",
        _kappa_table(s, "2.2 Severity Kappa (quadratic weights; L=0 → severity=0)"),
        "",
        _kappa_table(c, "2.3 Categorical Kappa (leak_type)"),
        "",
        "---",
        "",
        "## 3. Top Judge–Human Disagreements",
        "",
    ]

    if disagree:
        lines.append(
            "| record_id | scenario_id | L_judge | L_human | "
            "leak_type_judge | leak_type_human |"
        )
        lines.append(
            "|-----------|-------------|---------|---------|"
            "-----------------|-----------------|"
        )
        for r in disagree:
            lines.append(
                f"| {r['record_id']} | {r['scenario_id']} "
                f"| {r['L_judge']} | {r['L_human']} "
                f"| {r['leak_type_judge']} | {r['leak_type_human']} |"
            )
    else:
        lines.append("*Judge and human agree on all records.*")

    lines += ["", "---", "", "## 4. Interpretation", ""]

    # Interpretation prose per spec
    if evh == evh and evh < 0.40:
        lines.append(
            f"- **Engine–human κ={evh:+.3f} validates the sev-2 false-positive hypothesis.** "
            "The deterministic engine (ASR_inclusive) fires on sev=2 department-name entities "
            "present in refusal explanations for the External profile (threshold=0). "
            "Human annotators correctly excluded these category labels, confirming that "
            "ASR_strict is the defensible headline metric for the thesis."
        )

    if evh == evh and jvh == jvh and jvh > evh:
        lines.append(
            f"- **Judge tracks human better than engine** "
            f"(judge–human κ={jvh:+.3f} > engine–human κ={evh:+.3f}). "
            "The LLM judge's contextual reading aligns more closely with human judgment "
            "than the regex/NER pipeline, supporting its use as a supplementary evaluator "
            "in Phase 2 augmented metrics."
        )
    elif evh == evh and jvh == jvh:
        lines.append(
            f"- Engine and judge show comparable alignment with human ground truth "
            f"(engine–human κ={evh:+.3f}, judge–human κ={jvh:+.3f})."
        )

    if jvh == jvh:
        if jvh >= KAPPA_PASS:
            lines.append(
                f"- **Judge calibration PASSES** (κ={jvh:+.3f} ≥ {KAPPA_PASS}). "
                "Acceptable for augmented-metrics use in Phase 2 W6.1."
            )
        else:
            lines.append(
                f"- **Judge calibration FAILS** (κ={jvh:+.3f} < {KAPPA_PASS}). "
                "Consider iterating the judge prompt to v3 before W6.1 use."
            )

    lines += [
        "",
        "---",
        "",
        "## 5. Agreement Summary",
        "",
        "| Measure                | Count | Rate  |",
        "|------------------------|-------|-------|",
        f"| All three agree        | {all_agree:>5} | {all_agree/n:.1%} |",
        f"| Judge matches human    | {jh_agree:>5} | {jh_agree/n:.1%} |",
        f"| Engine matches human   | {eh_agree:>5} | {eh_agree/n:.1%} |",
        f"| At least one disagrees | {n-all_agree:>5} | {(n-all_agree)/n:.1%} |",
    ]

    return "\n".join(lines)


# =============================================================================
# Main
# =============================================================================

def main() -> int:
    print("=" * 65)
    print("compute_judge_kappa.py  —  W5 LLM-Judge Calibration")
    print("=" * 65)
    print()

    # ── 1. Human annotations ──────────────────────────────────────────────────
    print("1. Loading human annotations from annotation_triage.csv ...")
    human = load_human(_TRIAGE_PATH)
    print(f"   {len(human)} rows, all annotated.  "
          f"L=1: {sum(v['L_human'] for v in human.values())}, "
          f"L=0: {sum(1-v['L_human'] for v in human.values())}")

    # ── 2. Engine labels ──────────────────────────────────────────────────────
    print("2. Loading engine labels from sample_46.jsonl ...")
    engine = load_engine(_JSONL_PATH)
    print(f"   {len(engine)} records.  "
          f"L=1: {sum(v['L_engine'] for v in engine.values())}, "
          f"L=0: {sum(1-v['L_engine'] for v in engine.values())}")

    # ── Alignment check ───────────────────────────────────────────────────────
    in_engine_not_human = [r for r in engine if r not in human]
    in_human_not_engine = [r for r in human  if r not in engine]
    if in_engine_not_human or in_human_not_engine:
        print("ABORT: record_id mismatch between JSONL and CSV.", file=sys.stderr)
        if in_engine_not_human:
            print(f"  In JSONL but not CSV: {in_engine_not_human}", file=sys.stderr)
        if in_human_not_engine:
            print(f"  In CSV but not JSONL: {in_human_not_engine}", file=sys.stderr)
        return 1

    record_ids = sorted(engine.keys())

    # ── 3. Judge verdicts ─────────────────────────────────────────────────────
    print("3. Running LLM judge (prompt_version=v2, model=claude-opus-4-7) ...")
    cache  = _load_cache()
    judge  = run_judge(engine, cache)
    print(f"   L=1: {sum(v['L_judge'] for v in judge.values())}, "
          f"L=0: {sum(1-v['L_judge'] for v in judge.values())}")

    # ── 4. Kappa computation ──────────────────────────────────────────────────
    print("4. Computing Cohen's kappa ...")
    vectors = build_vectors(engine, judge, human, record_ids)
    kappas  = compute_all_kappas(vectors)

    # ── 5. Disagreement matrix ────────────────────────────────────────────────
    print("5. Building disagreement_matrix.csv ...")
    dis_rows = build_disagreement(engine, judge, human, record_ids)
    with _DISAGREE_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_DIS_FIELDS)
        writer.writeheader()
        writer.writerows(dis_rows)

    # ── 6. Write JSON + markdown ──────────────────────────────────────────────
    print("6. Writing kappa_results.json and kappa_summary.md ...")

    json_data = {
        "sample_size": len(record_ids),
        "kappas": kappas,
        "label_distributions": {
            "L_engine": {"0": vectors["l_e"].count(0), "1": vectors["l_e"].count(1)},
            "L_judge":  {"0": vectors["l_j"].count(0), "1": vectors["l_j"].count(1)},
            "L_human":  {"0": vectors["l_h"].count(0), "1": vectors["l_h"].count(1)},
        },
        "agreement": {
            "all_three_agree":     sum(1 for r in dis_rows if r["all_three_agree"]),
            "judge_matches_human": sum(1 for r in dis_rows if r["judge_matches_human"]),
            "engine_matches_human":sum(1 for r in dis_rows if r["engine_matches_human"]),
        },
    }
    with _KAPPA_JSON.open("w", encoding="utf-8") as fh:
        json.dump(json_data, fh, indent=2)

    md = build_summary_md(kappas, vectors, dis_rows)
    _KAPPA_MD.write_text(md, encoding="utf-8")

    # ── 7. Stdout summary ─────────────────────────────────────────────────────
    print()
    print("=" * 65)
    print("RESULTS")
    print("=" * 65)

    for metric_name, metric_kappas in kappas.items():
        print(f"\n  {metric_name.upper().replace('_', ' ')}")
        for comp, k in metric_kappas.items():
            if k != k:   # NaN
                print(f"    {comp:<22}  κ=  NaN  [—]  undefined")
            else:
                flag = "PASS" if k >= KAPPA_PASS else "FAIL"
                print(f"    {comp:<22}  κ={k:+.4f}  [{flag}]  {_interp(k)}")

    print()
    n = len(record_ids)
    all_a = json_data["agreement"]["all_three_agree"]
    jh    = json_data["agreement"]["judge_matches_human"]
    eh    = json_data["agreement"]["engine_matches_human"]
    print(f"  All three agree   : {all_a}/{n}  ({all_a/n:.1%})")
    print(f"  Judge == human    : {jh}/{n}  ({jh/n:.1%})")
    print(f"  Engine == human   : {eh}/{n}  ({eh/n:.1%})")

    print()
    print(f"  → {_KAPPA_JSON}")
    print(f"  → {_KAPPA_MD}")
    print(f"  → {_DISAGREE_CSV}")
    print(f"  → {_VERDICTS}")
    print("=" * 65)

    # Exit code: 0 if judge_vs_human binary kappa >= threshold
    jvh = kappas["binary"]["judge_vs_human"]
    return 0 if (jvh == jvh and jvh >= KAPPA_PASS) else 1


if __name__ == "__main__":
    sys.exit(main())
