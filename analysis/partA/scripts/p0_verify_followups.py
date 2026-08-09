#!/usr/bin/env python3
"""
p0_verify_followups.py -- four verification checks that qualify or strengthen Phase 0's
reported findings. Each exists because a Phase 0 claim could be wrong in a specific,
checkable way.

  V1  LOCKED-VERDICT PER-RUN INDEPENDENCE.
      The published scorer hardcodes run_index 0 into its cache key, yet locked verdicts
      exist for runs 0/1/2 with zero misses under a strict per-run lookup. Are runs 1 and 2
      genuinely separate judge calls, or were they populated by copying run 0? This decides
      whether the canonical JUDGED per-run variation is real, and whether the
      judge-determinism flip compares a fresh judgement against a replicated one.

  V2  TRUE n FOR THE JUDGE-DETERMINISM TEST.
      Those pairs are keyed on content, so one response appearing at several (run, turn)
      positions inflates n. Report distinct _judge_key count, not row count.

  V3  WHICH MANUSCRIPT THE REVIEW'S FLOAT NUMBERS FIT.
      Figure 6.6 and Figure 7.7 do not exist in thesis_pfe.tex. thesis.tex has a different
      chapter count and therefore different printed numbering. Scan both and say which one
      the requested numbers fit -- this decides whether A8's target really is fig:ch6-pareto.

  V4  THE UNJUDGED NON-EMPTY TURNS.
      Two non-empty F2 responses are scored no-leak by judge-cache miss in C00100 and
      C10000. Are they the same two distinct responses across both cells, or four?

Read-only. Emits analysis/partA/out/p0_verify_followups.json.
Run:  python3 analysis/partA/scripts/p0_verify_followups.py
"""
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib_partA as L  # noqa: E402
import p0_inventory as INV  # noqa: E402


# ------------------------------------------------------------------ V1
def v1_locked_verdict_independence():
    """Are locked verdicts for runs 1 and 2 independent judge calls, or copies of run 0?"""
    locked = L.load_jsonl("locked_verdicts")
    main = [v for v in locked if v.get("run_id") == "main-w3"]
    poison = [v for v in locked if v.get("run_id") == "poisoned-w4"]

    by_run = Counter(v.get("run_index") for v in locked)
    by_runid_run = Counter((v.get("run_id"), v.get("run_index")) for v in locked)

    # group by (run_id, scenario, turn) and compare the three runs' rows field by field
    groups = defaultdict(dict)
    for v in locked:
        groups[(v.get("run_id"), v.get("scenario_id"), v.get("turn_index"))][v.get("run_index")] = v

    full = {k: g for k, g in groups.items() if len(g) >= 2}
    # Fields that MUST differ between two genuinely separate API calls. latency_ms and
    # cost_usd/output_tokens are effectively call fingerprints: two independent calls
    # returning identical latency to the millisecond is implausible.
    fingerprint = ("latency_ms", "cost_usd", "input_tokens", "output_tokens", "rationale")
    identical_all = 0
    identical_fingerprint = 0
    differing = 0
    examples = []
    for k, g in sorted(full.items(), key=lambda x: str(x[0])):
        runs = sorted(g)
        base = g[runs[0]]
        same_fp = all(all(g[r].get(f) == base.get(f) for f in fingerprint) for r in runs[1:])
        same_verdict = all(
            (g[r].get("L_judge"), g[r].get("severity_judge"), g[r].get("leak_type_judge"))
            == (base.get("L_judge"), base.get("severity_judge"), base.get("leak_type_judge"))
            for r in runs[1:])
        identical_fingerprint += same_fp
        identical_all += (same_fp and same_verdict)
        if not same_fp:
            differing += 1
            if len(examples) < 4:
                examples.append({
                    "key": [str(x) for x in k],
                    "per_run": {str(r): {f: g[r].get(f) for f in
                                         ("L_judge", "severity_judge", "leak_type_judge",
                                          "latency_ms", "output_tokens")} for r in runs},
                })

    n = len(full)
    verdict = (
        "INDEPENDENT -- run 1 and run 2 verdicts are separate judge calls (distinct latency / "
        "token / rationale fingerprints), so the canonical per-run JUDGED variation is real."
        if differing > n * 0.5 else
        "REPLICATED -- runs 1 and 2 share run 0's call fingerprint, so they are copies, not "
        "independent judgements. The canonical per-run JUDGED variation is an artifact and "
        "the judge-determinism flip compares fresh against replicated.")
    return {
        "n_locked_rows": len(locked),
        "rows_by_run_index": {str(k): v for k, v in sorted(by_run.items(), key=lambda x: str(x[0]))},
        "rows_by_run_id_and_index": {f"{a}|run{b}": c for (a, b), c in sorted(by_runid_run.items(),
                                                                             key=lambda x: str(x[0]))},
        "n_turn_groups_with_multiple_runs": n,
        "n_groups_sharing_call_fingerprint": identical_fingerprint,
        "n_groups_with_distinct_call_fingerprint": differing,
        "n_groups_identical_in_every_field": identical_all,
        "fingerprint_fields": list(fingerprint),
        "examples_of_differing_groups": examples,
        "VERDICT": verdict,
    }


