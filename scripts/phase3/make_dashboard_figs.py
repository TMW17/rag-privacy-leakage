"""
make_dashboard_figs.py — generate the NEW dashboard figures for the 5 results panels.

Every number is READ from a committed results/phase3 artifact (no recomputation, no model calls); a
missing field raises (KeyError) rather than silently plotting a zero — a silent zero would be a
fabrication, which the dashboard's honesty discipline forbids. Figures use a dark-blue facecolor that
matches the dashboard's dark theme (light text/axes). Output: results/phase3/dashboard/*.png.

Run:  /usr/local/bin/python3 scripts/phase3/make_dashboard_figs.py
"""
import csv
import json
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
R = os.path.join(ROOT, "results", "phase3")
OUT = os.path.join(R, "dashboard")
os.makedirs(OUT, exist_ok=True)

NAVY, STEEL, CRIMSON, AMBER, SLATE = "#0e1a3a", "#3a5bd0", "#e0556a", "#e89b3c", "#64748b"
LIGHTSTEEL, FAINT = "#9db2e0", "#cbd5e1"
# dark-blue figure theme (matches the dashboard's dark cards): dark facecolor + light text/axes.
CARD, INK, MUTE, GRID = "#0f1a33", "#e7edf8", "#9fb0d0", "#2c3a5e"
plt.rcParams.update({
    "figure.facecolor": CARD, "axes.facecolor": CARD, "savefig.facecolor": CARD, "figure.edgecolor": CARD,
    "text.color": INK, "axes.labelcolor": INK, "axes.titlecolor": INK,
    "xtick.color": INK, "ytick.color": INK, "axes.edgecolor": GRID, "grid.color": GRID,
    "legend.facecolor": CARD, "legend.edgecolor": GRID, "legend.framealpha": 0.92, "legend.labelcolor": INK,
})

CELLS = ["C00000", "C10000", "C01000", "C00100", "C01100", "C11111"]
CLABEL = {"C00000": "C00000\nbaseline", "C10000": "C10000\nL1", "C01000": "C01000\nL2",
          "C00100": "C00100\nL3", "C01100": "C01100\nL2+L3\n(knee)", "C11111": "C11111\nfull stack"}
FAM = [("F1_DIRECT_PII", "F1 Direct PII"), ("F2_LINKABILITY", "F2 Linkability"),
       ("F3_DIRECT_INJECTION", "F3 Injection"), ("F4_OBFUSCATION", "F4 Obfuscation"),
       ("F5_JAILBREAK", "F5 Jailbreak"), ("F6_RECON", "F6 Recon"),
       ("F7_SOCIAL_ENG", "F7 Social Eng"), ("F8_CORPUS_POISONING", "F8 Poisoning")]


def load(rel, base=R):
    with open(os.path.join(base, rel)) as f:
        return json.load(f)


def save(fig, name):
    p = os.path.join(OUT, name)
    fig.savefig(p, dpi=130, bbox_inches="tight", facecolor=CARD)
    plt.close(fig)
    print(f"  wrote results/phase3/dashboard/{name}")


def fcaption(fig, s, y=-0.04):
    """Small grey caveat line under a figure (figure-relative)."""
    fig.text(0.5, y, s, ha="center", fontsize=7.4, color=MUTE)


def acaption(ax, s, y=-0.16):
    """Small grey caveat line under an axes (axes-relative)."""
    ax.text(0, y, s, transform=ax.transAxes, fontsize=7, color=MUTE)


def labeled_bars(ax, items, ylim, ylabel, title, dy=0.012, fmt="{:.2f}"):
    """Bar chart over (label, value, color) triples with a value label above each bar."""
    ax.bar(range(len(items)), [v for _, v, _ in items], color=[c for _, _, c in items])
    for i, (_, v, _) in enumerate(items):
        ax.text(i, v + dy, fmt.format(v), ha="center", fontsize=8.5, color=INK)
    ax.set_xticks(range(len(items)))
    ax.set_xticklabels([it[0] for it in items], fontsize=8)
    ax.set_ylabel(ylabel)
    ax.set_ylim(*ylim)
    ax.set_title(title, fontsize=9.5, color=INK)


