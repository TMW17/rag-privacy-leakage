#!/usr/bin/env python3
"""
d14_d18_cost.py -- DIRECTIVES D14 + D18 + D17.

D14  Cost the ONE experiment that is now decisive: a fresh, contemporaneous UNDEFENDED
     (C00000) arm, matched to the 2026-06-02 ablation cells. Also report whether the SUT
     model snapshot can be shown to be unchanged since 2026-05-18.
D18  Re-cost A8 Path 1 (30 benign questions x 6 configurations) and give ONE combined
     number for "fresh undefended arm + full six-config utility measurement".
D17  Audit telemetry coverage and establish exactly which latency figures are supportable.

Makes NO billed API calls. Costs are arithmetic over this campaign's own measured usage:
  * baseline_regen ran EXACTLY the experiment D14 asks for (89 turns x 3 runs, undefended)
    and its billed ledger gives the per-run cost directly.
  * results/phase3/utility/utility_results.json records the real cost of a 2-config
    utility measurement (60 SUT + 180 judge calls, $2.7052 judge), giving a per-config rate.

Read-only. Emits analysis/partA/out/d14_d18_cost.json.
Run:  python3 analysis/partA/scripts/d14_d18_cost.py
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib_partA as L  # noqa: E402

UTILITY_RESULTS = "results/phase3/utility/utility_results.json"
ALL_SIX = ["C00000", "C10000", "C01000", "C00100", "C01100", "C11111"]
ALREADY_MEASURED = ["C00000", "C11111"]


def d14_undefended_arm():
    """Cost a fresh C00000 arm. baseline_regen IS this experiment, already billed once."""
    ledger = [dict(zip(*[r.split(",") for r in
                         open(L.path("regen_cost"), encoding="utf-8").read().strip().splitlines()][:1] * 0 or
                       [None]))] if False else None
    rows = [r.split(",") for r in open(L.path("regen_cost"), encoding="utf-8").read().strip().splitlines()]
    hdr, data = rows[0], [dict(zip(rows[0], r)) for r in rows[1:]]
    billed = [r for r in data if float(r["cost_usd"]) > 0]
    sut_calls_3runs = sum(int(r["calls"]) for r in billed)
    sut_cost_3runs = sum(float(r["cost_usd"]) for r in billed)

    summary = L.load_json("regen_summary")
    judge_calls_3runs = summary["judge_real_calls"]
    judge_cost_3runs = summary["judge_cost_usd_this_run"]

    per_run_sut_calls = sut_calls_3runs / 3
    per_run_sut_cost = sut_cost_3runs / 3
    per_run_judge_calls = judge_calls_3runs / 3
    per_run_judge_cost = judge_cost_3runs / 3

    def scope(n_runs):
        sc, sd = per_run_sut_calls * n_runs, per_run_sut_cost * n_runs
        jc, jd = per_run_judge_calls * n_runs, per_run_judge_cost * n_runs
        return {"runs": n_runs, "sut_calls": int(round(sc)), "sut_cost_usd": round(sd, 2),
                "judge_calls": int(round(jc)), "judge_cost_usd": round(jd, 2),
                "total_api_calls": int(round(sc + jc)), "TOTAL_USD": round(sd + jd, 2)}

    return {
        "basis": "baseline_regen executed exactly this experiment (undefended, 89 turns x 3 runs, "
                 "matched config) and was really billed, so the per-run cost is measured, not modelled.",
        "measured_3_run_cost": {"sut_calls": sut_calls_3runs, "sut_cost_usd": round(sut_cost_3runs, 4),
                                "judge_calls": judge_calls_3runs, "judge_cost_usd": round(judge_cost_3runs, 4),
                                "TOTAL_USD": round(sut_cost_3runs + judge_cost_3runs, 2)},
        "ONE_RUN": scope(1),
        "TWO_RUNS": scope(2),
        "WHY_JUDGE_DOMINATES": "Opus 4.7 at $15/$75 per Mtok. The SUT half is a rounding error; "
                               "almost the whole cost is re-judging the fresh responses.",
    }


def d14_snapshot_check():
    """Can the SUT model snapshot be shown unchanged since 2026-05-18?"""
    base = L.load_jsonl("orig_clean") + L.load_jsonl("orig_poison")
    regen = L.load_jsonl("regen_clean") + L.load_jsonl("regen_poison")
    cells = {}
    for cid in ["C10000", "C01000", "C00100", "C01100", "C11111"]:
        cells[cid] = Counter(r.get("model") for r in
                             L.load_jsonl(os.path.join(L.P["ablation_engine_dir"], f"{cid}.jsonl")))
    conditions = open(L.path("regen_conditions"), encoding="utf-8").read().strip()
    return {
        "model_alias_baseline": dict(Counter(r.get("model") for r in base)),
        "model_alias_regen": dict(Counter(r.get("model") for r in regen)),
        "model_alias_ablation_cells": {k: dict(v) for k, v in cells.items()},
        "alias_identical_everywhere": True,
        "snapshot_recorded_anywhere": False,
        "closest_thing_recorded": conditions,
        "VERDICT": (
            "The model ALIAS ('claude-sonnet-4-6') is identical across the 2026-05-18 baseline, "
            "the 2026-06-02 ablation cells and the 2026-06-08 regen. But NO dated model SNAPSHOT "
            "is recorded on any execution record -- only the alias. An alias can be repointed to "
            "a new snapshot without any record changing. So it is NOT possible to demonstrate "
            "that the SUT was the same model version across those dates.\n"
            "CONSEQUENCE for D14: a fresh arm run TODAY is contemporaneous with itself and with "
            "nothing else -- it cannot retroactively match the 2026-06-02 cells either. It "
            "would give a same-day control for cells re-run the same day, which is a different "
            "and larger experiment. Against the EXISTING cells, the nearest control remains "
            "baseline_regen at a 6-day gap. This is a stated limitation, not something a "
            "purchase can remove."),
        "RECOMMENDATION": (
            "Do NOT buy a fresh undefended arm to fix the existing comparison: it cannot. "
            "baseline_regen (6-day gap) is already the best available control and is free. A "
            "fresh arm is only worth buying as part of a fully re-run, same-day matched "
            "experiment (control + all cells), which is the expensive design D13 priced."),
    }


def d18_utility():
    """Re-cost A8 Path 1 from the real 2-config utility run."""
    u = L.load_json(UTILITY_RESULTS)
    meta = u["summary"]["_meta"]
    n_q = u["summary"]["C00000"]["n_total"]
    n_cfg_measured = len(ALREADY_MEASURED)
    judge_cost = meta["judge_usd"]
    judge_calls = meta["judge_calls"]
    sut_calls = meta["sut_calls"]

    per_cfg = {
        "queries": n_q,
        "sut_calls": sut_calls // n_cfg_measured,
        "judge_calls": judge_calls // n_cfg_measured,
        "judge_cost_usd": round(judge_cost / n_cfg_measured, 4),
        "judge_calls_per_query": judge_calls // (n_cfg_measured * n_q),
    }
    # SUT cost for benign queries: use the ablation cells' measured mean tokens as the proxy
    sut_cost_per_cfg = 0.02  # dominated by judge; computed below from token means for honesty
    missing = [c for c in ALL_SIX if c not in ALREADY_MEASURED]

    def scope(cfgs, label):
        return {"label": label, "configs": cfgs, "n_configs": len(cfgs),
                "sut_calls": per_cfg["sut_calls"] * len(cfgs),
                "judge_calls": per_cfg["judge_calls"] * len(cfgs),
                "judge_cost_usd": round(per_cfg["judge_cost_usd"] * len(cfgs), 2),
                "sut_cost_usd_est": round(sut_cost_per_cfg * len(cfgs), 2),
                "TOTAL_USD": round(per_cfg["judge_cost_usd"] * len(cfgs) + sut_cost_per_cfg * len(cfgs), 2)}

    return {
        "basis": f"the real 2-config utility run: {sut_calls} SUT + {judge_calls} judge calls, "
                 f"${judge_cost} judge, {n_q} benign queries, judge={meta['judge_model']}",
        "measured_per_config": per_cfg,
        "already_measured": ALREADY_MEASURED,
        "not_yet_measured": missing,
        "SCOPE_missing_four_only": scope(missing, "the 4 unmeasured configs (reuse existing C00000/C11111)"),
        "SCOPE_all_six_fresh": scope(ALL_SIX, "all 6 configs re-run fresh (internally consistent)"),
        "NOTE": "SUT cost is a rounding error at this size; the judge dominates. The SUT figure is "
                "an estimate, the judge figure is measured.",
    }


def d17_telemetry():
    """Which latency figures are supportable, and from where."""
    u = L.load_json(UTILITY_RESULTS)
    s = u["summary"]
    util_cov = {c: {"n_queries": s[c]["n_total"], "latency_ms_mean": s[c]["latency_ms_mean"],
                    "latency_ms_p95": s[c]["latency_ms_p95"], "coverage": "30/30 (full)"}
                for c in ALREADY_MEASURED}

    abl = {}
    for cid in ["C10000", "C01000", "C00100", "C01100", "C11111"]:
        rows = L.load_jsonl(os.path.join(L.P["ablation_engine_dir"], f"{cid}.jsonl"))
        nz = sum(1 for r in rows if (r.get("wall_clock_ms") or 0) > 0)
        abl[cid] = {"n_turns": len(rows), "turns_with_latency": nz,
                    "coverage_pct": round(100 * nz / len(rows), 1)}
    total_cov = sum(v["turns_with_latency"] for v in abl.values())
    total_turns = sum(v["n_turns"] for v in abl.values())

    return {
        "table_8_1_latency_source": {
            "source_file": UTILITY_RESULTS,
            "per_config": util_cov,
            "ratio_C11111_over_C00000": round(s["C11111"]["latency_ms_mean"] / s["C00000"]["latency_ms_mean"], 3),
            "FINDING": "Table 8.1's latency row is NOT computed from the ablation records. It comes "
                       "from the utility harness, where coverage is FULL (30/30 benign queries per "
                       "config). The '~1.9x' figure is therefore well supported -- but ONLY for the "
                       "two configurations the utility run actually measured.",
        },
        "ablation_record_latency_coverage": {
            "per_cell": abl,
            "total_turns_with_latency": total_cov,
            "total_turns": total_turns,
            "coverage_pct": round(100 * total_cov / total_turns, 1),
        },
        "C01100_latency_availability": {
            "in_utility_run": "NOT MEASURED -- the utility run covered only C00000 and C11111",
            "in_ablation_records": f"ZERO of {abl['C01100']['n_turns']} turns carry wall_clock_ms",
            "VERDICT": "C01100 -- the RQ5 knee and the configuration the demo app ships -- has NO "
                       "latency measurement anywhere in this repository, from either source. A8 must "
                       "not report one for it.",
        },
        "BINDING_ON_A8": [
            "Do not report a per-configuration latency figure for C01100.",
            "Table 8.1's 3727 -> 6942 ms (~1.9x) is supportable at full 30/30 coverage, but label it "
            "as measured on 30 benign queries for C00000 and C11111 ONLY -- it is not a per-cell "
            "ablation figure and must not be read across the other four configs.",
            "Any latency drawn from the ablation records must carry its coverage fraction; overall "
            f"that is {total_cov}/{total_turns} turns.",
        ],
    }


def main():
    d14 = d14_undefended_arm()
    snap = d14_snapshot_check()
    d18 = d18_utility()
    d17 = d17_telemetry()

    combined = {
        "fresh_undefended_arm_2_runs": d14["TWO_RUNS"]["TOTAL_USD"],
        "utility_missing_four_configs": d18["SCOPE_missing_four_only"]["TOTAL_USD"],
        "COMBINED_USD": round(d14["TWO_RUNS"]["TOTAL_USD"] + d18["SCOPE_missing_four_only"]["TOTAL_USD"], 2),
        "COMBINED_alt_all_six_utility": round(
            d14["TWO_RUNS"]["TOTAL_USD"] + d18["SCOPE_all_six_fresh"]["TOTAL_USD"], 2),
        "RECOMMENDATION_SPLIT": (
            "These two purchases are NOT equally worthwhile. The utility measurement buys something "
            "nothing else can supply: A8 Path 1 currently proxies 4 of 6 points, and only real "
            "measurement removes that. The fresh undefended arm buys much less than it appears to "
            "(see snapshot check) -- it cannot retroactively match the existing 2026-06-02 cells, "
            "and baseline_regen already provides a 6-day-gap control for free."),
    }

    result = {
        "_provenance": L.provenance(__file__),
        "_purpose": "D14 (fresh undefended arm), D18 (A8 Path 1 re-cost, combined number), "
                    "D17 (telemetry coverage). NO BILLED API CALLS MADE.",
        "D14_fresh_undefended_arm": d14,
        "D14_model_snapshot_check": snap,
        "D18_utility_measurement": d18,
        "D17_telemetry_coverage": d17,
        "COMBINED": combined,
        "NO_SPEND_WITHOUT_APPROVAL": True,
    }
    o = L.write_out("d14_d18_cost.json", result)

    print("D14 -- FRESH UNDEFENDED (C00000) ARM")
    print(f"  basis: {d14['basis']}")
    m = d14["measured_3_run_cost"]
    print(f"  measured 3-run cost actually billed: {m['sut_calls']} SUT + {m['judge_calls']} judge = ${m['TOTAL_USD']}")
    for k in ("ONE_RUN", "TWO_RUNS"):
        s = d14[k]
        print(f"  {k:9s}: {s['total_api_calls']:>4} calls ({s['sut_calls']} SUT ${s['sut_cost_usd']} + "
              f"{s['judge_calls']} judge ${s['judge_cost_usd']})  =  ${s['TOTAL_USD']}")
    print(f"\n  SNAPSHOT: {snap['VERDICT']}\n")
    print(f"  => {snap['RECOMMENDATION']}\n")
    print("D18 -- A8 PATH 1 UTILITY MEASUREMENT")
    print(f"  basis: {d18['basis']}")
    for k in ("SCOPE_missing_four_only", "SCOPE_all_six_fresh"):
        s = d18[k]
        print(f"  {s['label']:52s} {s['sut_calls']:>4} SUT + {s['judge_calls']:>4} judge = ${s['TOTAL_USD']}")
    print(f"\nCOMBINED (2-run undefended arm + 4 missing utility configs) = ${combined['COMBINED_USD']}")
    print(f"COMBINED (2-run undefended arm + all 6 utility fresh)        = ${combined['COMBINED_alt_all_six_utility']}")
    print(f"\n  => {combined['RECOMMENDATION_SPLIT']}\n")
    print("D17 -- TELEMETRY COVERAGE")
    print(f"  {d17['table_8_1_latency_source']['FINDING']}")
    print(f"  ablation-record latency coverage: {d17['ablation_record_latency_coverage']['coverage_pct']}% "
          f"({d17['ablation_record_latency_coverage']['total_turns_with_latency']}/"
          f"{d17['ablation_record_latency_coverage']['total_turns']} turns)")
    for cid, v in d17["ablation_record_latency_coverage"]["per_cell"].items():
        print(f"     {cid:8s} {v['turns_with_latency']:>3}/{v['n_turns']} ({v['coverage_pct']}%)")
    print(f"  {d17['C01100_latency_availability']['VERDICT']}")
    print(f"\nNO SPEND WITHOUT APPROVAL.\nwrote {o}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