# ------------------------------------------------------------------ V2
def v2_determinism_true_n():
    """Distinct-input count for the judge-determinism test, not row count."""
    orig = L.load_jsonl("orig_clean") + L.load_jsonl("orig_poison")
    cache = {e["_judge_key"]: e for e in L.load_jsonl("regen_judge_cache")}
    locked = {v["_cache_key"]: v for v in L.load_jsonl("locked_verdicts")}

    by_key = defaultdict(list)
    for r in orig:
        k = L.judge_key(r["attacker_profile"], r["response"])
        if k not in cache:
            continue
        ck = f"{r.get('run_id','')}|{r['scenario_id']}|{r.get('run_index')}|{r['turn_index']}"
        if ck not in locked:
            continue
        by_key[k].append((r, locked[ck]))

    rows_total = sum(len(v) for v in by_key.values())
    distinct = len(by_key)

    # per distinct input: does the locked verdict agree with the regen verdict? If the same
    # content appears at several positions with DIFFERENT locked verdicts, that is itself a
    # judge-determinism signal within the locked pass.
    disagreements, internal_splits = [], []
    for k, items in by_key.items():
        rv = cache[k]
        rb = (int(rv.get("L_judge", 0) or 0), int(rv.get("severity_judge", 0) or 0))
        locked_set = {(int(lv.get("L_judge", 0) or 0), int(lv.get("severity_judge", 0) or 0))
                      for _, lv in items}
        if len(locked_set) > 1:
            internal_splits.append({
                "judge_key_16": k[:16],
                "n_positions": len(items),
                "locked_verdicts": sorted(str(x) for x in locked_set),
                "positions": [f"{r['scenario_id']}|run{r.get('run_index')}|t{r['turn_index']}"
                              for r, _ in items],
            })
        la = next(iter(locked_set))
        if len(locked_set) == 1 and la != rb:
            disagreements.append({
                "judge_key_16": k[:16],
                "n_positions": len(items),
                "positions": [f"{r['scenario_id']}|run{r.get('run_index')}|t{r['turn_index']}"
                              for r, _ in items],
                "profile": items[0][0]["attacker_profile"],
                "response_len": len(items[0][0]["response"]),
                "locked": {"L": la[0], "severity": la[1]},
                "regen": {"L": rb[0], "severity": rb[1]},
                "strict_agrees": (la[1] >= 3) == (rb[1] >= 3),
            })

    return {
        "n_rows_previously_reported": rows_total,
        "n_distinct_inputs_TRUE_N": distinct,
        "multiplicity_histogram": dict(Counter(len(v) for v in by_key.values())),
        "n_distinct_inputs_disagreeing": len(disagreements),
        "disagreements": disagreements,
        "n_inputs_with_split_locked_verdicts": len(internal_splits),
        "internal_locked_splits": internal_splits,
        "VERDICT": (f"{len(disagreements)} of {distinct} DISTINCT inputs got a different verdict "
                    f"on re-judging (previously stated as a rate over {rows_total} rows)."),
    }