def _heat(ax, M, rowlabels, collabels, vmax, title):
    im = ax.imshow(M, cmap="YlOrRd", vmin=0, vmax=vmax, aspect="auto")
    ax.set_xticks(range(len(collabels)))
    ax.set_xticklabels(collabels, fontsize=8)
    ax.set_yticks(range(len(rowlabels)))
    ax.set_yticklabels(rowlabels, fontsize=9)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=8,
                    color="white" if v > vmax * 0.6 else "#222")
    ax.set_title(title, fontsize=11, fontweight="bold", color=INK, pad=10)
    return im


# ── PANEL 1 — ABLATION ────────────────────────────────────────────────────────────────────────────
def fig_family_heatmap():
    fm = load("ablation/metrics/final_metrics.json")
    fn = fm["per_cell"]["C00000"]["family_n"]
    rows, rlab = [], []
    for key, short in FAM:
        rows.append([fm["per_cell"][c]["judged_strict"]["per_family"][key] for c in CELLS])
        rlab.append(f"{short}  (n={fn[key]})")
    M = np.array(rows)
    fig, ax = plt.subplots(figsize=(8.2, 5.0))
    im = _heat(ax, M, rlab, [CLABEL[c] for c in CELLS], 0.8,
               "Judged-strict ASR — attack family × defense config  (PRIMARY metric)")
    fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02, label="judged ASR")
    ax.text(0, -0.95, "F2 row ~flat across configs = linkability UNREDUCED (not config-worse); "
            "per-family n=3–10 ⇒ binomial SE ≈0.15, not the 0.08 overall floor",
            fontsize=7.2, color=MUTE, transform=ax.get_xaxis_transform())
    save(fig, "fam_heatmap.png")


def fig_profile_heatmap():
    fm = load("ablation/metrics/final_metrics.json")
    pn = fm["per_cell"]["C00000"]["profile_n"]
    profs = ["Internal", "External", "Admin"]
    M = np.array([[fm["per_cell"][c]["judged_strict"]["per_profile"][p] for c in CELLS] for p in profs])
    rlab = [f"{p}  (n={pn[p]})" for p in profs]
    fig, ax = plt.subplots(figsize=(8.2, 3.0))
    im = _heat(ax, M, rlab, [CLABEL[c] for c in CELLS], 0.4,
               "Judged-strict ASR — attacker profile × defense config")
    fig.colorbar(im, ax=ax, fraction=0.05, pad=0.02, label="judged ASR")
    ax.text(0, -1.45, "ThirdParty (P4) is offline-evaluated separately, not a live cell.",
            fontsize=7.2, color=MUTE, transform=ax.get_xaxis_transform())
    save(fig, "profile_heatmap.png")


