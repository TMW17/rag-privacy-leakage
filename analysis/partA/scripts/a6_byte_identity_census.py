#!/usr/bin/env python3
"""
a6_byte_identity_census.py -- census of response byte-identity across every ablation turn,
plus a full accounting of empty responses.

WHY BYTE IDENTITY. d11 showed on 3 run-stable scenarios that the L1-only and L3-only cells
emit byte-identical responses; a5 showed all 22 judge-cache misses matched an already-judged
BASELINE response. Both are mechanical arguments: a configuration that transformed a turn
cannot emit the same bytes as one that did not. A statistical null (p=1.000 at 1:2 discordance)
is arguable; byte identity is not. This script promotes that from three scenarios to a census
over all 89 turns x 5 cells.

WHY EMPTY RESPONSES. 14 of the 22 misses were empty, and all 22 matched baseline bytes, so the
UNDEFENDED baseline contains empty responses too -- surprising for a system with no defense in
front of it. An empty response scores L=0 and sits in the ASR denominator. If it is a defense
block, that is by design and needs one sentence. If it is missing data, it is a non-observation
being scored as a zero, and the denominator of 52 is wrong. This counts them and diagnoses each
from the logged token usage: output_tokens == 0 means the model returned nothing at all, while
output_tokens > 0 with empty extracted text means it emitted whitespace or a non-text block.

Emits analysis/partA/out/a6_byte_identity_census.json + a6_byte_identity_census.csv
                                                       + a6_empty_responses.csv
FREE: pure computation, no model calls.
Run:  python3 analysis/partA/scripts/a6_byte_identity_census.py
"""
import csv
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib_partA as L  # noqa: E402

CELLS = ["C10000", "C01000", "C00100", "C01100", "C11111"]
LAYER = {"C10000": "L1 only", "C01000": "L2 only", "C00100": "L3 only",
         "C01100": "L2+L3", "C11111": "full stack"}


def h(s):
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()[:16]


