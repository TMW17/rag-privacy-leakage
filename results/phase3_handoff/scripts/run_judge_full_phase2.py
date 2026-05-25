#!/usr/bin/env python3
"""
run_judge_full_phase2.py
========================
Run LLMJudge(v2) on every turn across all Phase 2 log files and cache the
results to judge_verdicts_full.jsonl.

Log files processed
-------------------
  experiment_logs/B1_PILOT_pilot-B1-w3.jsonl    (17 turns)
  experiment_logs/B2_CLEAN_main-w3.jsonl         (246 turns)
  experiment_logs/B2_POISONED_poisoned-w4.jsonl  (21 turns)
  ─────────────────────────────────────────────
  Total: 284 turns (fresh run), ~$8.50 at claude-opus-4-7 pricing

Cache
-----
  results/judge_calibration/judge_verdicts_full.jsonl
  Separate from W5 calibration cache (judge_verdicts.jsonl).
  Re-running is safe: cached verdicts are skipped.

COST: ~$8–10 (range depends on response lengths).
"""

import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scripts.evaluation_engine import AttackerProfile
from scripts.llm_judge import LLMJudge

# ── Paths ──────────────────────────────────────────────────────────────────────
LOG_FILES = [
    ROOT / "experiment_logs" / "B1_PILOT_pilot-B1-w3.jsonl",
    ROOT / "experiment_logs" / "B2_CLEAN_main-w3.jsonl",
    ROOT / "experiment_logs" / "B2_POISONED_poisoned-w4.jsonl",
]
CACHE_PATH = ROOT / "results" / "judge_calibration" / "judge_verdicts_full.jsonl"

# ── Pricing (claude-opus-4-7) ─────────────────────────────────────────────────
_IN_RATE  = 15.0 / 1_000_000
_OUT_RATE = 75.0 / 1_000_000

# ── Minimum gap between API calls ─────────────────────────────────────────────
_RATE_LIMIT_S = 0.2

# ── Attacker profile string → enum ────────────────────────────────────────────
_PROFILE_MAP = {
    "Internal":   AttackerProfile.INTERNAL,
    "External":   AttackerProfile.EXTERNAL,
    "Admin":      AttackerProfile.ADMIN,
    "ThirdParty": AttackerProfile.THIRD_PARTY,
}


# =============================================================================
# Helpers
# =============================================================================

def _cache_key(rec: dict) -> str:
    """Stable, unique key for a single turn record."""
    return (
        f"{rec.get('run_id', '')}|"
        f"{rec['scenario_id']}|"
        f"{rec.get('run_index', 0)}|"
        f"{rec['turn_index']}"
    )


def _load_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def load_all_records() -> list[dict]:
    """Load every turn from all three log files."""
    all_records = []
    for path in LOG_FILES:
        if not path.exists():
            print(f"  WARNING: {path.relative_to(ROOT)} not found, skipping.")
            continue
        recs = _load_jsonl(path)
        print(f"  {path.name}: {len(recs)} turns")
        all_records.extend(recs)
    return all_records


def load_cache() -> dict[str, dict]:
    """Load existing cache. Returns {cache_key: entry_dict}."""
    if not CACHE_PATH.exists():
        return {}
    cache: dict[str, dict] = {}
    with CACHE_PATH.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    entry = json.loads(line)
                    key = entry.get("_cache_key", "")
                    if key:
                        cache[key] = entry
                except json.JSONDecodeError:
                    pass
    return cache


def _append_cache(entry: dict) -> None:
    """Append a single cache entry to the JSONL file."""
    with CACHE_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _max_severity(entities: list) -> int:
    """Max severity from judge disclosed_entities list."""
    return max((e.get("severity", 0) for e in entities), default=0)


# =============================================================================
# Main judge loop
# =============================================================================

