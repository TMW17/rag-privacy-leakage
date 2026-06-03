"""
l2_llm_report.py — honest writeup + focused trade-off figure for the L2-LLM experiment.

Corrects the security read: the 0.08 noise floor was derived for the n=52 OVERALL metric; F2 is a
10-scenario family (binomial SE ~0.16). The proper paired test is McNemar on the discordant pairs.
Headline framing (per review): UTILITY win is the solid finding (n=30, paired, mechanistic); the F2
drop is DIRECTIONAL, NOT statistically significant at n=10; the per-scenario diagnosis prediction is
FALSIFIED. C01000-LLM is L2-LLM ALONE; 17.3% (Presidio full stack) stays the primary headline.
"""
import json
import os
import sys
from math import comb

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "results", "phase3", "l2_llm")
RES = os.path.join(OUT, "l2_llm_results.json")


def mcnemar_exact(b, c):
    nd = b + c
    return round(2 * sum(comb(nd, k) for k in range(0, min(b, c) + 1)) / 2 ** nd, 4)


def main():
    d = json.load(open(RES))
    s = d["summary"]
    ps = s["per_scenario"]
    pq = d["per_query_utility"]

    closed = [r["scenario"] for r in ps if r["presidio_strict"] == 1 and r["llm_strict"] == 0]
    rose = [r["scenario"] for r in ps if r["presidio_strict"] == 0 and r["llm_strict"] == 1]
    p_mcnemar = mcnemar_exact(len(closed), len(rose))
    sig = p_mcnemar < 0.05

    # utility win quantification (paired per-query cp_llm vs cp_presidio_C11111)
    pairs = [(r.get("cp_llm"), r.get("cp_presidio_C11111")) for r in pq if r.get("cp_llm") is not None]
    better = [(a, b) for a, b in pairs if a is not None and b is not None and a > b + 1e-9]
    worse = [(a, b) for a, b in pairs if a is not None and b is not None and a < b - 1e-9]
    drivers = sorted([r for r in pq if r.get("cp_llm") is not None and r.get("cp_presidio_C11111") is not None
                      and r["cp_llm"] - r["cp_presidio_C11111"] > 0.1],
                     key=lambda r: -(r["cp_llm"] - r["cp_presidio_C11111"]))

    correction = {
        "security_significance": {
            "f2_presidio": s["security_F2_judged_strict"]["C01000_presidio"],
            "f2_llm": s["security_F2_judged_strict"]["C01000_LLM"],
            "f2_baseline": s["security_F2_judged_strict"]["C00000_baseline"],
            "n_scenarios": 10, "per_family_binomial_SE_at_p0.5": 0.158,
            "WRONG_floor_used_pre-reg": "0.08 (that floor was for the n=52 OVERALL metric, not a 10-scenario family)",
            "paired_test": f"McNemar exact two-sided on discordant pairs ({len(closed)} closed, {len(rose)} rose) = p {p_mcnemar}",
            "verdict": "DIRECTIONAL, NOT statistically significant at n=10" if not sig else "significant",
            "steelman": "F2 sat at 0.60/0.70/0.60/0.70 across ALL four prior Presidio configs; LLM-L2's 0.40 is "
                        "below that entire historical plateau -> the strongest argument the drop is real.",
            "two_rises_caveat": f"{rose} were CLEAN under Presidio and leaked under a strictly-more-redacting layer "
                        "-> mechanically incoherent; most likely fresh-vs-reused judge variance (Presidio's 0.70 is "
                        "reused-locked verdicts; LLM's 0.40 is fresh-judged). Responses were NOT persisted, so this "
                        "cannot be attributed to noise-vs-redaction without re-judging (future work).",
            "prediction_FALSIFIED": "pre-registered '4 recall-miss close, 2 genuine-linkage survive' did NOT hold: "
                        "recall-miss P1-LINK-007 SURVIVED; genuine-linkage P2-LINK-002 CLOSED. The recall-miss/"
                        "linkage decomposition does not predict per-scenario closure (labels are partly judge-dependent).",
        },
        "utility_finding": {
            "mean_cp": {"llm": s["utility_benign"]["context_precision"]["C01000_LLM"],
                        "presidio_C11111_proxy": s["utility_benign"]["context_precision"]["C11111_presidio_proxy"],
                        "no_redaction_C00000": s["utility_benign"]["context_precision"]["C00000_no_redaction"]},
            "n_queries_cp_better": len(better), "n_worse": len(worse),
            "drivers": [{"id": r["id"], "cp_llm": r["cp_llm"], "cp_presidio": r["cp_presidio_C11111"]} for r in drivers],
            "mechanism": "the LLM redactor avoids Presidio's DATE_TIME over-redaction of schedules "
                         "('Monday-Friday 08:00-16:00'->[DATE_TIME]); the cp lift is concentrated in the few schedule "
                         "queries Presidio cratered (rest ~unchanged). 0.755==C00000's 0.755 is a coincidental mean, "
                         "NOT proof of zero cost.",
            "robust": "n=30, paired, mechanistically explained -> the SOLID finding of this experiment.",
        },
        "headline": "C01000-LLM is L2-LLM ALONE (not the full stack). 17.3% (Presidio full stack, C11111) stays the "
                    "PRIMARY headline. C11111-LLM (LLM redactor swapped into the full stack) is the unrun next experiment.",
        "limitations": ["same-vendor redactor(Sonnet)+judge(Opus) coupling (disclosed; cross-vendor re-judge = future work)",
                        "fresh-vs-reused judge confound on F2 (fix = re-judge Presidio F2 fresh ~$1.2; disclose-don't-spend under one-shot)",
                        "n=10 F2 family -> low power; responses not persisted (logging gap)",
                        "F2 still 0.40 -> linkability NOT eliminated"],
    }
    d["CORRECTED_INTERPRETATION"] = correction
    json.dump(d, open(RES, "w"), indent=2, ensure_ascii=False)

    _figure(s)
    _md(s, correction, closed, rose, p_mcnemar, drivers, better)
    # console
    print("=" * 78)
    print("L2-LLM REPORT (corrected)")
    print("=" * 78)
    print(f"  SECURITY F2: Presidio 0.70 -> LLM 0.40 | McNemar p={p_mcnemar} -> "
          f"{'DIRECTIONAL, NOT significant (n=10)' if not sig else 'significant'}")
    print(f"    closed={closed}")
    print(f"    rose(incoherent)={rose}  survived={s['survived']}")
    print(f"    prediction diagnosis_confirmed={s['prediction_check']['diagnosis_confirmed']} (FALSIFIED)")
    print(f"  UTILITY cp: Presidio~0.658 -> LLM 0.755 (no-redaction 0.755); {len(better)} queries better, {len(worse)} worse")
    print(f"    drivers (cp +>0.1): {[r['id'] for r in drivers]}")
    print(f"  redactor: {s['validity']['redactor']['real_calls']} calls, {s['validity']['redactor']['fallbacks']} fallbacks (clean)")
    print("  HEADLINE: utility-win SOLID; security SUGGESTIVE-not-significant; 17.3% Presidio full-stack stays primary")
    print("Files: results/phase3/l2_llm/{L2_LLM.md, l2_llm_tradeoff.png/pdf, l2_llm_results.json}")
    return 0


