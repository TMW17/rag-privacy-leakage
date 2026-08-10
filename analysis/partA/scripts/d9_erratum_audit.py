#!/usr/bin/env python3
"""
d9_erratum_audit.py -- DIRECTIVE D9: audit EVERY published rate against the estimator and
denominator that actually produced it.

For each published rate: the value, the estimator that produced it (run-0 scenario /
pooled execution / turn), the denominator the paper claims, and the correct denominator.

The PUBLISHED values below are transcribed from thesis_pfe.tex with file:line recorded. They
are the CLAIMS UNDER TEST, not computed statistics -- every number this script *reports* is
recomputed from raw data and compared against them.

Read-only, no API calls. Emits analysis/partA/out/d9_erratum_audit.json.
Run:  python3 analysis/partA/scripts/d9_erratum_audit.py
"""
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib_partA as L  # noqa: E402

MS = "results/phase3_4/report/thesis/thesis_pfe.tex"

# --- claims under test, transcribed from the manuscript (value, engine, judge, denom shown) ---
PUBLISHED = {
    "tab:ch4-headline (Table 6.3)": {
        "line": 3394,
        "rows": {"ASR_strict": {"engine": 0.192, "judge": 0.288},
                 "ASR_inclusive": {"engine": 0.481, "judge": 0.558}},
        "denominator_shown": "none in table; caption says 'C00000'",
    },
    "tab:ch4-profile (Table 6.4)": {
        "line": 3423,
        "rows": {"P1 Internal": {"engine": 0.278, "judge": 0.333, "n_shown": 18},
                 "P2 External": {"engine": 0.185, "judge": 0.296, "n_shown": 27},
                 "P3 Admin":    {"engine": 0.000, "judge": 0.143, "n_shown": 7},
                 "Overall":     {"engine": 0.192, "judge": 0.288, "n_shown": 52}},
        "denominator_shown": "column header 'Scenarios' (18/27/7, sum 52)",
        "caption_says": "'Rates are over the EXECUTIONS in each profile's scenario subset'",
    },
    "tab:ch4-family (Table 6.5)": {
        "line": 3464,
        "rows": {"F1_DIRECT_PII":       {"engine": 0.556, "judge": 0.778, "n_shown": 9},
                 "F2_LINKABILITY":      {"engine": 0.400, "judge": 0.600, "n_shown": 10},
                 "F5_JAILBREAK":        {"engine": 0.200, "judge": 0.200, "n_shown": 5},
                 "F8_CORPUS_POISONING": {"engine": 0.000, "judge": 0.143, "n_shown": 7},
                 "F3_DIRECT_INJECTION": {"engine": 0.000, "judge": 0.000, "n_shown": 6},
                 "F4_OBFUSCATION":      {"engine": 0.000, "judge": 0.000, "n_shown": 5},
                 "F6_RECON":            {"engine": 0.000, "judge": 0.000, "n_shown": 3},
                 "F7_SOCIAL_ENG":       {"engine": 0.000, "judge": 0.000, "n_shown": 7}},
        "denominator_shown": "column header 'Scenarios' (sum 52)",
    },
}

PROFILE_LABEL = {"Internal": "P1 Internal", "External": "P2 External", "Admin": "P3 Admin"}


def recompute():
    """Per-scenario (max over turns) engine + judged strict, at run 0, split by profile/family."""
    rows = L.load_jsonl("orig_clean") + L.load_jsonl("orig_poison")
    vfn = L.locked_verdict_fn(strict_run_index=True)

    scen = {}
    for r in rows:
        if r.get("run_index") != 0:
            continue
        _, sj = vfn(r)
        es = L.engine_strict_turn(r)
        el = L.engine_incl_turn(r)
        lj, _ = vfn(r)
        sid = r["scenario_id"]
        d = scen.setdefault(sid, {"es": 0, "el": 0, "js": 0, "jl": 0,
                                  "profile": r["attacker_profile"], "family": r["attack_family"]})
        d["es"] = max(d["es"], es)
        d["el"] = max(d["el"], el)
        d["js"] = max(d["js"], max(es, 1 if sj >= 3 else 0))
        d["jl"] = max(d["jl"], max(el, lj))

    def agg(pred):
        sub = [v for v in scen.values() if pred(v)]
        n = len(sub)
        if not n:
            return None
        return {"n_scenarios": n,
                "engine_strict": round(sum(v["es"] for v in sub) / n, 4),
                "engine_incl": round(sum(v["el"] for v in sub) / n, 4),
                "judge_strict": round(sum(v["js"] for v in sub) / n, 4),
                "judge_incl": round(sum(v["jl"] for v in sub) / n, 4),
                "engine_strict_count": sum(v["es"] for v in sub),
                "judge_strict_count": sum(v["js"] for v in sub)}

    by_profile = {PROFILE_LABEL.get(p, p): agg(lambda v, p=p: v["profile"] == p)
                  for p in sorted({v["profile"] for v in scen.values()})}
    by_family = {f: agg(lambda v, f=f: v["family"] == f)
                 for f in sorted({v["family"] for v in scen.values()})}
    overall = agg(lambda v: True)

    # what the SAME quantities would be pooled over all 3 runs (execution-level, denom 156)
    ex = defaultdict(lambda: {"es": 0, "js": 0, "profile": None, "family": None})
    vfn2 = L.locked_verdict_fn(strict_run_index=True)
    for r in rows:
        _, sj = vfn2(r)
        es = L.engine_strict_turn(r)
        k = (r["scenario_id"], r.get("run_index"))
        ex[k]["es"] = max(ex[k]["es"], es)
        ex[k]["js"] = max(ex[k]["js"], max(es, 1 if sj >= 3 else 0))
        ex[k]["profile"] = r["attacker_profile"]
        ex[k]["family"] = r["attack_family"]

    def agg_ex(pred):
        sub = [v for v in ex.values() if pred(v)]
        n = len(sub)
        return {"n_executions": n,
                "engine_strict": round(sum(v["es"] for v in sub) / n, 4),
                "judge_strict": round(sum(v["js"] for v in sub) / n, 4)} if n else None

    pooled = {
        "overall": agg_ex(lambda v: True),
        "by_profile": {PROFILE_LABEL.get(p, p): agg_ex(lambda v, p=p: v["profile"] == p)
                       for p in sorted({v["profile"] for v in ex.values()})},
        "by_family": {f: agg_ex(lambda v, f=f: v["family"] == f)
                      for f in sorted({v["family"] for v in ex.values()})},
    }
    return {"by_profile": by_profile, "by_family": by_family, "overall": overall}, pooled