def run_judge_loop(
    records: list[dict],
    cache: dict[str, dict],
    judge: LLMJudge,
) -> tuple[int, float]:
    """
    Judge every uncached turn.

    Returns
    -------
    (n_processed, total_cost_usd)
    """
    n_total     = len(records)
    n_cached    = sum(1 for r in records if _cache_key(r) in cache)
    n_to_do     = n_total - n_cached
    n_processed = 0
    total_cost  = 0.0
    t_start     = time.time()

    print(f"\nTurns total: {n_total}  cached: {n_cached}  to judge: {n_to_do}")

    if n_to_do == 0:
        print("All turns already cached — nothing to do.")
        return 0, 0.0

    for i, rec in enumerate(records):
        key = _cache_key(rec)
        if key in cache:
            continue

        response = rec.get("response", "")
        if not response:
            # Empty response: skip entirely to avoid wasting a call
            entry = {
                "_cache_key":     key,
                "run_id":         rec.get("run_id", ""),
                "scenario_id":    rec["scenario_id"],
                "run_index":      rec.get("run_index", 0),
                "turn_index":     rec["turn_index"],
                "attacker_profile": rec.get("attacker_profile", ""),
                "attack_family":  rec.get("attack_family", ""),
                "L_judge":        0,
                "leak_type_judge": "none",
                "severity_judge": 0,
                "rationale":      "skipped_empty_response",
                "input_tokens":   0,
                "output_tokens":  0,
                "latency_ms":     0,
                "cost_usd":       0.0,
            }
            cache[key] = entry
            _append_cache(entry)
            n_processed += 1
            continue

        profile_str = rec.get("attacker_profile", "External")
        profile_enum = _PROFILE_MAP.get(profile_str, AttackerProfile.EXTERNAL)

        verdict = judge.judge(
            response_text=response,
            profile=profile_enum,
        )

        call_cost = verdict.input_tokens * _IN_RATE + verdict.output_tokens * _OUT_RATE
        total_cost += call_cost

        entry = {
            "_cache_key":       key,
            "run_id":           rec.get("run_id", ""),
            "scenario_id":      rec["scenario_id"],
            "run_index":        rec.get("run_index", 0),
            "turn_index":       rec["turn_index"],
            "attacker_profile": profile_str,
            "attack_family":    rec.get("attack_family", ""),
            # ── Judge output ──────────────────────────────────────────────────
            "L_judge":          int(verdict.leak_detected),
            "leak_type_judge":  verdict.leak_type,
            "severity_judge":   _max_severity(verdict.disclosed_entities),
            "rationale":        verdict.rationale,
            "input_tokens":     verdict.input_tokens,
            "output_tokens":    verdict.output_tokens,
            "latency_ms":       verdict.latency_ms,
            "cost_usd":         round(call_cost, 6),
        }
        cache[key] = entry
        _append_cache(entry)
        n_processed += 1

        # Progress every 10 processed turns
        if n_processed % 10 == 0:
            elapsed = time.time() - t_start
            rate = n_processed / elapsed if elapsed > 0 else 0
            remaining = (n_to_do - n_processed) / rate if rate > 0 else 0
            print(
                f"  [{n_processed}/{n_to_do}] "
                f"cost so far: ${total_cost:.3f}  "
                f"elapsed: {elapsed:.0f}s  "
                f"eta: {remaining:.0f}s"
            )

        time.sleep(_RATE_LIMIT_S)

    return n_processed, total_cost


# =============================================================================
# Main
# =============================================================================

def main() -> int:
    print("=" * 65)
    print("run_judge_full_phase2.py — LLMJudge v2 full Phase 2 run")
    print("=" * 65)

    # ── Load records ───────────────────────────────────────────────────────────
    print("\nLoading log files:")
    records = load_all_records()
    print(f"Total turns loaded: {len(records)}")

    if not records:
        print("ERROR: No records found.", file=sys.stderr)
        return 1

    # ── Load existing cache ────────────────────────────────────────────────────
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    cache = load_cache()
    print(f"Cache loaded: {len(cache)} existing verdicts from {CACHE_PATH.relative_to(ROOT)}")

    # ── Initialise judge ───────────────────────────────────────────────────────
    try:
        judge = LLMJudge(prompt_version="v2")
    except (FileNotFoundError, EnvironmentError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    # ── Run judge loop ─────────────────────────────────────────────────────────
    n_processed, total_cost = run_judge_loop(records, cache, judge)

    # ── Final summary ──────────────────────────────────────────────────────────
    total_cached = len(cache)
    print()
    print("=" * 65)
    print("SUMMARY")
    print("=" * 65)
    print(f"  Turns processed this run : {n_processed}")
    print(f"  Total cache size         : {total_cached}")
    print(f"  Total cost this run      : ${total_cost:.4f}")

    # L_judge distribution
    all_entries = list(cache.values())
    l1_count = sum(1 for e in all_entries if e.get("L_judge", 0) == 1)
    l0_count = sum(1 for e in all_entries if e.get("L_judge", 0) == 0)
    print(f"\n  L_judge distribution (full cache):")
    print(f"    L=1 : {l1_count}")
    print(f"    L=0 : {l0_count}")

    # Leak-type distribution
    from collections import Counter
    lt_dist = Counter(e.get("leak_type_judge", "none") for e in all_entries)
    print(f"\n  leak_type_judge distribution:")
    for lt, cnt in sorted(lt_dist.items(), key=lambda x: -x[1]):
        print(f"    {lt:<20}: {cnt}")

    # Sanity checks
    print("\n--- Sanity checks ---")
    if total_cost > 12.0:
        print(f"  WARN: total cost ${total_cost:.2f} exceeds $12 threshold")
    else:
        print(f"  OK  : total cost ${total_cost:.2f} within expected range (< $12)")

    elapsed_total = time.time()
    print(f"\n  Cache written to: {CACHE_PATH.relative_to(ROOT)}")
    print("=" * 65)

    return 0


if __name__ == "__main__":
    sys.exit(main())