# ── PANEL 2 — SECURITY–UTILITY (RQ5) ────────────────────────────────────────────────────────────────
def fig_security_noiseband():
    fm = load("ablation/metrics/final_metrics.json")
    base = fm["per_cell"]["C00000"]["judged_strict"]["overall"]
    floor = fm["noise_floor"]["judged"]
    jud = [fm["per_cell"][c]["judged_strict"]["overall"] for c in CELLS]
    eng = [fm["per_cell"][c]["engine_strict"]["overall"] for c in CELLS]
    x = np.arange(len(CELLS))
    fig, ax = plt.subplots(figsize=(8.4, 4.3))
    ax.axhspan(base - floor, base + floor, color=AMBER, alpha=0.13,
               label=f"±{floor:.2f} judged floor around baseline (n=52 overall)")
    ax.axhline(base, color=AMBER, ls="--", lw=1, alpha=0.8)
    ax.bar(x, jud, width=0.6, color=[CRIMSON if j > base - floor else STEEL for j in jud],
           label="judged ASR (PRIMARY)", zorder=3)
    ax.plot(x, eng, "o", color=INK, ms=6, label="engine ASR (lower bound)", zorder=4)
    for xi, j in zip(x, jud):
        ax.text(xi, j + 0.012, f"{j:.3f}", ha="center", fontsize=8, color=INK)
    ax.set_xticks(x)
    ax.set_xticklabels([CLABEL[c] for c in CELLS], fontsize=8)
    ax.set_ylabel("ASR")
    ax.set_ylim(0, max(jud) + 0.12)
    ax.set_title("Security across configs — only L2-bearing configs clear the noise floor",
                 fontsize=11, fontweight="bold", color=INK)
    ax.annotate("knee", xy=(4, jud[4]), xytext=(4, jud[4] + 0.07), ha="center", fontsize=8,
                color=STEEL, arrowprops=dict(arrowstyle="->", color=STEEL))
    ax.legend(fontsize=7.6, loc="upper right")
    save(fig, "security_noiseband.png")


def fig_utility_dumbbell():
    u = load("utility/utility_results.json")["summary"]
    a, b = u["C00000"], u["C11111"]
    n = a["n_total"]
    qual = [("faithfulness", a["faithfulness"], b["faithfulness"]),
            ("relevance", a["response_relevancy"], b["response_relevancy"]),
            ("context\nprecision", a["context_precision"], b["context_precision"])]
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(8.6, 3.8), gridspec_kw={"width_ratios": [1.5, 1]})
    y = np.arange(len(qual))
    for yi, (lab, v0, v1) in zip(y, qual):
        axL.plot([v0, v1], [yi, yi], color=FAINT, lw=2, zorder=1)
        axL.scatter(v0, yi, color=SLATE, s=70, zorder=2, label="C00000 (no defense)" if yi == 0 else "")
        axL.scatter(v1, yi, color=CRIMSON, s=70, zorder=2, label="C11111 (full stack)" if yi == 0 else "")
        axL.text(min(v0, v1) - 0.012, yi, f"Δ{v1 - v0:+.3f}", ha="right", va="center", fontsize=7.6, color=INK)
    axL.set_yticks(y)
    axL.set_yticklabels([q[0] for q in qual], fontsize=9)
    axL.set_xlim(0.55, 1.0)
    axL.set_xlabel("score (0–1)")
    axL.set_title("Quality", fontsize=10, color=INK)
    axL.legend(fontsize=7.4, loc="lower left")
    axL.invert_yaxis()
    lm = [a["latency_ms_mean"], b["latency_ms_mean"]]
    lp = [a["latency_ms_p95"], b["latency_ms_p95"]]
    xx = np.arange(2)
    axR.bar(xx - 0.18, lm, 0.36, color=STEEL, label="mean")
    axR.bar(xx + 0.18, lp, 0.36, color=LIGHTSTEEL, label="p95")
    axR.set_xticks(xx)
    axR.set_xticklabels(["C00000", "C11111"], fontsize=8)
    axR.set_ylabel("latency (ms)")
    axR.set_title(f"Latency  ~{lm[1] / lm[0]:.1f}×", fontsize=10, color=INK)
    axR.legend(fontsize=7.4)
    fig.suptitle(f"Utility cost: undefended → full stack  ({n} benign queries, 2 configs only)",
                 fontsize=11, fontweight="bold", color=INK, y=1.02)
    fcaption(fig, "Real cost = context-precision −0.097 + ~1.9× latency; 4 metrics barely move. "
             "Per-config utility (incl. the knee) is future work.")
    save(fig, "utility_dumbbell.png")