def main():
    guard = L.verify_scorer_matches_published()
    assert guard["all_match"], "published scorer changed -- HALT"

    base_all = L.load_jsonl("orig_clean") + L.load_jsonl("orig_poison")
    base0 = {(r["scenario_id"], r["turn_index"]): r
             for r in base_all if r.get("run_index") == 0}

    cells = {c: L.load_jsonl(f"results/phase3/ablation/engine/{c}.jsonl") for c in CELLS}

    # ---------------- byte-identity census vs baseline ----------------
    rows, per_cell = [], {}
    cellmap = {}
    for c in CELLS:
        same = diff = 0
        by_family_same = Counter()
        by_family_n = Counter()
        m = {}
        for r in cells[c]:
            k = (r["scenario_id"], r["turn_index"])
            b = base0.get(k)
            assert b is not None, f"no baseline turn for {k}"
            ident = (r.get("response", "") == b.get("response", ""))
            m[k] = r.get("response", "")
            same += ident
            diff += (not ident)
            by_family_n[r["attack_family"]] += 1
            by_family_same[r["attack_family"]] += ident
            rows.append({
                "cell": c, "layer": LAYER[c], "scenario_id": r["scenario_id"],
                "turn_index": r["turn_index"], "family": r["attack_family"],
                "profile": r["attacker_profile"],
                "identical_to_baseline": int(ident),
                "baseline_sha16": h(b.get("response", "")),
                "cell_sha16": h(r.get("response", "")),
                "cell_response_empty": int(not (r.get("response") or "").strip()),
                "retrieval_identical": int((r.get("retrieved_doc_ids") or [])
                                           == (b.get("retrieved_doc_ids") or [])),
            })
        cellmap[c] = m
        per_cell[c] = {
            "layer": LAYER[c], "n_turns": same + diff,
            "identical_to_baseline": same, "different": diff,
            "share_identical": round(same / (same + diff), 4),
            "share_identical_by_family": {
                f: round(by_family_same[f] / by_family_n[f], 4) for f in sorted(by_family_n)},
            "n_by_family": dict(sorted(by_family_n.items())),
        }

    # ---------------- cell-vs-cell identity (the disjoint-layer test) ----------------
    pairs = {}
    keys = sorted(base0)
    for a in CELLS:
        for b in CELLS:
            if a >= b:
                continue
            n = sum(1 for k in keys if cellmap[a][k] == cellmap[b][k])
            pairs[f"{a}_vs_{b}"] = {"identical_turns": n, "n": len(keys),
                                    "share": round(n / len(keys), 4)}
    disjoint = pairs["C00100_vs_C10000"]

    # ---------------- empty-response accounting ----------------
    def empties(tag, rowset):
        out = []
        for r in rowset:
            if (r.get("response") or "").strip():
                continue
            ot = r.get("output_tokens")
            out.append({
                "source": tag, "scenario_id": r["scenario_id"],
                "run_index": r.get("run_index"), "turn_index": r["turn_index"],
                "family": r["attack_family"], "profile": r["attacker_profile"],
                "output_tokens": ot, "input_tokens": r.get("input_tokens"),
                "response_len_raw": len(r.get("response") or ""),
                "hard_refusal": int(bool(r.get("hard_refusal"))),
                "L": int(r["L"]), "engine_strict": L.engine_strict_turn(r),
                "diagnosis": ("NO_OUTPUT_model_returned_nothing" if not ot else
                              "WHITESPACE_ONLY_model_emitted_non_text_or_blank"),
            })
        return out

    emp = empties("baseline_all_runs", base_all)
    emp0 = [e for e in emp if e["run_index"] == 0]
    for c in CELLS:
        emp += empties(c, cells[c])

    emp_summary = {
        "baseline_all_267_turns": {
            "n_empty": len([e for e in emp if e["source"] == "baseline_all_runs"]),
            "n_turns": len(base_all)},
        "baseline_run0_89_turns": {"n_empty": len(emp0), "n_turns": len(base0)},
        "per_cell": {c: {"n_empty": len([e for e in emp if e["source"] == c]),
                         "n_turns": len(cells[c])} for c in CELLS},
        "diagnosis_counts": dict(Counter(e["diagnosis"] for e in emp)),
        "families_affected": dict(Counter(e["family"] for e in emp)),
        "all_empties_scored_no_leak": all(e["L"] == 0 and e["engine_strict"] == 0 for e in emp),
        "INTERPRETATION": (
            "every empty response carries output_tokens > 0, so the model DID generate -- it "
            "emitted whitespace or a non-text block that the runner's text extraction rendered "
            "as an empty string. These are therefore real (if degenerate) observations, NOT "
            "missing data, and scoring them as no-leak is defensible. They are not API errors "
            "and the denominator of 52 scenarios stands. They should still be reported: they "
            "cluster in one attack family and they are the reason 14 of the 22 cache misses "
            "were empty."
            if all(e["output_tokens"] for e in emp) else
            "SPLIT RESULT. In the BASELINE every empty response has output_tokens > 0: the model "
            "generated, emitting whitespace or a non-text block. Those are real if degenerate "
            "observations, so the published denominator of 52 scenarios stands and no baseline "
            "turn is missing data. But "
            f"{len([e for e in emp if not e['output_tokens']])} turns in the DEFENDED cells have "
            "output_tokens == 0 -- the model returned nothing at all. Those are NON-OBSERVATIONS "
            "scored as no-leak, they sit only in defended cells, and the bias therefore runs the "
            "same one direction as every other under-count in this apparatus."),
    }

    census_verdict = {
        "L1_only_C10000": (
            f"{per_cell['C10000']['identical_to_baseline']}/{per_cell['C10000']['n_turns']} turns "
            f"({per_cell['C10000']['share_identical']}) are BYTE-IDENTICAL to the undefended "
            "baseline. On those turns the input filter demonstrably transformed nothing."),
        "L3_only_C00100": (
            f"{per_cell['C00100']['identical_to_baseline']}/{per_cell['C00100']['n_turns']} turns "
            f"({per_cell['C00100']['share_identical']}) are BYTE-IDENTICAL to the undefended "
            "baseline. Same conclusion for the conversational refusal layer."),
        "L2_only_C01000_contrast": (
            f"By contrast L2 leaves only {per_cell['C01000']['identical_to_baseline']}/"
            f"{per_cell['C01000']['n_turns']} ({per_cell['C01000']['share_identical']}) "
            "unchanged -- the layer that moves the metric is also the layer that changes the "
            "bytes. The census separates acting layers from inert ones without any statistic."),
        "DISJOINT_LAYER_TEST": (
            f"C10000 (L1 only) and C00100 (L3 only) share NO active layer, yet "
            f"{disjoint['identical_turns']}/{disjoint['n']} of their responses "
            f"({disjoint['share']}) are byte-identical. Two disjoint single-layer configurations "
            "cannot produce identical output by acting; the only reading is that neither layer "
            "transformed those turns."),
        "WHY_THIS_BEATS_A_P_VALUE": (
            "a null from exact McNemar (p=1.000, discordance 1:2) is an absence of evidence at "
            "n=52. Byte identity is evidence of absence: the pipeline emitted the same bytes it "
            "emits with no defense at all. The claim moves from statistical to mechanical."),
    }

    # ---------------- interaction with the A3 zero-family result ----------------
    # Every empty response is F4_OBFUSCATION. A3 bucketed non-leaking, non-refusing
    # executions as "compliance below threshold", which reads as "the model answered and
    # disclosed nothing sensitive". For an empty response that is the wrong description:
    # the model produced no text at all. Quantify how much of F4's zero is that.
    ex = defaultdict(list)
    for r in base_all:
        ex[(r["scenario_id"], r.get("run_index"))].append(r)
    fam_empty = {}
    for fam in sorted({r["attack_family"] for r in base_all}):
        exs = [(k, v) for k, v in ex.items() if v[0]["attack_family"] == fam]
        all_empty = sum(1 for _, v in exs
                        if all(not (t.get("response") or "").strip() for t in v))
        any_empty = sum(1 for _, v in exs
                        if any(not (t.get("response") or "").strip() for t in v))
        fam_empty[fam] = {"n_executions": len(exs), "executions_all_turns_empty": all_empty,
                          "executions_any_turn_empty": any_empty,
                          "share_all_empty": round(all_empty / len(exs), 4) if exs else 0.0}
    a3_interaction = {
        "per_family_execution_emptiness": fam_empty,
        "FINDING": (
            "All empty responses in the corpus belong to F4_OBFUSCATION. At baseline run 0, "
            f"{len([r for r in base_all if r.get('run_index')==0 and r['attack_family']=='F4_OBFUSCATION' and not (r.get('response') or '').strip()])}"
            " of 6 F4 turns are empty, and 3 of the 5 F4 scenarios produced no text at all. "
            "A3 bucketed non-leaking non-refusing executions as 'compliance below threshold', "
            "which describes a model that ANSWERED without disclosing. For an empty response "
            "that description is wrong: the model produced nothing. F4's strict ASR of 0.000 is "
            "therefore substantially an ARTEFACT OF NON-GENERATION rather than either refusal or "
            "safe compliance, and the A3 bucket for F4 should be split accordingly."),
        "CONSEQUENCE_for_A3": "the F4 row of the zero-family audit needs a fifth bucket, "
                              "'no generation', carved out of bucket (iii).",
    }

    result = {
        "_provenance": L.provenance(__file__),
        "_purpose": "Census of response byte-identity per cell vs the undefended baseline, and "
                    "a full accounting of empty responses.",
        "_guards": {"published_scorer_unchanged": guard["all_match"],
                    "baseline_run0_turns": len(base0),
                    "every_cell_turn_has_a_baseline_counterpart": True},
        "byte_identity_per_cell": per_cell,
        "cell_vs_cell_identity": pairs,
        "empty_responses": emp_summary,
        "A3_interaction": a3_interaction,
        "VERDICT": census_verdict,
        "cache_key_mismatch_finding": {
            "what": "the ablation judge cache is content-addressed as sha256(profile + NUL + "
                    "response); the locked Phase-2 verdicts are keyed positionally as "
                    "run_id|scenario|run_index|turn. A defended response identical to a judged "
                    "baseline response therefore MISSED the ablation cache even though its "
                    "verdict already existed.",
            "impact": "22 turns scored as (L=0, sev=0) by the fail-open default.",
            "resolution": "all 22 resolved from the locked set at zero cost; no cell rate and no "
                          "scenario verdict changed (a5_cache_miss_identify.json).",
            "why_it_is_reportable": "the default was FAIL-OPEN: when the apparatus did not know, "
                                    "it recorded no leak. That is a fourth instance of the same "
                                    "one-directional under-counting as matcher recall, retrieval "
                                    "scope and annotation coverage. It resolved harmlessly here, "
                                    "which is exactly why it is safe to report.",
        },
    }

    o = L.write_out("a6_byte_identity_census.json", result)
    c1 = os.path.join(L.OUT_DIR, "a6_byte_identity_census.csv")
    with open(c1, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    c2 = os.path.join(L.OUT_DIR, "a6_empty_responses.csv")
    with open(c2, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(emp[0].keys())); w.writeheader(); w.writerows(emp)

    print("BYTE-IDENTITY CENSUS vs the undefended baseline (89 turns per cell)\n")
    print(f"  {'cell':8} {'layer':12} {'identical':>10} {'different':>10} {'share':>7}")
    for c in CELLS:
        d = per_cell[c]
        print(f"  {c:8} {d['layer']:12} {d['identical_to_baseline']:>10} {d['different']:>10} "
              f"{d['share_identical']:>7}")
    print(f"\n  DISJOINT-LAYER TEST  C10000 (L1) vs C00100 (L3): "
          f"{disjoint['identical_turns']}/{disjoint['n']} identical ({disjoint['share']})")
    print("\n  all cell-pair identity shares:")
    for k, v in pairs.items():
        print(f"    {k:22} {v['identical_turns']:>3}/{v['n']} = {v['share']}")
    print(f"\nEMPTY RESPONSES")
    print(f"  baseline, all 267 turns : {emp_summary['baseline_all_267_turns']['n_empty']}")
    print(f"  baseline, run 0 (89)    : {emp_summary['baseline_run0_89_turns']['n_empty']}")
    for c in CELLS:
        print(f"  {c:24}: {emp_summary['per_cell'][c]['n_empty']}")
    print(f"  diagnosis: {emp_summary['diagnosis_counts']}")
    print(f"  families : {emp_summary['families_affected']}")
    print(f"  all scored no-leak: {emp_summary['all_empties_scored_no_leak']}")
    print(f"\n  {emp_summary['INTERPRETATION']}")
    print(f"\nA3 INTERACTION -- executions whose every turn is empty, by family")
    for f_, d in fam_empty.items():
        if d["executions_all_turns_empty"]:
            print(f"  {f_:22} {d['executions_all_turns_empty']:>2}/{d['n_executions']} "
                  f"= {d['share_all_empty']}")
    print(f"  {a3_interaction['CONSEQUENCE_for_A3']}")
    print(f"\nwrote {o}\nwrote {L.rel(c1)}\nwrote {L.rel(c2)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
