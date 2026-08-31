#!/usr/bin/env python3
"""
a5_cache_miss_identify.py -- find every judge-cache miss in the ablation, and resolve as many
as possible for FREE before any call is billed.

A "miss" is an ablation turn whose (profile, response) content address is absent from
results/phase3/ablation/judged/judge_cache.jsonl. The published scorer treats a miss as
L_judge=0, severity=0, so every miss biases its cell's judged rate DOWNWARD -- and the
baseline has zero misses, so the bias runs one way, inflating the apparent reduction.

FREE RESOLUTION comes first. Two sources can settle a miss without an API call:
  (a) the ablation cache itself, under the same content address (a genuine miss cannot be
      resolved this way, but the check is what proves it is genuine);
  (b) the LOCKED Phase-2 verdict set. Those verdicts are keyed positionally, so this script
      re-derives each locked verdict's CONTENT address from the baseline log row it belongs
      to, building a content index over already-judged responses. If a defended cell emitted
      a byte-identical response to a baseline turn -- which is expected wherever a layer did
      not fire -- the existing verdict applies and no call is needed.

This script BILLS NOTHING. It identifies, resolves what it can for free, prices the rest, and
stops. a5_cache_miss_judge.py performs the run after explicit approval.

Emits analysis/partA/out/a5_cache_miss_identify.json + a5_cache_misses.csv.
Run:  python3 analysis/partA/scripts/a5_cache_miss_identify.py
"""
import csv
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib_partA as L  # noqa: E402

CELLS = ["C10000", "C01000", "C00100", "C01100", "C11111"]
IN_RATE, OUT_RATE = 15.0 / 1e6, 75.0 / 1e6      # Opus 4.7, as in judge_ablation.py
EXPECTED = {"C00100": 8, "C10000": 5, "C01000": 4, "C01100": 4, "C11111": 1}