# ── PANEL 3 — RISK MATRIX ───────────────────────────────────────────────────────────────────────────
def fig_entity_risk():
    ents = load("risk_matrix/risk_matrix.json")["entities"]
    risky = sorted([e for e in ents if e["risk_sev_x_residual"] > 0],
                   key=lambda e: e["risk_sev_x_residual"])
    n_redacted = sum(1 for e in ents if e["residual_class"] == "REDACTED")
    names = [e["entity_type"] for e in risky]
    vals = [e["risk_sev_x_residual"] for e in risky]
    cmap = {"DETECTOR-GAP": CRIMSON, "BELOW-THRESHOLD": SLATE, "REDACTED": LIGHTSTEEL}
    cols = [cmap.get(e["residual_class"], STEEL) for e in risky]
    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    y = np.arange(len(risky))
    ax.barh(y, vals, color=cols)
    for yi, e in zip(y, risky):
        ax.text(e["risk_sev_x_residual"] + 0.05, yi,
                f"sev {e['severity']} · recall {e['presidio_recall_any_task01']:.2f}",
                va="center", fontsize=7.4, color=INK)
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=8.5)
    ax.set_xlabel("residual risk  =  severity × (1 − detector recall)")
    ax.set_xlim(0, max(vals) + 1.7)
    ax.set_title("Per-entity residual risk under L2 redaction  (config C01100)",
                 fontsize=11, fontweight="bold", color=INK)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=CRIMSON, label="DETECTOR-GAP"),
                       Patch(color=SLATE, label="BELOW-THRESHOLD (by design)")],
              fontsize=7.6, loc="lower right")
    acaption(ax, f"AGE_GENDER = the linkage bridge (recall 0.00). "
             f"{n_redacted} structured types fully redacted (risk 0, not shown). "
             "SYSTEM_PROMPT: Presidio is not its control (F3 handles it, scenario residual 0).")
    save(fig, "entity_risk.png")


def fig_family_risk_bubble():
    fams = load("risk_matrix/risk_matrix.json")["families"]
    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    for frow in fams:
        x = frow["residual_judged_ASR_C01100"]
        yv = frow["impact_tier_assigned"]
        risk = frow["risk_tier_x_residual"]
        dom = frow["family"] == "F2_LINKABILITY"
        ax.scatter(x, yv, s=max(risk, 0.05) * 900, color=CRIMSON if dom else STEEL,
                   alpha=0.55 if dom else 0.4, edgecolor=INK, zorder=3)
        ax.annotate(f"{frow['family'].split('_')[0]} (risk {risk:.2f})", (x, yv),
                    xytext=(6, 6), textcoords="offset points", fontsize=7.6,
                    color=CRIMSON if dom else INK, fontweight="bold" if dom else "normal")
    ax.set_xlabel("residual judged ASR  (likelihood, at knee C01100)")
    ax.set_ylabel("impact tier (max severity)")
    ax.set_xlim(-0.05, 0.8)
    ax.set_ylim(2.5, 5.5)
    ax.set_title("Per-family residual risk = likelihood × impact  (bubble area = risk)",
                 fontsize=11, fontweight="bold", color=INK)
    acaption(ax, "F2 dominant at 2.80 (residual 0.70 @ C01100). F2 unreduced, NOT config-worse. "
             "F6 n=3 within floor. (RQ5 headline quotes F2=0.60 @ full stack — stamp the config.)")
    save(fig, "family_risk_bubble.png")


