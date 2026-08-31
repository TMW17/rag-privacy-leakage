#!/usr/bin/env python3
"""
a1_defended_ppv_by_family.py -- per-family PPV of the judge on the DEFENDED sample.

THE QUESTION (external review): "Of the seven human-confirmed leaks among the eighteen
flags, how many are F2?" The thesis calls 17.3% a LOWER bound because the judge's three
misses were all linkage. But the over-flags outnumber the misses 11:3 and concentrate on
the same family, so the direction of the bias is contested. This script answers it with
counts.

DESIGN CONSTRAINT that governs every number here: the 46-record defended sample is
STRATIFIED and takes a CENSUS of judge-positives (all 18 in the 143-response pool) while
UNDERSAMPLING the negatives (13 of 59 degraded_answer, 13 of 64 redacted_residue, 2 of 2
clean_refusal). Consequences, stated once and enforced throughout:
  * PPV (human-confirmed / judge-flagged) IS valid -- the positives are a census.
  * FPR and specificity are NOT valid -- the negatives are subsampled. kappa_defended.json
    §7.8 says exactly this. A rate of 11/36 = 0.306 must NOT be reported as an FPR.
  * FOR (false-omission rate) is measurable only ON THE EXAMINED NEGATIVES, and scaling it
    to the pool is an EXTRAPOLATION, reported as such with its sampling weights.

Sources (read-only):
  results/phase3_4/judge_defended_calibration/sample_manifest.json   (judge side + strata)
  results/phase3_4/judge_defended_calibration/annotation_defended.csv (human side)
  results/phase3_4/judge_defended_calibration/kappa_defended.json     (published targets)

Emits analysis/partA/out/a1_defended_ppv_by_family.json + a1_defended_ppv_by_family.csv.
FREE: pure computation, no model calls.
Run:  python3 analysis/partA/scripts/a1_defended_ppv_by_family.py
"""
import csv
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib_partA as L  # noqa: E402

MANIFEST = "results/phase3_4/judge_defended_calibration/sample_manifest.json"
KAPPA = "results/phase3_4/judge_defended_calibration/kappa_defended.json"


def clopper_pearson(k, n, alpha=0.05):
    """Exact binomial interval. Single-digit n here, so nothing normal-approximate."""
    if n == 0:
        return None
    try:
        from statistics import NormalDist  # noqa: F401
    except Exception:
        pass
    # Beta quantiles via bisection on the regularised incomplete beta (no scipy dependency).
    def betacdf(x, a, b, it=200):
        if x <= 0:
            return 0.0
        if x >= 1:
            return 1.0
        # continued fraction (Lentz) for I_x(a,b)
        import math
        lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
        front = math.exp(math.log(x) * a + math.log(1 - x) * b - lbeta) / a
        f, c, d = 1.0, 1.0, 0.0
        for i in range(it):
            m = i // 2
            if i == 0:
                num = 1.0
            elif i % 2 == 0:
                num = (m * (b - m) * x) / ((a + 2 * m - 1) * (a + 2 * m))
            else:
                num = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
            d = 1.0 + num * d
            d = 1e-30 if abs(d) < 1e-30 else d
            d = 1.0 / d
            c = 1.0 + num / c
            c = 1e-30 if abs(c) < 1e-30 else c
            f *= c * d
            if abs(1.0 - c * d) < 1e-12:
                break
        return front * (f - 1.0)

    def invbeta(p, a, b):
        lo, hi = 0.0, 1.0
        for _ in range(200):
            mid = (lo + hi) / 2
            if betacdf(mid, a, b) < p:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    lo = 0.0 if k == 0 else invbeta(alpha / 2, k, n - k + 1)
    hi = 1.0 if k == n else invbeta(1 - alpha / 2, k + 1, n - k)
    return [round(lo, 4), round(hi, 4)]