# ------------------------------------------------------------------ V3
def v3_which_manuscript():
    """Scan every root and report which one's numbering fits the review's float numbers."""
    tdir = os.path.join(L.ROOT, "results", "phase3_4", "report", "thesis")
    wanted_fig = {"Figure 6.6", "Figure 7.7"}
    wanted_all = list(INV.scan_manuscript()["requested_float_resolution"].keys())

    out = {}
    for fn in sorted(f for f in os.listdir(tdir) if f.endswith(".tex")):
        fp = os.path.join(tdir, fn)
        src = open(fp, encoding="utf-8", errors="replace").read()
        if "\\documentclass" not in src:
            continue
        chs = [(m.start(), m.group(1)) for m in INV.CHAPTER_RE.finditer(src)]
        if len(chs) < 6:
            continue
        bounds = [(chs[i][0], chs[i + 1][0] if i + 1 < len(chs) else len(src), i + 1, chs[i][1])
                  for i in range(len(chs))]
        counters, nums = {}, {}
        for m in INV.FLOAT_RE.finditer(src):
            kind, pos = m.group(1), m.start()
            ch = next((n for s, e, n, _ in bounds if s <= pos < e), None)
            if ch is None:
                continue
            ck = (ch, kind)
            counters[ck] = counters.get(ck, 0) + 1
            endm = re.search(r"\\end\{" + kind + r"\*?\}", src[pos:])
            body = src[pos:pos + (endm.end() if endm else 6000)]
            lab = INV.LABEL_RE.search(body)
            nums[f"{'Table' if kind=='table' else 'Figure'} {ch}.{counters[ck]}"] = \
                lab.group(1) if lab else None
        resolved = sum(1 for w in wanted_all if w in nums)
        out[os.path.relpath(fp, L.ROOT)] = {
            "n_chapters": len(chs),
            "chapter_titles": [t for _, t in chs],
            "floats_per_chapter": {f"ch{c}_{k}": v for (c, k), v in sorted(counters.items())},
            "n_requested_resolved": resolved,
            "n_requested": len(wanted_all),
            "missing_requested": [w for w in wanted_all if w not in nums],
            "resolves_Figure_6_6": "Figure 6.6" in nums,
            "resolves_Figure_7_7": "Figure 7.7" in nums,
            "label_for_Figure_8_1": nums.get("Figure 8.1"),
            "label_for_Figure_6_6": nums.get("Figure 6.6"),
            "label_for_Figure_7_7": nums.get("Figure 7.7"),
        }

    best = max(out.items(), key=lambda kv: kv[1]["n_requested_resolved"]) if out else (None, {})
    fits_all = [k for k, v in out.items() if not v["missing_requested"]]
    return {
        "roots_scanned": out,
        "best_fit": best[0],
        "roots_resolving_every_requested_float": fits_all,
        "wanted_figures_that_were_missing_in_pfe": sorted(wanted_fig),
        "VERDICT": (f"No manuscript root resolves all {len(wanted_all)} requested floats; "
                    f"best fit is {best[0]} at {best[1].get('n_requested_resolved')}/{len(wanted_all)}."
                    if not fits_all else
                    f"{fits_all} resolve(s) every requested float."),
    }


