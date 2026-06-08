"""
compute_defended_kappa.py  (Phase 3-4 correction, Point 1)

Computes judge-vs-human Cohen's kappa ON THE DEFENDED DISTRIBUTION from the author's hand labels.
The 0.827 in the report was validated on UNDEFENDED text; this re-measures the judge against the
human on redacted/refused/degraded (defended) output, where the judge was suspected of over-flagging.

NO model calls. Joins:
  results/phase3_4/judge_defended_calibration/annotation_defended.csv   (human labels: L_human, ...)
  results/phase3_4/judge_defended_calibration/sample_manifest.json      (judge/engine verdicts on disk)
by row_id. Judge/engine verdicts were resolved by the same path that produced the 0.192/0.173 ASR.

Writes results/phase3_4/judge_defended_calibration/kappa_defended.json
"""
import csv
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIR = os.path.join(ROOT, "results", "phase3_4", "judge_defended_calibration")
CSV = os.path.join(DIR, "annotation_defended.csv")
MANIFEST = os.path.join(DIR, "sample_manifest.json")
OUT = os.path.join(DIR, "kappa_defended.json")
UNDEFENDED_KAPPA = 0.827   # results/judge_calibration/kappa_results.json: judge_vs_human binary


def cohen_kappa(pairs):
    """pairs: list of (rater_x, rater_y) in {0,1}. Returns Cohen's kappa."""
    n = len(pairs)
    n11 = sum(1 for x, y in pairs if x == 1 and y == 1)
    n10 = sum(1 for x, y in pairs if x == 1 and y == 0)
    n01 = sum(1 for x, y in pairs if x == 0 and y == 1)
    n00 = sum(1 for x, y in pairs if x == 0 and y == 0)
    po = (n11 + n00) / n
    px1 = (n11 + n10) / n
    py1 = (n11 + n01) / n
    pe = px1 * py1 + (1 - px1) * (1 - py1)
    kappa = (po - pe) / (1 - pe) if (1 - pe) else 1.0
    return {"kappa": round(kappa, 4), "po": round(po, 4), "pe": round(pe, 4),
            "n11": n11, "n10": n10, "n01": n01, "n00": n00, "n": n}


def _raw_agreement(k_jh):
    """Raw (observed) agreement, prevalence-independent and comparable across samples."""
    undef = json.load(open(os.path.join(ROOT, "results", "judge_calibration", "kappa_results.json")))
    um, un = undef["agreement"]["judge_matches_human"], undef["sample_size"]
    dm, dn = k_jh["n11"] + k_jh["n00"], k_jh["n"]
    return {
        "undefended": {"matches": um, "n": un, "rate": round(um / un, 4)},
        "defended": {"matches": dm, "n": dn, "rate": round(dm / dn, 4)},
        "note": "Raw agreement is prevalence-independent and directly comparable across the two "
                "samples; kappa is prevalence-sensitive and the judge-positive rate differs between "
                f"them ({undef['label_distributions']['L_judge']['1']}/{un} undefended vs "
                f"{k_jh['n11'] + k_jh['n10']}/{dn} defended), which is why both are reported.",
    }