def _figure(s):
    # focused, FULLY-MEASURED F2-vs-cp trade-off (4 points). NOT an estimated point on the RQ5 Pareto.
    pts = {  # (F2 judged ASR [lower=better], benign cp [higher=better])
        "C00000\n(no redaction)": (0.60, 0.755, "#3498db", "o"),
        "C01000\nPresidio-L2": (0.70, 0.6578, "#e74c3c", "s"),
        "C11111\nPresidio full-stack": (0.60, 0.6578, "#e67e22", "^"),
        "C01000-LLM\n(this experiment)": (0.40, 0.755, "#27ae60", "*"),
    }
    fig, ax = plt.subplots(figsize=(8.6, 6.4))
    for name, (x, y, col, mk) in pts.items():
        ax.scatter([x], [y], s=620 if mk == "*" else 240, marker=mk, color=col,
                   edgecolors="#2c3e50", linewidths=1.6, zorder=5)
        ax.annotate(name, (x, y), textcoords="offset points", xytext=(10, 8), fontsize=9,
                    fontweight="bold" if mk == "*" else "normal")
    ax.annotate("", xy=(0.40, 0.755), xytext=(0.70, 0.6578),
                arrowprops=dict(arrowstyle="->", color="#27ae60", lw=1.8, ls="--"))
    ax.annotate("L2-LLM: lower F2 AND higher cp\nthan Presidio-L2\n(F2 −0.30 directional, McNemar p≈0.45 n.s.;\ncp +0.10 robust, paired n=30)",
                (0.45, 0.70), fontsize=8.2, color="#27ae60",
                bbox=dict(boxstyle="round", fc="#eafaf1", ec="#27ae60", alpha=0.9))
    # x-axis runs 0.78 (left) -> 0.32 (right): higher F2 (less secure) left, lower F2 (more secure) right
    ax.set_xlabel("← less secure      F2 LINKABILITY judged ASR_strict      more secure →", fontsize=10)
    ax.set_ylabel("← worse      benign context-precision (utility)      better →", fontsize=10)
    ax.set_title("L2-LLM redactor vs Presidio-L2 — focused F2-vs-utility trade-off (fully measured)\n"
                 "C01000-LLM = L2-LLM alone; placing it on the full RQ5 Pareto needs a full-family run (future work)",
                 fontsize=10.5, fontweight="bold")
    ax.grid(alpha=0.25)
    ax.set_xlim(0.78, 0.32); ax.set_ylim(0.62, 0.79)   # descending x -> more-secure (low F2) on the right
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "l2_llm_tradeoff.png"), dpi=150)
    fig.savefig(os.path.join(OUT, "l2_llm_tradeoff.pdf"))
    plt.close(fig)