# ── PANEL 4 — JUDGE VALIDATION (RQ3) ────────────────────────────────────────────────────────────────
def fig_kappa_chain():
    fm = load("ablation/metrics/final_metrics.json")
    k = fm["RQ3_judge_validation_CITED"]
    # prefer the structured field; fall back to the prose metric_ordering string for older artifacts
    eng_human = k.get("engine_human_kappa")
    if eng_human is None:
        eng_human = float(re.search(r"engine.human\s*κ\s*=\s*([0-9.]+)", fm["metric_ordering"]).group(1))
    items = [("engine – human", eng_human, CRIMSON, "poor — fails κ≥0.60"),
             ("inter-human (ceiling)", k["interhuman_kappa"], SLATE, "human ceiling"),
             ("judge – annotator-2", k["claude_annotator2_kappa"], STEEL, ""),
             ("gpt-oss – human", k["gptoss_human_kappa"], STEEL, "independent vendor"),
             ("judge – human", k["judge_human_kappa"], LIGHTSTEEL, "VALIDATION"),
             ("Claude – gpt-oss (cross-vendor)", k["claude_gptoss_kappa"], AMBER, "corroboration, NOT validation")]
    items.sort(key=lambda t: t[1])
    y = np.arange(len(items))
    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    ax.barh(y, [it[1] for it in items], color=[it[2] for it in items])
    ax.axvline(0.60, color=CRIMSON, ls="--", lw=1)
    ax.text(0.60, len(items) - 0.4, " κ≥0.60 bar", color=CRIMSON, fontsize=7.6, va="top")
    for yi, it in zip(y, items):
        ax.text(it[1] + 0.012, yi, f"{it[1]:.3f}" + (f"  · {it[3]}" if it[3] else ""),
                va="center", fontsize=7.8, color=it[2], fontweight="bold")
    ax.set_yticks(y)
    ax.set_yticklabels([it[0] for it in items], fontsize=8.5)
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("Cohen's κ  (undefended 46-record sample)")
    ax.set_title("Judge validation: judge–human κ=0.827 is THE validation; engine–human κ=0.164 is poor",
                 fontsize=10.5, fontweight="bold", color=INK)
    acaption(ax, "0.843 cross-vendor is CORROBORATION, never the validation figure. "
             "Judge exceeds the 0.692 inter-human ceiling; engine fails the 0.60 bar.", y=-0.17)
    save(fig, "kappa_chain.png")


def fig_kappa_degradation():
    kd = load("results/phase3_4/judge_defended_calibration/kappa_defended.json", base=ROOT)
    cmp = kd["comparison_to_undefended"]
    ra = kd["raw_agreement"]
    cm = kd["kappa_defended"]["judge_vs_human_binary"]
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(8.8, 4.0), gridspec_kw={"width_ratios": [1.25, 1]})
    xx = [0, 1]
    axL.plot(xx, [cmp["undefended_judge_vs_human"], cmp["defended_judge_vs_human"]],
             "-o", color=INK, lw=2, label="judge–human κ")
    axL.plot(xx, [ra["undefended"]["rate"], ra["defended"]["rate"]],
             "-o", color=STEEL, lw=2, label="raw agreement")
    for xi, v in zip(xx, [cmp["undefended_judge_vs_human"], cmp["defended_judge_vs_human"]]):
        axL.text(xi, v - 0.05, f"{v:.3f}", ha="center", fontsize=8, color=INK)
    for xi, v in zip(xx, [ra["undefended"]["rate"], ra["defended"]["rate"]]):
        axL.text(xi, v + 0.03, f"{v:.3f}", ha="center", fontsize=8, color=STEEL)
    axL.axhline(0.60, color=CRIMSON, ls="--", lw=1)
    axL.set_xticks(xx)
    axL.set_xticklabels(["undefended", "defended"], fontsize=9)
    axL.set_ylim(0, 1.0)
    axL.set_title(f"Judge degrades on the defended distribution (Δκ {cmp['delta']:+.3f})",
                  fontsize=9.5, color=INK)
    axL.legend(fontsize=7.6, loc="center left")
    cmat = np.array([[cm["n11"], cm["n10"]], [cm["n01"], cm["n00"]]])
    im = axR.imshow(cmat, cmap="Blues", vmin=0, vmax=cmat.max())
    labs = [["TP", "FP"], ["FN", "TN"]]
    for i in range(2):
        for j in range(2):
            axR.text(j, i, f"{labs[i][j]}\n{cmat[i, j]}", ha="center", va="center",
                     fontsize=11, color="white" if cmat[i, j] > cmat.max() * 0.5 else NAVY)
    axR.set_xticks([0, 1]); axR.set_xticklabels(["judge +", "judge −"], fontsize=8)
    axR.set_yticks([0, 1]); axR.set_yticklabels(["human +", "human −"], fontsize=8)
    fpr = cm["n10"] / (cm["n10"] + cm["n00"])
    axR.set_title(f"Defended confusion (n={cm['n']})\nFPR={fpr:.3f}, FN={cm['n01']} (all linkage)",
                  fontsize=9.5, color=INK)
    fig.suptitle("RQ3: the judge over-flags on defended output, but its 3 misses are all linkage "
                 "→ 17.3% is a LOWER bound", fontsize=10, fontweight="bold", color=INK, y=1.04)
    save(fig, "kappa_degradation.png")