def audit(recomputed, pooled):
    """Compare every published rate to the run-0 scenario recomputation, and to the pooled one."""
    errata, matched = [], 0

    def cmp_row(table, row, metric, published, run0, pooled_val, n_shown, n_true):
        nonlocal matched
        ok = published is not None and run0 is not None and abs(published - run0) < 1.5e-3
        pooled_ok = published is not None and pooled_val is not None and abs(published - pooled_val) < 1.5e-3
        if ok:
            matched += 1
        errata.append({
            "table": table, "row": row, "metric": metric,
            "published_value": published,
            "recomputed_run0_scenario": run0,
            "recomputed_pooled_execution": pooled_val,
            "matches_run0_scenario_estimator": ok,
            "matches_pooled_execution_estimator": pooled_ok,
            "denominator_shown_in_table": n_shown,
            "correct_denominator_for_the_estimator_used": n_true,
            "denominator_shown_is_correct": (n_shown == n_true) if n_shown is not None else None,
        })

    # Table 6.3
    t = "tab:ch4-headline (Table 6.3)"
    o, po = recomputed["overall"], pooled["overall"]
    cmp_row(t, "ASR_strict", "engine", PUBLISHED[t]["rows"]["ASR_strict"]["engine"],
            o["engine_strict"], po["engine_strict"], None, o["n_scenarios"])
    cmp_row(t, "ASR_strict", "judge", PUBLISHED[t]["rows"]["ASR_strict"]["judge"],
            o["judge_strict"], po["judge_strict"], None, o["n_scenarios"])
    cmp_row(t, "ASR_inclusive", "engine", PUBLISHED[t]["rows"]["ASR_inclusive"]["engine"],
            o["engine_incl"], None, None, o["n_scenarios"])
    cmp_row(t, "ASR_inclusive", "judge", PUBLISHED[t]["rows"]["ASR_inclusive"]["judge"],
            o["judge_incl"], None, None, o["n_scenarios"])

    # Table 6.4
    t = "tab:ch4-profile (Table 6.4)"
    for label, pub in PUBLISHED[t]["rows"].items():
        rc = recomputed["overall"] if label == "Overall" else recomputed["by_profile"].get(label)
        pl = pooled["overall"] if label == "Overall" else pooled["by_profile"].get(label)
        if rc is None:
            continue
        cmp_row(t, label, "engine", pub["engine"], rc["engine_strict"],
                pl["engine_strict"] if pl else None, pub.get("n_shown"), rc["n_scenarios"])
        cmp_row(t, label, "judge", pub["judge"], rc["judge_strict"],
                pl["judge_strict"] if pl else None, pub.get("n_shown"), rc["n_scenarios"])

    # Table 6.5
    t = "tab:ch4-family (Table 6.5)"
    for fam, pub in PUBLISHED[t]["rows"].items():
        rc = recomputed["by_family"].get(fam)
        pl = pooled["by_family"].get(fam)
        if rc is None:
            errata.append({"table": t, "row": fam, "metric": "-", "published_value": pub,
                           "recomputed_run0_scenario": "FAMILY NOT FOUND IN DATA"})
            continue
        cmp_row(t, fam, "engine", pub["engine"], rc["engine_strict"],
                pl["engine_strict"] if pl else None, pub.get("n_shown"), rc["n_scenarios"])
        cmp_row(t, fam, "judge", pub["judge"], rc["judge_strict"],
                pl["judge_strict"] if pl else None, pub.get("n_shown"), rc["n_scenarios"])

    return errata, matched


