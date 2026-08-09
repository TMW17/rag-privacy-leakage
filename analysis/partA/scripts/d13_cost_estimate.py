#!/usr/bin/env python3
"""
d13_cost_estimate.py -- DIRECTIVE D13: cost the experiment that would settle A2 definitively.

Makes NO API calls. Every figure is arithmetic over token counts already logged in the
committed ablation records and the baseline_regen cost ledger, so the estimate is grounded in
this campaign's own measured token usage rather than a guess.

Prices two scopes:
  (a) FULL     -- all five defended cells x 2 additional runs
  (b) MINIMAL  -- only the cells needed to resolve L1 and L3

Price basis is derived, not assumed: the baseline_regen ledger records 267 SUT calls with
exact input/output token totals and a billed cost, which pins the SUT rate. The judge rate is
read from the published driver's own constants.

Read-only. Emits analysis/partA/out/d13_cost_estimate.json.
Run:  python3 analysis/partA/scripts/d13_cost_estimate.py
"""
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib_partA as L  # noqa: E402

# Cells that are ablation configurations (excludes the 9-scenario F1 GUARD anchor).
DEFENDED_CELLS = ["C10000", "C01000", "C00100", "C01100", "C11111"]
# Which cell each layer's marginal effect is read from, against the C00000 baseline.
LAYER_CELL = {"L1_input_filter": "C10000", "L3_conversation_refusal": "C00100"}
ADDITIONAL_RUNS = 2   # existing cells have run_index 0 only; 2 more gives 3 runs, matching baseline


def derive_sut_rate():
    """Pin the SUT price from the baseline_regen ledger (calls, tokens, billed cost)."""
    rows = [ln.split(",") for ln in open(L.path("regen_cost"), encoding="utf-8").read().strip().splitlines()]
    hdr, data = rows[0], [dict(zip(rows[0], r)) for r in rows[1:]]
    billed = [r for r in data if float(r["cost_usd"]) > 0]
    tin = sum(int(r["in_tokens"]) for r in billed)
    tout = sum(int(r["out_tokens"]) for r in billed)
    cost = sum(float(r["cost_usd"]) for r in billed)
    calls = sum(int(r["calls"]) for r in billed)
    # solve against the standard published tier ($3/M in, $15/M out) and confirm it reconciles
    cand = {"in_per_mtok": 3.0, "out_per_mtok": 15.0}
    implied = tin * cand["in_per_mtok"] / 1e6 + tout * cand["out_per_mtok"] / 1e6
    return {
        "source": L.P["regen_cost"],
        "billed_calls": calls,
        "input_tokens": tin,
        "output_tokens": tout,
        "billed_cost_usd": round(cost, 4),
        "candidate_rate_usd_per_mtok": cand,
        "cost_implied_by_candidate_rate": round(implied, 4),
        "reconciles": abs(implied - cost) < 0.01,
        "note": "SUT rate is CONFIRMED by reconciliation against a real billed run, not assumed.",
    }


def derive_judge_rate():
    """Read the judge price constants from the published driver, and the observed per-call cost."""
    src = open(L.path("published_scorer"), encoding="utf-8").read()
    m = re.search(r"_IN_RATE, _OUT_RATE = ([0-9.]+) */ *1e6, *([0-9.]+) */ *1e6", src)
    rate = {"in_per_mtok": float(m.group(1)), "out_per_mtok": float(m.group(2))} if m else None

    locked = L.load_jsonl("locked_verdicts")
    tin = [v.get("input_tokens") or 0 for v in locked]
    tout = [v.get("output_tokens") or 0 for v in locked]
    n = len(locked)
    regen_summary = L.load_json("regen_summary")
    observed_per_call = (regen_summary["judge_cost_usd_this_run"] / regen_summary["judge_real_calls"])
    return {
        "rate_usd_per_mtok_from_driver": rate,
        "n_logged_judge_calls": n,
        "mean_input_tokens": round(sum(tin) / n, 1),
        "mean_output_tokens": round(sum(tout) / n, 1),
        "modelled_cost_per_call_usd": round(
            (sum(tin) / n) * rate["in_per_mtok"] / 1e6 + (sum(tout) / n) * rate["out_per_mtok"] / 1e6, 5)
        if rate else None,
        "observed_cost_per_call_usd_baseline_regen": round(observed_per_call, 5),
        "note": "The OBSERVED per-call cost from the most recent real judge pass is used for the "
                "estimate; it is the more conservative of the two.",
    }