def _md(s, corr, closed, rose, p_mc, drivers, better):
    sc = corr["security_significance"]
    u = corr["utility_finding"]
    lat = s["latency"]
    L = ["# L2-LLM redactor — enhancement experiment (C01000-LLM = L2-LLM alone)\n",
         "**Headline: a generalizable LLM redactor's robust win is UTILITY (it is more *surgical* than Presidio); "
         "its security effect on F2 is directional but NOT statistically significant at n=10. "
         "17.3% (Presidio full stack) stays the primary headline; this is an enhancement experiment on L2 alone.**\n",
         "> Correction: the pre-registered ≤0.52 bar used the **0.08 noise floor, which was derived for the n=52 "
         "OVERALL metric — wrong for a 10-scenario family** (binomial SE ≈0.16). The proper paired test is McNemar.\n",
         "> **Methodological note (general):** the 0.08 noise floor applies to the n=52 *overall* ASR; per-family "
         "deltas (n≈5–13) have a larger floor (binomial SE ≈0.14–0.16) and per-family significance should use the "
         "appropriate binomial/McNemar test at that n. This does not change prior conclusions (which rest on large "
         "F1 drops or genuine nulls), but it is the precise standard.\n",
         "## Security (F2 linkability) — SUGGESTIVE, not significant\n",
         "| Config | F2 judged ASR_strict |", "|---|---|",
         f"| C00000 baseline | {sc['f2_baseline']} |", f"| C01000 Presidio-L2 | {sc['f2_presidio']} |",
         f"| **C01000-LLM** | **{sc['f2_llm']}** |",
         f"\n- **F2 0.70 → 0.40** (−0.30). Paired **McNemar exact p = {p_mc}** on {len(closed)+len(rose)} discordant "
         f"pairs ({len(closed)} closed, {len(rose)} rose) → **directional, NOT significant at n=10.**",
         f"- **Steelman (the real argument it's not nothing):** {sc['steelman']}",
         f"- **The 2 rises are the tell:** {rose} were clean under Presidio and leaked under a strictly-more-redacting "
         f"layer — mechanically incoherent → fresh-vs-reused judge variance (Presidio reused-locked; LLM fresh-judged). "
         f"Responses were not persisted, so noise-vs-redaction can't be separated without re-judging (future work).",
         f"- **Pre-registered prediction FALSIFIED:** recall-miss **P1-LINK-007 survived**, genuine-linkage "
         f"**P2-LINK-002 closed** → the recall-miss/linkage decomposition does NOT predict per-scenario closure "
         f"(`diagnosis_confirmed=False`). The earlier 'can't touch genuine linkage' claim is contradicted by the data.",
         "\n| scenario | bucket | Presidio | LLM |", "|---|---|---|---|"]
    for r in s["per_scenario"]:
        flag = " ←rose" if r["scenario"] in rose else (" ←closed" if r["scenario"] in closed else "")
        L.append(f"| {r['scenario']} | {r['bucket']} | {r['presidio_strict']} | {r['llm_strict']}{flag} |")
    L.append("\n## Utility (benign) — the SOLID finding (n=30, paired, mechanistic)\n")
    L.append(f"- **Mean context-precision 0.658 (Presidio) → {u['mean_cp']['llm']} (LLM)** = no-redaction level "
             f"({u['mean_cp']['no_redaction_C00000']}). **{u['n_queries_cp_better']} queries better, {u['n_worse']} worse.** "
             f"Faithfulness {s['utility_benign']['faithfulness']['C01000_LLM']} (≥ all); 0 over-refusal.")
    L.append(f"- **Mechanism:** {u['mechanism']}")
    if drivers:
        L.append("- **Drivers (cp lift > 0.1):** " + ", ".join(
            f"{r['id']} ({r['cp_presidio_C11111']}→{r['cp_llm']})" for r in drivers))
    L.append(f"\n## Cost & latency\n- redactor ${s['validity']['redactor']['est_usd']} "
             f"({s['validity']['redactor']['real_calls']} calls, {s['validity']['redactor']['cache_hits']} cache hits, "
             f"**{s['validity']['redactor']['fallbacks']} fallbacks → clean, not a hybrid**); util-judge "
             f"${s['cost']['util_judge_usd']}; total ≈ $3 (this task).")
    L.append(f"- **Latency = the headline cost of the approach:** ~{lat['redactor_only_wall_s_mean_5chunks']}s/turn "
             f"(5 redaction calls, cache-warmed here); cold (5 fresh sequential calls) is higher; parallelizable. "
             f"Benign turn mean {lat['benign_turn_ms_mean_incl_redaction']}ms.")
    L.append("\n## Limitations\n- " + "\n- ".join(corr["limitations"]))
    L.append(f"\n## Verdict\n**Utility win: solid and specific** (avoids Presidio's DATE_TIME over-redaction on "
             f"schedule queries). **Security: promising — F2 below the entire Presidio plateau — but not established "
             f"at n=10 (McNemar p≈{p_mc}), and the per-scenario diagnosis was falsified.** Not a clean win, not a null. "
             f"**17.3% Presidio full-stack remains the primary headline.** Future work: C11111-LLM (LLM redactor in the "
             f"full stack), a full-family run to place it on the RQ5 Pareto, cross-vendor re-judging (same-vendor "
             f"coupling), and fresh re-judging of Presidio F2 (fresh-vs-reused confound).")
    open(os.path.join(OUT, "L2_LLM.md"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    sys.exit(main())