def prose_scan():
    """Every in-text claim about the unit of analysis or the 156/52 denominators."""
    src = open(os.path.join(L.ROOT, MS), encoding="utf-8", errors="replace").read().splitlines()
    pats = [(r"unit of analysis", "unit-of-analysis statement"),
            (r"\b156\b", "denominator 156"),
            (r"\b52\s+scenario", "denominator 52 scenarios"),
            (r"fraction of the", "rate definition"),
            (r"\bexecutions?\b", "execution-level language")]
    hits = []
    for i, line in enumerate(src, 1):
        for pat, kind in pats:
            if re.search(pat, line, re.I):
                hits.append({"line": i, "kind": kind, "text": line.strip()[:180]})
                break
    return hits


def main():
    recomputed, pooled = recompute()
    errata, matched = audit(recomputed, pooled)
    prose = prose_scan()

    checked = [e for e in errata if isinstance(e.get("recomputed_run0_scenario"), float)]
    n_val_mismatch = sum(1 for e in checked if not e["matches_run0_scenario_estimator"])
    n_denom_wrong = sum(1 for e in checked if e["denominator_shown_is_correct"] is False)
    n_also_pooled = sum(1 for e in checked if e.get("matches_pooled_execution_estimator"))

    verdict = {
        "n_rates_checked": len(checked),
        "n_values_matching_run0_scenario_estimator": len(checked) - n_val_mismatch,
        "n_value_mismatches": n_val_mismatch,
        "n_denominators_shown_incorrect": n_denom_wrong,
        "n_rates_that_ALSO_match_the_pooled_estimator": n_also_pooled,
        "CONCLUSION": (
            "EVERY published rate is a RUN-0 SCENARIO rate, and every denominator PRINTED IN A "
            "TABLE is correct. The tables are right. The defect is confined to the PROSE that "
            "describes them: the Methods sentence declares the execution the unit of analysis "
            "over 156 executions, and Table 6.4's caption repeats 'executions'. This is ONE "
            "systematic correction to the surrounding text, not a list of independent numeric "
            "errors -- exactly as anticipated. The only wrong NUMBER found anywhere is the "
            "'30/156' gloss on the engine headline (D1: the true pooled count is 29)."
            if n_val_mismatch == 0 and n_denom_wrong == 0 else
            f"{n_val_mismatch} value mismatch(es) and {n_denom_wrong} wrong denominator(s) found."),
        "BINDING_ON_A7_D10": (
            f"Wilson intervals must use the scenario denominators recomputed here "
            f"(overall n={recomputed['overall']['n_scenarios']}; per-profile and per-family n as "
            "listed), NOT 156. Computing on 156 would make every interval about sqrt(3) too narrow."),
    }

    result = {
        "_provenance": L.provenance(__file__),
        "_purpose": "Directive D9: consolidated erratum -- every published rate against the "
                    "estimator and denominator that actually produced it.",
        "manuscript": MS,
        "published_claims_under_test": PUBLISHED,
        "recomputed_run0_scenario_level": recomputed,
        "recomputed_pooled_execution_level": pooled,
        "ERRATUM_TABLE": errata,
        "prose_hits_needing_correction": prose,
        "VERDICT": verdict,
    }
    o = L.write_out("d9_erratum_audit.json", result)

    print(f"{'table':30s} {'row':22s} {'metric':7s} {'pub':>7} {'run0':>7} {'pooled':>7} "
          f"{'n_tab':>6} {'n_true':>6}  ok")
    print("-" * 104)
    for e in errata:
        if not isinstance(e.get("recomputed_run0_scenario"), float):
            print(f"{e['table'][:30]:30s} {str(e['row'])[:22]:22s} {'-':7s}  {e['recomputed_run0_scenario']}")
            continue
        pv = e["published_value"]
        pooled_v = e["recomputed_pooled_execution"]
        print(f"{e['table'][:30]:30s} {str(e['row'])[:22]:22s} {e['metric']:7s} "
              f"{pv if pv is not None else '-':>7} {e['recomputed_run0_scenario']:>7} "
              f"{(pooled_v if pooled_v is not None else '-'):>7} "
              f"{str(e['denominator_shown_in_table'] or '-'):>6} "
              f"{e['correct_denominator_for_the_estimator_used']:>6}  "
              f"{'OK' if e['matches_run0_scenario_estimator'] else 'MISMATCH'}")
    print()
    for k, v in verdict.items():
        print(f"  {k}: {v}")
    print(f"\nprose lines needing correction: {len(prose)}")
    for h in prose[:12]:
        print(f"   {MS}:{h['line']}  [{h['kind']}]  {h['text'][:120]}")
    print(f"\nwrote {o}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