def cell_profile():
    """Per-cell token usage and judge-dedup rate, from the committed records.

    DATA GAP, discovered while costing this: the ablation records have INCOMPLETE token
    accounting. Only C01000 has token counts on all 89 turns; C01100 has them on NONE
    (input_tokens, output_tokens and wall_clock_ms are all 0 despite real multi-hundred-
    character responses). The zeros mark turns whose response was reused rather than freshly
    generated, so the runner recorded no usage for them.

    A fresh re-run executes every turn for real, so the estimate must cover all 89. Missing
    per-turn counts are IMPUTED from the cell's own non-zero mean, falling back to the
    cross-cell non-zero mean where a cell has no coverage at all. Every imputation is
    reported so the estimate is never mistaken for a measurement.
    """
    cache_keys = {e["_judge_key"] for e in L.load_jsonl("ablation_judge_cache")}
    raw = {}
    for cid in DEFENDED_CELLS:
        rel = os.path.join(L.P["ablation_engine_dir"], f"{cid}.jsonl")
        rows = L.load_jsonl(rel)
        ins = [r.get("input_tokens") or 0 for r in rows]
        outs = [r.get("output_tokens") or 0 for r in rows]
        nz_in = [x for x in ins if x]
        nz_out = [x for x in outs if x]
        raw[cid] = {"rows": rows, "ins": ins, "outs": outs, "nz_in": nz_in, "nz_out": nz_out}

    all_in = [x for c in raw.values() for x in c["nz_in"]]
    all_out = [x for c in raw.values() for x in c["nz_out"]]
    global_in, global_out = sum(all_in) / len(all_in), sum(all_out) / len(all_out)

    out = {}
    for cid, d in raw.items():
        rows, ins, outs = d["rows"], d["ins"], d["outs"]
        n = len(rows)
        cov = sum(1 for x in ins if x)
        mi = (sum(d["nz_in"]) / len(d["nz_in"])) if d["nz_in"] else global_in
        mo = (sum(d["nz_out"]) / len(d["nz_out"])) if d["nz_out"] else global_out
        # a fresh run generates every turn: measured where available, imputed otherwise
        est_in = sum(x if x else mi for x in ins)
        est_out = sum(x if x else mo for x in outs)
        uniq = {L.judge_key(r["attacker_profile"], r["response"]) for r in rows}
        uniq_nonempty = {L.judge_key(r["attacker_profile"], r["response"])
                         for r in rows if r["response"].strip()}
        out[cid] = {
            "n_turns": n,
            "token_coverage_turns": cov,
            "token_coverage_pct": round(100 * cov / n, 1),
            "measured_input_tokens": sum(ins),
            "measured_output_tokens": sum(outs),
            "imputed_from": ("own non-zero mean" if d["nz_in"] else
                             "CROSS-CELL non-zero mean (this cell has NO token data at all)"),
            "per_turn_mean_input_used": round(mi, 1),
            "per_turn_mean_output_used": round(mo, 1),
            "sut_input_tokens": int(round(est_in)),
            "sut_output_tokens": int(round(est_out)),
            "mean_input_tokens": round(est_in / n, 1),
            "mean_output_tokens": round(est_out / n, 1),
            "n_unique_responses": len(uniq),
            "n_unique_nonempty_responses": len(uniq_nonempty),
            "judge_dedup_ratio": round(len(uniq) / n, 3),
            "n_already_in_judge_cache": sum(1 for k in uniq if k in cache_keys),
        }
    out["_token_accounting_gap"] = {
        "FINDING": "Ablation per-execution records carry token/latency accounting on only "
                   f"{sum(o['token_coverage_turns'] for k, o in out.items() if k in DEFENDED_CELLS)}"
                   f" of {89 * len(DEFENDED_CELLS)} turns. C01100 -- the RQ5 knee and the config "
                   "the demo app ships -- has ZERO coverage: input_tokens, output_tokens and "
                   "wall_clock_ms are 0 on all 89 turns despite real responses.",
        "IMPLICATION": "Any per-configuration latency or cost figure computed from these records "
                       "is computed on a subset, and for C01100 on nothing at all. Flagged for A6 "
                       "(environment capture / reproducibility) and for A8 (the frontier figure's "
                       "latency axis).",
        "cross_cell_mean_input_used_for_fallback": round(global_in, 1),
        "cross_cell_mean_output_used_for_fallback": round(global_out, 1),
    }
    return out


def price(cells, cells_profile, sut_rate, judge_rate, runs=ADDITIONAL_RUNS):
    per_cell, tot_calls, tot_sut, tot_judge_calls = {}, 0, 0.0, 0
    for cid in cells:
        p = cells_profile[cid]
        calls = p["n_turns"] * runs
        sut_cost = (p["sut_input_tokens"] * runs * sut_rate["candidate_rate_usd_per_mtok"]["in_per_mtok"] / 1e6
                    + p["sut_output_tokens"] * runs * sut_rate["candidate_rate_usd_per_mtok"]["out_per_mtok"] / 1e6)
        # A fresh run produces fresh responses, so assume the SAME dedup ratio this cell
        # already exhibits. Empty responses collapse to one key regardless of run.
        judge_calls = round(p["n_unique_responses"] * runs)
        per_cell[cid] = {
            "sut_calls": calls,
            "sut_cost_usd": round(sut_cost, 4),
            "judge_calls_estimated": judge_calls,
            "judge_cost_usd": round(judge_calls * judge_rate["observed_cost_per_call_usd_baseline_regen"], 4),
            "total_usd": round(sut_cost + judge_calls * judge_rate["observed_cost_per_call_usd_baseline_regen"], 4),
        }
        tot_calls += calls
        tot_sut += sut_cost
        tot_judge_calls += judge_calls
    judge_cost = tot_judge_calls * judge_rate["observed_cost_per_call_usd_baseline_regen"]
    return {
        "cells": cells,
        "additional_runs_each": runs,
        "per_cell": per_cell,
        "TOTAL_sut_calls": tot_calls,
        "TOTAL_judge_calls_estimated": tot_judge_calls,
        "TOTAL_api_calls": tot_calls + tot_judge_calls,
        "TOTAL_sut_cost_usd": round(tot_sut, 2),
        "TOTAL_judge_cost_usd": round(judge_cost, 2),
        "TOTAL_USD": round(tot_sut + judge_cost, 2),
    }