def main():
    human = {}
    for r in csv.DictReader(open(CSV)):
        lv = (r["L_human"] or "").strip()
        if lv == "":
            raise SystemExit(f"row {r['row_id']} has empty L_human — annotation incomplete; STOP.")
        human[int(r["row_id"])] = {"L": int(lv),
                                   "sev": (r["severity_human"] or "").strip(),
                                   "type": (r["leak_type_human"] or "").strip()}
    manifest = json.load(open(MANIFEST))
    recs = {rec["row_id"]: rec for rec in manifest["records"]}
    assert set(human) == set(recs), "row_id mismatch between CSV and manifest"

    jh, eh, je = [], [], []   # judge-human, engine-human, judge-engine pairs
    rows = []
    for rid in sorted(human):
        Lh = human[rid]["L"]
        Lj = int(recs[rid]["L_judge"])
        Le = int(recs[rid]["engine_L"])
        jh.append((Lj, Lh)); eh.append((Le, Lh)); je.append((Lj, Le))
        rows.append({"row_id": rid, "scenario": recs[rid]["scenario"],
                     "stratum": recs[rid]["stratum"], "L_human": Lh, "L_judge": Lj, "L_engine": Le})

    k_jh = cohen_kappa(jh)
    k_eh = cohen_kappa(eh)
    k_je = cohen_kappa(je)

    # Over-flag analysis on the judge-positive cases (we sampled ALL judge-positives in the pool,
    # so this denominator is the full judge-positive set, not a subsample).
    judge_pos = [r for r in rows if r["L_judge"] == 1]
    judge_overflags = [r for r in judge_pos if r["L_human"] == 0]   # judge=leak, human=no-leak
    human_pos = [r for r in rows if r["L_human"] == 1]
    judge_misses = [r for r in human_pos if r["L_judge"] == 0]      # human=leak, judge=missed

    result = {
        "purpose": "Point 1: judge-vs-human Cohen's kappa on the DEFENDED distribution.",
        "no_new_model_calls": True,
        "n_records": len(rows),
        "sample_design": {
            "configs": manifest["sample_configs"], "seed": manifest["seed"],
            "stratified": True,
            "selected_stratum_counts": manifest["selected_stratum_counts"],
            "note": "Stratified, enriched for judge-positives (all 18 judge-flagged in the 143-pool "
                    "were included), mirroring the Phase-2 46-record calibration design. The kappa is "
                    "on this stratified set; the over-flag COUNT below is exact for the pool's "
                    "judge-positive cases (denominator = all judge-positives), not a population rate.",
        },
        "kappa_defended": {
            "judge_vs_human_binary": k_jh,
            "engine_vs_human_binary": k_eh,
            "judge_vs_engine_binary": k_je,
        },
        "comparison_to_undefended": {
            "undefended_judge_vs_human": UNDEFENDED_KAPPA,
            "defended_judge_vs_human": k_jh["kappa"],
            "delta": round(k_jh["kappa"] - UNDEFENDED_KAPPA, 4),
        },
        "raw_agreement": _raw_agreement(k_jh),
        "judge_PPV_on_defended": {
            "human_confirmed": k_jh["n11"], "judge_flagged": k_jh["n11"] + k_jh["n10"],
            "ppv": round(k_jh["n11"] / (k_jh["n11"] + k_jh["n10"]), 4) if (k_jh["n11"] + k_jh["n10"]) else None,
            "note": "valid because the sample took ALL judge-positives in the 143-pool; raw count, "
                    "not a population leak rate.",
        },
        "over_flagging": {
            "direction": "judge flags leak (L_judge=1) where human says no leak (L_human=0)",
            "judge_positive_n": len(judge_pos),
            "judge_overflag_n": len(judge_overflags),
            "judge_overflag_rate_among_judge_positives": round(len(judge_overflags) / len(judge_pos), 4)
            if judge_pos else None,
            "judge_overflag_rows": [r["row_id"] for r in judge_overflags],
            "judge_miss_n_among_human_leaks": len(judge_misses),
            "human_leak_n": len(human_pos),
            "judge_miss_rows": [r["row_id"] for r in judge_misses],
        },
        "label_totals": {
            "human_leaks": sum(r["L_human"] for r in rows),
            "judge_leaks": sum(r["L_judge"] for r in rows),
            "engine_leaks": sum(r["L_engine"] for r in rows),
        },
        "per_record": rows,
    }
    json.dump(result, open(OUT, "w"), indent=2)
    # console summary
    print(f"n = {len(rows)} defended records")
    print(f"label totals: human_leaks={result['label_totals']['human_leaks']}, "
          f"judge_leaks={result['label_totals']['judge_leaks']}, "
          f"engine_leaks={result['label_totals']['engine_leaks']}")
    print(f"\nDEFENDED judge-vs-human kappa = {k_jh['kappa']}  (po={k_jh['po']}, pe={k_jh['pe']}, "
          f"n11={k_jh['n11']} n10={k_jh['n10']} n01={k_jh['n01']} n00={k_jh['n00']})")
    print(f"   vs UNDEFENDED judge-vs-human kappa = {UNDEFENDED_KAPPA}  "
          f"(delta {result['comparison_to_undefended']['delta']})")
    print(f"engine-vs-human kappa = {k_eh['kappa']}   judge-vs-engine kappa = {k_je['kappa']}")
    print(f"\nover-flagging: judge flagged {len(judge_pos)} leaks; human disagreed on "
          f"{len(judge_overflags)} -> over-flag {result['over_flagging']['judge_overflag_rate_among_judge_positives']} "
          f"of judge-positives (rows {result['over_flagging']['judge_overflag_rows']})")
    print(f"judge missed {len(judge_misses)} of {len(human_pos)} human-confirmed leaks "
          f"(rows {result['over_flagging']['judge_miss_rows']})")
    print(f"\nwrote {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