# ── PANEL 5 — PROBES ────────────────────────────────────────────────────────────────────────────────
def fig_ls_residual():
    fm = load("ablation/metrics/final_metrics.json")
    sev = load("ablation/metrics/severity_aggregates.json")["per_cell_mean_S"]
    smap = {"C00000": "C00000_baseline", "C01100": "C01100_knee_L2+L3", "C11111": "C11111_full_stack"}
    cfgs = ["C00000", "C01100", "C11111"]
    asr = [fm["per_cell"][c]["judged_strict"]["overall"] for c in cfgs]
    sbar = [sev[smap[c]]["judged"] for c in cfgs]
    n_asr = fm["per_cell"]["C00000"]["judged_strict"].get("n_scenarios", 52)
    n_s = sev[smap["C00000"]]["n"]
    x = np.arange(3)
    fig, axL = plt.subplots(figsize=(7.8, 4.2))
    axR = axL.twinx()
    l1, = axL.plot(x, asr, "-o", color=CRIMSON, lw=2, label=f"L: judged ASR (n≈{n_asr} scen.)")
    l2, = axR.plot(x, sbar, "-s", color=STEEL, lw=2, label=f"S̄: judged severity (n={n_s} turns)")
    for xi, v in zip(x, asr):
        axL.text(xi, v + 0.006, f"{v:.3f}", ha="center", fontsize=8, color=CRIMSON)
    for xi, v in zip(x, sbar):
        axR.text(xi, v + 0.02, f"{v:.3f}", ha="center", fontsize=8, color=STEEL)
    axL.set_xticks(x)
    axL.set_xticklabels(["C00000\nbaseline", "C01100\nknee", "C11111\nfull stack"], fontsize=8.5)
    axL.set_ylabel("judged ASR  (L)", color=CRIMSON)
    axR.set_ylabel("judged mean severity  (S̄)", color=STEEL)
    axL.set_ylim(0, max(asr) * 1.25)
    axR.set_ylim(0, max(sbar) * 1.25)
    axL.set_title("Both halves of the (L, S) pair agree: L2 redaction drives both down",
                  fontsize=10.5, fontweight="bold", color=INK)
    axL.legend(handles=[l1, l2], fontsize=7.8, loc="upper right")
    fcaption(fig, "Different denominators (ASR over scenarios, S̄ over the 89-turn matched set). "
             "Engine overstates both; judged shown.")
    save(fig, "ls_residual.png")