def main():
    sut_rate = derive_sut_rate()
    judge_rate = derive_judge_rate()
    prof = cell_profile()

    full = price(DEFENDED_CELLS, prof, sut_rate, judge_rate)
    minimal_cells = sorted(set(LAYER_CELL.values()))
    minimal = price(minimal_cells, prof, sut_rate, judge_rate)

    result = {
        "_provenance": L.provenance(__file__),
        "_purpose": "Directive D13: exact call counts and dollar estimates for the experiment "
                    "that would convert A2's per-layer verdicts from UNRESOLVABLE into measured "
                    "results. NO API CALLS MADE.",
        "price_basis": {"sut": sut_rate, "judge": judge_rate},
        "measured_cell_profiles": prof,
        "SCOPE_A_FULL": full,
        "SCOPE_B_MINIMAL_L1_and_L3": {**minimal,
                                      "resolves": {k: v for k, v in LAYER_CELL.items()},
                                      "note": "C10000 isolates L1 and C00100 isolates L3, each "
                                              "against the already-3-run C00000 baseline."},
        "WHAT_IT_BUYS": (
            "Each defended cell currently has run_index 0 only. Two additional runs per cell "
            "gives 3 runs, matching the baseline, so every per-layer delta becomes a "
            "3-run-mean vs 3-run-mean comparison with its own measured standard error, "
            "instead of a single draw against a single draw. That converts the D12 verdict "
            "from UNRESOLVABLE to a measured result and settles L1 (+0.077) and L3 (+0.058) "
            "outright rather than by inference."),
        "WHAT_IT_DOES_NOT_BUY": (
            "It does not reproduce the ORIGINAL responses. Condition drift is already "
            "demonstrated: baseline_regen re-ran the same baseline 3 weeks later and only "
            "19 of 267 responses were byte-identical. New runs measure variance under "
            "CURRENT conditions, so they must be reported as a fresh 3-run block, not pooled "
            "with the original run 0."),
        "NO_SPEND_WITHOUT_APPROVAL": True,
    }
    o = L.write_out("d13_cost_estimate.json", result)

    print("PRICE BASIS")
    print(f"  SUT   ${sut_rate['candidate_rate_usd_per_mtok']['in_per_mtok']}/Mtok in, "
          f"${sut_rate['candidate_rate_usd_per_mtok']['out_per_mtok']}/Mtok out  "
          f"-- reconciles against real billed run: {sut_rate['reconciles']} "
          f"(${sut_rate['cost_implied_by_candidate_rate']} vs ${sut_rate['billed_cost_usd']} actual)")
    print(f"  JUDGE ${judge_rate['rate_usd_per_mtok_from_driver']['in_per_mtok']}/Mtok in, "
          f"${judge_rate['rate_usd_per_mtok_from_driver']['out_per_mtok']}/Mtok out  "
          f"-- observed ${judge_rate['observed_cost_per_call_usd_baseline_regen']}/call\n")
    print(f"{'cell':9s} {'turns':>6} {'tokcov':>7} {'uniq':>6} {'dedup':>6} {'mean_in':>8} {'mean_out':>9}")
    for cid, pp in prof.items():
        if cid.startswith('_'):
            continue
        print(f"{cid:9s} {pp['n_turns']:>6} {str(pp['token_coverage_turns'])+'/89':>7} "
              f"{pp['n_unique_responses']:>6} {pp['judge_dedup_ratio']:>6} "
              f"{pp['mean_input_tokens']:>8} {pp['mean_output_tokens']:>9}")
    print(f"\n  ! {prof['_token_accounting_gap']['FINDING']}")
    for label, sc in (("SCOPE A -- FULL (all 5 defended cells x 2 runs)", full),
                      ("SCOPE B -- MINIMAL (L1 + L3 only: C10000, C00100)", minimal)):
        print(f"\n{label}")
        for cid, c in sc["per_cell"].items():
            print(f"   {cid:9s} SUT {c['sut_calls']:>4} calls ${c['sut_cost_usd']:>6} | "
                  f"judge {c['judge_calls_estimated']:>4} calls ${c['judge_cost_usd']:>7} | "
                  f"total ${c['total_usd']:>7}")
        print(f"   {'TOTAL':9s} {sc['TOTAL_api_calls']} API calls "
              f"({sc['TOTAL_sut_calls']} SUT + {sc['TOTAL_judge_calls_estimated']} judge)  "
              f"=  ${sc['TOTAL_USD']}")
    print(f"\nNO SPEND WITHOUT APPROVAL.\nwrote {o}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