# ------------------------------------------------------------------ V4
def v4_unjudged_turns():
    """Are the unjudged non-empty responses the same distinct responses across cells?"""
    cache_keys = {e["_judge_key"] for e in L.load_jsonl("ablation_judge_cache")}
    eng_dir = os.path.join(L.ROOT, L.P["ablation_engine_dir"])
    per_cell, all_missed = {}, defaultdict(list)
    for fn in sorted(f for f in os.listdir(eng_dir) if f.endswith(".jsonl")):
        rows = L.load_jsonl(os.path.join(L.P["ablation_engine_dir"], fn))
        cid = fn[:-6]
        miss = []
        for r in rows:
            k = L.judge_key(r["attacker_profile"], r["response"])
            if k in cache_keys:
                continue
            miss.append({"judge_key_16": k[:16], "scenario_id": r["scenario_id"],
                         "turn_index": r["turn_index"], "family": r.get("attack_family"),
                         "profile": r["attacker_profile"],
                         "response_len": len(r["response"]),
                         "empty": not r["response"].strip(),
                         "engine_strict": L.engine_strict_turn(r)})
            all_missed[k].append(f"{cid}:{r['scenario_id']}|t{r['turn_index']}")
        per_cell[cid] = {"n_missed": len(miss), "n_missed_empty": sum(1 for m in miss if m["empty"]),
                         "n_missed_nonempty": sum(1 for m in miss if not m["empty"]),
                         "missed": miss}
    nonempty_keys = {k: v for k, v in all_missed.items()
                     if not any(m["empty"] for c in per_cell.values() for m in c["missed"]
                                if m["judge_key_16"] == k[:16])}
    return {
        "per_cell": per_cell,
        "n_distinct_missed_responses_across_all_cells": len(all_missed),
        "n_distinct_missed_NONEMPTY_responses": len(nonempty_keys),
        "distinct_nonempty_missed": {k[:16]: v for k, v in nonempty_keys.items()},
        "VERDICT": (f"{len(nonempty_keys)} DISTINCT non-empty responses were never judged, "
                    f"appearing at {sum(len(v) for v in nonempty_keys.values())} cell/turn positions. "
                    "Each is scored no-leak by cache miss, so the effect can only understate leakage."),
    }


def main():
    result = {
        "_provenance": L.provenance(__file__),
        "_purpose": "Verification checks that qualify Phase 0's reported findings before they "
                    "are relied on by A2/A4/A8.",
        "V1_locked_verdict_per_run_independence": v1_locked_verdict_independence(),
        "V2_determinism_true_n": v2_determinism_true_n(),
        "V3_which_manuscript_fits_review_numbering": v3_which_manuscript(),
        "V4_unjudged_nonempty_turns": v4_unjudged_turns(),
    }
    out = L.write_out("p0_verify_followups.json", result)
    for k in ("V1_locked_verdict_per_run_independence", "V2_determinism_true_n",
              "V3_which_manuscript_fits_review_numbering", "V4_unjudged_nonempty_turns"):
        print(f"[{k.split('_')[0]}] {result[k]['VERDICT']}")
    v1 = result["V1_locked_verdict_per_run_independence"]
    print(f"    V1 groups: {v1['n_turn_groups_with_multiple_runs']} multi-run, "
          f"{v1['n_groups_with_distinct_call_fingerprint']} with distinct fingerprints, "
          f"{v1['n_groups_sharing_call_fingerprint']} sharing")
    v2 = result["V2_determinism_true_n"]
    print(f"    V2 rows={v2['n_rows_previously_reported']} distinct={v2['n_distinct_inputs_TRUE_N']} "
          f"multiplicity={v2['multiplicity_histogram']} splits={v2['n_inputs_with_split_locked_verdicts']}")
    v3 = result["V3_which_manuscript_fits_review_numbering"]
    for root, d in v3["roots_scanned"].items():
        print(f"    V3 {root}: {d['n_chapters']} ch, resolved {d['n_requested_resolved']}/{d['n_requested']}, "
              f"missing {d['missing_requested']}, Fig8.1={d['label_for_Figure_8_1']}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