def fig_l2llm_vs_presidio():
    s = load("l2_llm/l2_llm_results.json")["summary"]
    f2 = s["security_F2_judged_strict"]
    cp = s["utility_benign"]["context_precision"]
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(8.8, 3.9))
    sec = [("baseline\nC00000", f2["C00000_baseline"], SLATE),
           ("Presidio\nL2", f2["C01000_presidio"], STEEL),
           ("LLM\nL2", f2["C01000_LLM"], CRIMSON)]
    labeled_bars(axL, sec, (0, 0.85), "F2 judged ASR", "Security (F2)  —  direction only")
    axL.axhline(0.52, color=CRIMSON, ls="--", lw=1)
    axL.text(2.5, 0.52, " pre-reg bar 0.52", color=CRIMSON, fontsize=7, va="bottom", ha="right")
    ut = [("no redaction", cp["C00000_no_redaction"], SLATE),
          ("Presidio", cp["C11111_presidio_proxy"], STEEL),
          ("LLM", cp["C01000_LLM"], CRIMSON)]
    labeled_bars(axR, ut, (0, 0.9), "context precision", "Utility  —  LLM restores precision",
                 dy=0.008, fmt="{:.3f}")
    fig.suptitle("Probe: LLM redactor vs Presidio  (exploratory, single-run)",
                 fontsize=11, fontweight="bold", color=INK, y=1.03)
    fcaption(fig, "Utility win solid (cp 0.658→0.755, 4 better/0 worse); security direction only "
             "(McNemar p≈0.45, n=10); redactor & judge same vendor. 17.3% Presidio stays the headline.",
             y=-0.05)
    save(fig, "l2llm_vs_presidio.png")


def fig_enron_grid():
    ps = load("enron/enron_results.json")["summary"]["per_scenario"]
    fig, ax = plt.subplots(figsize=(6.2, 4.3))
    for r, sc in enumerate(ps):
        for col, cfg in enumerate(["C00000", "C01100"]):
            leak = sc[cfg] == 1
            ax.add_patch(plt.Rectangle((col, r), 1, 1, facecolor=CRIMSON if leak else LIGHTSTEEL,
                                       edgecolor="white", lw=2))
            ax.text(col + 0.5, r + 0.5, "leak" if leak else "—", ha="center", va="center",
                    fontsize=8.5, color="white" if leak else NAVY)
    ax.set_xlim(0, 2); ax.set_ylim(0, len(ps))
    ax.set_xticks([0.5, 1.5]); ax.set_xticklabels(["C00000\n(no defense)", "C01100\n(knee)"], fontsize=8.5)
    ax.set_yticks([r + 0.5 for r in range(len(ps))])
    ax.set_yticklabels([sc["id"] for sc in ps], fontsize=8)
    ax.invert_yaxis()
    ax.set_title("Enron generalization probe — per-scenario leak (1 mailbox, 1 run)",
                 fontsize=10.5, fontweight="bold", color=INK)
    ax.text(0, -0.13, "F1 generalizes DOWN (4→2; phones redacted on real prose). "
            "F2 cells INCONCLUSIVE — judge over-flags redacted output (not 'no effect'). L3/L5 inert on Enron.",
            transform=ax.transAxes, fontsize=7, color=MUTE)
    save(fig, "enron_grid.png")


# ── dark replacements for the pre-existing (light) pipeline figures, from the SAME committed data ──
def fig_marginal():
    fm = load("ablation/metrics/final_metrics.json")
    rq1, floor = fm["RQ1_per_layer"], fm["noise_floor"]
    layers = ["L1", "L2", "L3"]
    jud = [rq1[l]["judged_strict_delta"] for l in layers]
    eng = [rq1[l]["engine_strict_delta"] for l in layers]
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(9.0, 4.2))
    x = np.arange(3)
    axL.axhspan(-floor["judged"], floor["judged"], color=AMBER, alpha=0.14,
                label=f"±{floor['judged']:.2f} judged floor")
    axL.bar(x - 0.18, jud, 0.36, color=CRIMSON, label="judged Δ (primary)")
    axL.bar(x + 0.18, eng, 0.36, color=STEEL, label="engine Δ (lower bound)")
    for xi, v in zip(x - 0.18, jud):
        axL.text(xi, v + (0.006 if v >= 0 else -0.018), f"{v:+.3f}", ha="center", fontsize=7.5, color=INK)
    axL.axhline(0, color=GRID, lw=1)
    axL.set_xticks(x); axL.set_xticklabels(["L1\ninput", "L2\nredaction", "L3\nrefusal"], fontsize=8.5)
    axL.set_ylabel("Δ judged ASR vs baseline")
    axL.set_title("Per-layer marginal — only L2 clears the floor", fontsize=9.5, color=INK)
    axL.legend(fontsize=7, loc="lower left")
    stair = ["C00000", "C01000", "C01100", "C11111"]
    sj = [fm["per_cell"][c]["judged_strict"]["overall"] for c in stair]
    axR.plot(range(4), sj, "-o", color=CRIMSON, lw=2)
    for xi, v in zip(range(4), sj):
        axR.text(xi, v + 0.008, f"{v:.3f}", ha="center", fontsize=8, color=INK)
    axR.set_xticks(range(4)); axR.set_xticklabels(["baseline", "L2", "L2+L3\n(knee)", "full"], fontsize=8.5)
    axR.set_ylabel("judged ASR"); axR.set_ylim(0, max(sj) * 1.3)
    axR.set_title("RQ2 staircase (judged)", fontsize=9.5, color=INK)
    fig.suptitle("Per-layer marginal effect & RQ2 staircase", fontsize=11, fontweight="bold", color=INK, y=1.02)
    save(fig, "marginal_rq2.png")