def main():
    guard = L.verify_scorer_matches_published()
    assert guard["all_match"], "published scorer changed -- HALT"

    cache = {e["_judge_key"]: e for e in L.load_jsonl("ablation_judge_cache")}

    # content index over the LOCKED verdicts: re-derive each one's content address
    base_rows = L.load_jsonl("orig_clean") + L.load_jsonl("orig_poison")
    locked = {f"{v['run_id']}|{v['scenario_id']}|{v['run_index']}|{v['turn_index']}": v
              for v in L.load_jsonl("locked_verdicts")}
    locked_by_content = {}
    for r in base_rows:
        k = f"{r.get('run_id','')}|{r['scenario_id']}|{r.get('run_index')}|{r['turn_index']}"
        v = locked.get(k)
        if v is None:
            continue
        locked_by_content.setdefault(
            L.judge_key(r["attacker_profile"], r.get("response", "")), v)

    misses, per_cell = [], defaultdict(lambda: {"turns": 0, "miss": 0, "free": 0, "bill": 0})
    for c in CELLS:
        for r in L.load_jsonl(f"results/phase3/ablation/engine/{c}.jsonl"):
            per_cell[c]["turns"] += 1
            resp = r.get("response", "")
            key = L.judge_key(r["attacker_profile"], resp)
            if key in cache:
                continue
            per_cell[c]["miss"] += 1
            lv = locked_by_content.get(key)
            if lv is not None:
                per_cell[c]["free"] += 1
                res, src = "FREE_from_locked_verdict", "locked Phase-2 verdict, identical response"
            else:
                per_cell[c]["bill"] += 1
                res, src = "NEEDS_LIVE_CALL", ""
            misses.append({
                "cell": c, "scenario_id": r["scenario_id"], "run_index": r.get("run_index"),
                "turn_index": r["turn_index"], "profile": r["attacker_profile"],
                "family": r["attack_family"], "judge_key": key,
                "response_len": len(resp), "response_empty": int(not resp.strip()),
                "engine_strict": L.engine_strict_turn(r),
                "resolution": res, "free_source": src,
                "resolved_L_judge": (int(lv.get("L_judge", 0) or 0) if lv else None),
                "resolved_severity_judge": (int(lv.get("severity_judge", 0) or 0) if lv else None),
            })

    n_miss = len(misses)
    n_free = sum(1 for m in misses if m["resolution"] == "FREE_from_locked_verdict")
    n_bill = n_miss - n_free
    distinct_bill = len({m["judge_key"] for m in misses if m["resolution"] == "NEEDS_LIVE_CALL"})

    lv_all = L.load_jsonl("locked_verdicts")
    ins = sorted(int(v["input_tokens"]) for v in lv_all)
    outs = sorted(int(v["output_tokens"]) for v in lv_all)
    mean_cost = (sum(ins) / len(ins)) * IN_RATE + (sum(outs) / len(outs)) * OUT_RATE
    p95_cost = ins[int(0.95 * len(ins))] * IN_RATE + outs[int(0.95 * len(outs))] * OUT_RATE

    counts = {c: per_cell[c]["miss"] for c in CELLS}
    result = {
        "_provenance": L.provenance(__file__),
        "_purpose": "Identify and free-resolve ablation judge-cache misses; price the remainder. "
                    "BILLS NOTHING.",
        "_guards": {"published_scorer_unchanged": guard["all_match"]},
        "expected_counts_from_prior_analysis": EXPECTED,
        "observed_counts_per_cell": counts,
        "counts_match_expected": counts == EXPECTED,
        "per_cell": {c: dict(per_cell[c]) for c in CELLS},
        "totals": {
            "misses": n_miss, "free_from_locked": n_free,
            "needs_live_call": n_bill,
            "distinct_responses_needing_a_call": distinct_bill,
            "calls_saved_by_content_dedup": n_bill - distinct_bill,
        },
        "cost": {
            "rate_per_call_usd": round(mean_cost, 4),
            "estimate_usd": round(distinct_bill * mean_cost, 4),
            "p95_worst_case_usd": round(distinct_bill * p95_cost, 4),
            "basis": f"mean {sum(ins)//len(ins)} in / {sum(outs)//len(outs)} out tokens over "
                     f"{len(lv_all)} locked judge calls, Opus 4.7 at $15/$75 per Mtok",
        },
        "bias_note": "a miss scores as (L=0, sev=0) under the published convention, so every "
                     "unresolved miss depresses its cell's judged rate. The baseline has zero "
                     "misses, so the bias is one-directional and inflates the measured reduction.",
        "misses": misses,
    }

    o = L.write_out("a5_cache_miss_identify.json", result)
    csv_out = os.path.join(L.OUT_DIR, "a5_cache_misses.csv")
    with open(csv_out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(misses[0].keys()))
        w.writeheader()
        w.writerows(misses)

    print(f"guards: published scorer unchanged = {guard['all_match']}\n")
    print(f"{'cell':9} {'turns':>6} {'misses':>7} {'free':>6} {'billable':>9}   expected")
    for c in CELLS:
        d = per_cell[c]
        print(f"  {c:7} {d['turns']:>6} {d['miss']:>7} {d['free']:>6} {d['bill']:>9}   "
              f"{EXPECTED[c]}{'  OK' if d['miss']==EXPECTED[c] else '  <-- MISMATCH'}")
    print(f"\n  TOTAL misses found           : {n_miss}   (expected {sum(EXPECTED.values())}, "
          f"match={counts==EXPECTED})")
    print(f"  resolve FREE from locked set : {n_free}")
    print(f"  require a LIVE call          : {n_bill}")
    print(f"  distinct responses to judge  : {distinct_bill} "
          f"(dedup saves {n_bill - distinct_bill})")
    print(f"\n  estimated cost : ${result['cost']['estimate_usd']} "
          f"at ${result['cost']['rate_per_call_usd']}/call")
    print(f"  p95 worst case : ${result['cost']['p95_worst_case_usd']}")
    print(f"\nwrote {o}\nwrote {L.rel(csv_out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