def main():
    man = L.load_json(MANIFEST)
    kap = L.load_json(KAPPA)
    recs = {str(r["row_id"]): r for r in man["records"]}

    csv_path = L.path("defended_calib")
    human = {str(r["row_id"]): r for r in csv.DictReader(open(csv_path, encoding="utf-8"))}

    ids = sorted(set(recs) & set(human), key=lambda s: int(s))
    assert len(ids) == 46, f"join produced {len(ids)} rows, expected 46"

    rows = []
    for rid in ids:
        m, h = recs[rid], human[rid]
        assert m["family"] == h["family"], f"family mismatch on row {rid}"
        rows.append({
            "row_id": int(rid),
            "config": m["config"],
            "scenario": m["scenario"],
            "turn": m["turn"],
            "profile": m["profile"],
            "family": m["family"],
            "stratum": m["stratum"],
            "L_judge": int(m["L_judge"] or 0),
            "severity_judge": int(m["severity_judge"] or 0),
            "leak_type_judge": m.get("leak_type_judge"),
            "L_human": int(h["L_human"] or 0),
            "leak_type_human": h.get("leak_type_human", ""),
            "severity_human": h.get("severity_human", ""),
            "cell": None,
            "classified_by_model": "n/a -- deterministic join of committed judge and human labels",
        })
    for r in rows:
        r["cell"] = {(1, 1): "TP_confirmed", (1, 0): "FP_overflag",
                     (0, 1): "FN_miss", (0, 0): "TN"}[(r["L_judge"], r["L_human"])]

    # ---- guard: reproduce the published 2x2 before any new number is reported ----
    cells = Counter(r["cell"] for r in rows)
    pub = kap["kappa_defended"]["judge_vs_human_binary"]
    guard = {
        "published_n11_TP": pub["n11"], "recomputed_TP": cells["TP_confirmed"],
        "published_n10_FP": pub["n10"], "recomputed_FP": cells["FP_overflag"],
        "published_n01_FN": pub["n01"], "recomputed_FN": cells["FN_miss"],
        "published_n00_TN": pub["n00"], "recomputed_TN": cells["TN"],
    }
    guard["all_match"] = (guard["recomputed_TP"] == pub["n11"] and guard["recomputed_FP"] == pub["n10"]
                          and guard["recomputed_FN"] == pub["n01"] and guard["recomputed_TN"] == pub["n00"])
    assert guard["all_match"], f"2x2 does not reproduce the published one: {guard}"

    judge_pos = [r for r in rows if r["L_judge"] == 1]
    assert len(judge_pos) == 18, f"{len(judge_pos)} judge positives, expected 18"
    assert all(r["stratum"] == "judge_flagged_leak" for r in judge_pos), \
        "a judge positive fell outside the judge_flagged_leak stratum"

    # ---- THE ANSWER: per-family PPV over the census of judge positives ----
    by_fam = defaultdict(lambda: {"flagged": 0, "confirmed": 0, "overflag": 0})
    for r in judge_pos:
        d = by_fam[r["family"]]
        d["flagged"] += 1
        d["confirmed"] += r["L_human"]
        d["overflag"] += (1 - r["L_human"])
    ppv_by_family = {}
    for fam, d in sorted(by_fam.items()):
        ppv_by_family[fam] = {
            "judge_flagged": d["flagged"],
            "human_confirmed": d["confirmed"],
            "over_flagged": d["overflag"],
            "PPV": round(d["confirmed"] / d["flagged"], 4) if d["flagged"] else None,
            "PPV_95CI_exact": clopper_pearson(d["confirmed"], d["flagged"]),
        }

    overall_ppv = round(cells["TP_confirmed"] / len(judge_pos), 4)

    # ---- CLUSTERING: the 18 flags are not 18 independent observations ----
    # C01100 and C11111 are sampled separately, so the same (scenario, turn) can appear twice.
    # Treating those as independent narrows every interval spuriously. Collapse to the
    # (scenario, turn) unit -- confirmed if ANY config's response was human-confirmed -- and
    # report both the naive and the clustered figure.
    units = defaultdict(list)
    for r in judge_pos:
        units[(r["scenario"], r["turn"])].append(r)
    dup_units = {f"{k[0]}|t{k[1]}": len(v) for k, v in sorted(units.items()) if len(v) > 1}
    u_conf = sum(1 for v in units.values() if any(x["L_human"] for x in v))
    u_disagree = {f"{k[0]}|t{k[1]}": [x["config"] + ":L_human=" + str(x["L_human"]) for x in v]
                  for k, v in sorted(units.items())
                  if len(v) > 1 and len({x["L_human"] for x in v}) > 1}
    clustered = {
        "n_flags_naive": len(judge_pos),
        "n_distinct_scenario_turn_units": len(units),
        "units_appearing_twice": dup_units,
        "human_confirmed_units": u_conf,
        "PPV_clustered": round(u_conf / len(units), 4),
        "PPV_clustered_95CI_exact": clopper_pearson(u_conf, len(units)),
        "PPV_naive": overall_ppv,
        "units_whose_two_configs_got_OPPOSITE_human_labels": u_disagree,
        "opposite_label_note":
            "a unit labelled differently under its two configurations is NOT necessarily an "
            "annotator inconsistency: the two pipelines can emit different responses for the "
            "same scenario turn. response_bytes_identical below settles it per unit.",
        "response_identity_for_opposite_label_units": {
            f"{k[0]}|t{k[1]}": {
                "configs": [x["config"] for x in v],
                "response_sha256_16": [__import__("hashlib").sha256(
                    (recs[str(x["row_id"])]["response"] or "").encode()).hexdigest()[:16] for x in v],
                "response_bytes_identical": len({recs[str(x["row_id"])]["response"] for x in v}) == 1,
            } for k, v in units.items() if len(v) > 1 and len({x["L_human"] for x in v}) > 1},
        "IMPLICATION":
            "every interval computed on n=18 is optimistic; the effective sample behind PPV is "
            f"{len(units)} scenario-turns, and they are further concentrated in one family.",
    }

    # ---- the misses, by family (the thesis's stated basis for 'lower bound') ----
    misses = [r for r in rows if r["cell"] == "FN_miss"]
    miss_fams = dict(Counter(r["family"] for r in misses))

    # ---- FOR on the EXAMINED negatives, and the pool extrapolation ----
    examined_neg = [r for r in rows if r["L_judge"] == 0]
    for_examined = round(len(misses) / len(examined_neg), 4) if examined_neg else None
    pool = man["stratum_pool_counts"]
    sel = man["selected_stratum_counts"]
    neg_strata = [s for s in pool if s != "judge_flagged_leak"]
    per_stratum, extrapolated_missed = {}, 0.0
    for s in neg_strata:
        ex = [r for r in examined_neg if r["stratum"] == s]
        m_ = sum(1 for r in ex if r["cell"] == "FN_miss")
        rate = (m_ / len(ex)) if ex else None
        est = (rate * pool[s]) if rate is not None else None
        per_stratum[s] = {"pool_n": pool[s], "examined_n": len(ex), "misses_found": m_,
                          "FOR_in_stratum": round(rate, 4) if rate is not None else None,
                          "estimated_misses_in_pool": round(est, 2) if est is not None else None}
        if est:
            extrapolated_missed += est

    result = {
        "_provenance": L.provenance(__file__),
        "_purpose": "Per-family PPV of the judge on the defended distribution; whether the F2 "
                    "residual survives human confirmation.",
        "_sampling_design": {
            "n": 46, "pool_unique_responses": man["pool_unique_responses"],
            "stratum_pool_counts": pool, "selected_stratum_counts": sel,
            "judge_positives_are_a_census": True,
            "judge": man["judge"],
            "VALID_ON_THIS_SAMPLE": ["PPV (positives are a census)", "raw counts"],
            "INVALID_ON_THIS_SAMPLE": [
                "FPR / specificity (negatives are subsampled; 11/36 = 0.306 is NOT an FPR)",
                "any population leak rate"],
        },
        "guard_2x2_reproduces_published": guard,
        "overall": {
            "judge_flagged": len(judge_pos),
            "human_confirmed": cells["TP_confirmed"],
            "over_flagged": cells["FP_overflag"],
            "PPV": overall_ppv,
            "PPV_95CI_exact": clopper_pearson(cells["TP_confirmed"], len(judge_pos)),
            "published_ppv_for_comparison": kap["judge_PPV_on_defended"]["ppv"],
        },
        "ANSWER_ppv_by_family": ppv_by_family,
        "clustering": clustered,
        "misses_by_family": {"n_misses": len(misses), "families": miss_fams,
                             "row_ids": [r["row_id"] for r in misses]},
        "false_omission": {
            "examined_negatives": len(examined_neg),
            "FOR_on_examined_negatives": for_examined,
            "per_negative_stratum": per_stratum,
            "extrapolated_missed_leaks_in_pool": round(extrapolated_missed, 2),
            "over_flags_observed_census": cells["FP_overflag"],
            "EXTRAPOLATION_WARNING":
                "estimated_misses_in_pool is an extrapolation from 26 examined negatives to a "
                "123-response negative pool, at 1-3 observed misses per stratum. Its sampling "
                "error is large and it is NOT a measured quantity. It is reported only to show "
                "which way the net bias could go, not to settle it.",
        },
    }

    o = L.write_out("a1_defended_ppv_by_family.json", result)
    csv_out = os.path.join(L.OUT_DIR, "a1_defended_ppv_by_family.csv")
    with open(csv_out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"guard 2x2 reproduces published: {guard['all_match']}  "
          f"(TP {cells['TP_confirmed']} / FP {cells['FP_overflag']} / "
          f"FN {cells['FN_miss']} / TN {cells['TN']})\n")
    print(f"OVERALL PPV = {cells['TP_confirmed']}/{len(judge_pos)} = {overall_ppv}  "
          f"95% CI {result['overall']['PPV_95CI_exact']}\n")
    print("PPV BY FAMILY (judge positives are a census -> PPV is valid)")
    print(f"  {'family':22} {'flagged':>8} {'confirmed':>10} {'overflag':>9} {'PPV':>7}  95% CI")
    for fam, d in ppv_by_family.items():
        print(f"  {fam:22} {d['judge_flagged']:>8} {d['human_confirmed']:>10} "
              f"{d['over_flagged']:>9} {str(d['PPV']):>7}  {d['PPV_95CI_exact']}")
    print(f"\nCLUSTERING: {clustered['n_flags_naive']} flags span "
          f"{clustered['n_distinct_scenario_turn_units']} distinct scenario-turns "
          f"({len(dup_units)} appear under both configs)")
    print(f"  PPV naive {clustered['PPV_naive']} {result['overall']['PPV_95CI_exact']} -> "
          f"clustered {clustered['PPV_clustered']} {clustered['PPV_clustered_95CI_exact']}")
    for k, v in clustered["response_identity_for_opposite_label_units"].items():
        print(f"  opposite human labels on {k}: configs {v['configs']}, "
              f"responses byte-identical = {v['response_bytes_identical']}")
    print(f"\nmisses (human leak, judge silent): n={len(misses)} families={miss_fams}")
    print(f"FOR on the 26 examined negatives = {for_examined}")
    print(f"extrapolated misses across the {sum(pool[s] for s in neg_strata)}-response negative pool "
          f"= {round(extrapolated_missed,2)}  vs {cells['FP_overflag']} over-flags (census)")
    print(f"\nwrote {o}\nwrote {L.rel(csv_out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