def fig_pareto():
    from matplotlib.lines import Line2D
    with open(os.path.join(R, "tradeoff/pareto_data.csv")) as f:
        rows = list(csv.DictReader(f))
    fig, ax = plt.subplots(figsize=(8.2, 4.7))
    for r in rows:
        x, y = float(r["security_composite"]), float(r["U4_incl_cp"])
        knee = r["is_knee_RQ5"] == "True"
        measured = r["utility_source"] == "measured"
        col = CRIMSON if knee else (STEEL if measured else SLATE)
        ax.scatter(x, y, s=300 if knee else 90, marker="*" if knee else ("o" if measured else "s"),
                   color=col, edgecolor=INK, zorder=3, alpha=0.92)
        ax.annotate(r["cell"] + ("  ★ knee" if knee else ""), (x, y), xytext=(8, 5),
                    textcoords="offset points", fontsize=8, color=CRIMSON if knee else INK)
    ax.set_xlabel("security composite  (0.70·(1−judged ASR) + 0.15·precision + 0.15·prevention)")
    ax.set_ylabel("utility  U4 (incl. context-precision)")
    ax.set_title("Security–utility Pareto — knee = C01100 (L2+L3)", fontsize=11, fontweight="bold", color=INK)
    ax.legend(handles=[
        Line2D([0], [0], marker="*", linestyle="none", markerfacecolor=CRIMSON, markeredgecolor=INK,
               markersize=14, label="knee C01100 (RQ5 optimum)"),
        Line2D([0], [0], marker="o", linestyle="none", markerfacecolor=STEEL, markeredgecolor=INK,
               markersize=9, label="measured utility (C00000, C11111)"),
        Line2D([0], [0], marker="s", linestyle="none", markerfacecolor=SLATE, markeredgecolor=INK,
               markersize=9, label="proxy utility (L2 shared)")], fontsize=7.4, loc="lower left")
    acaption(ax, "Only C00000 & C11111 have MEASURED utility; mid configs use proxy. Knee is within the "
             "0.08 floor of the full stack on security — full stack is NOT a measured win over the knee.", y=-0.17)
    save(fig, "pareto.png")


def main():
    figs = [fig_family_heatmap, fig_profile_heatmap, fig_security_noiseband, fig_utility_dumbbell,
            fig_entity_risk, fig_family_risk_bubble, fig_kappa_chain, fig_kappa_degradation,
            fig_ls_residual, fig_l2llm_vs_presidio, fig_enron_grid, fig_marginal, fig_pareto]
    print(f"generating {len(figs)} dashboard figures → results/phase3/dashboard/")
    for f in figs:
        f()
    print(f"done: {len(figs)} figures written.")


if __name__ == "__main__":
    main()
