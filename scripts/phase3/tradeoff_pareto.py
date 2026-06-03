"""
tradeoff_pareto.py — Phase-3 RQ5: security–utility Pareto over the 6 ablation cells.

PURE SYNTHESIS — aggregates already-measured metrics (Task 2.4 judged ASR + detection table,
Task 3.1 utility). NO SUT/judge calls, no spend. L6 was never measured -> 6 cells, not 7.

SECURITY axis (x), all components higher=better, JUDGED metric PRIMARY (mandate):
    security = 0.70*(1 - judged_ASR_strict)        # PRIMARY (judge-human kappa=0.827)
             + 0.15*Precision_engine                # detection precision (engine vs annotation)
             + 0.15*prevention_rate                 # = 1 - engine residual-leak rate
  Polarity note: the detection table's "Recall_residual_rate" is INVERTED (higher=worse, it is the
  residual-leak rate). The user's intended security components "Recall (prevention)" and "(1-FNR)"
  COLLAPSE to one number = prevention_rate = FNR_prevention_rate = 1 - residual_leak_rate. Included once.
  prevention_rate is ENGINE-derived (= 1 - engine residual rate) -> NOT independent corroboration of
  judged; kept minor (0.15). Engine ASR itself is shown as a SECONDARY ANNOTATION only (not scored).
  Guardrail: composite ranking must equal the pure (1 - judged_ASR) ranking (asserted below).

UTILITY axis (y), higher=better. Two variants (both reported; CSV carries every raw input):
    U3_spec   = 0.40*faithfulness + 0.40*relevancy + 0.20*query_success      # the SPECIFIED 3 metrics
    U4_incl_cp= 0.30*faithfulness + 0.30*relevancy + 0.15*query_success + 0.25*context_precision
  WHY BOTH: L2 (retrieval redaction) makes the model emit FAITHFUL non-answers ("I'm unable to
  provide specific details about <DATE_TIME>" — BEN-007/009/025 under C11111: faithfulness 1.0,
  refused=false [counts as a query-success WIN], context_precision 0.0). All three spec metrics are
  BLIND to this failure mode; only context_precision catches it. So U3 is ~flat across cells (looks
  "free") while U4 reveals the real ~0.10 context-precision cost concentrated in L2-bearing cells.
  U4 is the HONEST utility axis (primary plot); U3 is reported to honor the spec + show the artifact.

UTILITY for the 4 middle cells is a PROXY (only C00000 & C11111 have measured utility): the bare
  query-success proxy is DEGENERATE (=1.0 for all, by monotonicity — a subset of gates cannot
  over-refuse more than C11111's 0 over-refusals; benign over-refusal was 0 at both extremes) AND was
  never measured on them. So we use a MECHANISTIC proxy: utility cost is driven almost entirely by L2
  (the only content-altering layer), so L2-bearing cells (C01000,C01100) ~ C11111 and non-L2 cells
  (C10000,C00100) ~ C00000. Marked VISIBLY as proxy (hollow markers + band). faithfulness/relevancy/
  context_precision were NOT measured on these 4 cells.

NOISE-AWARE PARETO (mandate: cells within the 0.08 judged-ASR floor must NOT be drawn as cleanly
  separated): cells are grouped into judged-ASR near-tie CLUSTERS; a within-floor security edge does
  NOT create Pareto domination. Result here: security splits into two clusters that align EXACTLY with
  L2 presence — a 'with-L2' secure cluster (C01000/C01100/C11111) and a '~baseline' cluster
  (C00000/C10000/C00100). L2 is the single pivot layer. latency (~1.9x) and context_precision cost
  are concentrated in the L2 cells — annotated, not scored.
"""
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

FINAL = os.path.join(ROOT, "results/phase3/ablation/metrics/final_metrics.json")
UTIL = os.path.join(ROOT, "results/phase3/utility/utility_results.json")
CFG = os.path.join(ROOT, "results/phase3/ablation/config_set6.json")
OUT = os.path.join(ROOT, "results/phase3/tradeoff")

W_SEC = {"judged": 0.70, "precision": 0.15, "prevention": 0.15}
W_U3 = {"faithfulness": 0.40, "relevancy": 0.40, "query_success": 0.20}
W_U4 = {"faithfulness": 0.30, "relevancy": 0.30, "query_success": 0.15, "context_precision": 0.25}
JUDGED_FLOOR = 0.08
ORDER = ["C00000", "C10000", "C01000", "C00100", "C01100", "C11111"]


def load():
    fm = json.load(open(FINAL))
    ut = json.load(open(UTIL))["summary"]
    cfg = {c["id"]: c for c in json.load(open(CFG))["cells"]}
    return fm, ut, cfg


def security_score(cell, fm):
    asr = fm["per_cell"][cell]["judged_strict"]["overall"]
    det = fm["detection_metrics"][cell]
    comp = (W_SEC["judged"] * (1 - asr) + W_SEC["precision"] * det["Precision"]
            + W_SEC["prevention"] * det["FNR_prevention_rate"])
    return {"judged_asr": asr, "engine_asr": fm["per_cell"][cell]["engine_strict"]["overall"],
            "precision": det["Precision"], "residual_leak_rate": det["Recall_residual_rate"],
            "prevention_rate": det["FNR_prevention_rate"], "security_composite": round(comp, 4)}


def utility_measured(cell, ut):
    s = ut[cell]
    u3 = (W_U3["faithfulness"] * s["faithfulness"] + W_U3["relevancy"] * s["response_relevancy"]
          + W_U3["query_success"] * s["query_success_rate"])
    u4 = (W_U4["faithfulness"] * s["faithfulness"] + W_U4["relevancy"] * s["response_relevancy"]
          + W_U4["query_success"] * s["query_success_rate"] + W_U4["context_precision"] * s["context_precision"])
    return {"faithfulness": s["faithfulness"], "relevancy": s["response_relevancy"],
            "query_success": s["query_success_rate"], "context_precision": s["context_precision"],
            "latency_ms_mean": s["latency_ms_mean"], "U3_spec": round(u3, 4),
            "U4_incl_cp": round(u4, 4), "utility_source": "measured"}


def utility_proxy(cell, cfg, measured):
    has_l2 = bool(cfg[cell]["bits"]["L2_retrieval_redaction"])
    anchor = "C11111" if has_l2 else "C00000"
    a = measured[anchor]
    return {"faithfulness": None, "relevancy": None, "query_success": 1.0,
            "context_precision": None, "latency_ms_mean": None,
            "U3_spec": a["U3_spec"], "U4_incl_cp": a["U4_incl_cp"],
            "utility_source": f"proxy(~{anchor}; L2={'yes' if has_l2 else 'no'})"}


def near_tie_clusters(rows):
    """Group cells whose judged ASR is within JUDGED_FLOOR (single-linkage); sorted most-secure first."""
    items = sorted(rows, key=lambda c: rows[c]["judged_asr"])
    clusters, cur = [], [items[0]]
    for c in items[1:]:
        if rows[c]["judged_asr"] - rows[cur[-1]]["judged_asr"] < JUDGED_FLOOR:
            cur.append(c)
        else:
            clusters.append(cur); cur = [c]
    clusters.append(cur)
    return clusters


def main():
    os.makedirs(OUT, exist_ok=True)
    fm, ut, cfg = load()

    rows = {}
    for c in ORDER:
        rows[c] = {"cell": c, "bit_vector": cfg[c]["bit_vector"],
                   "active_layers": "+".join(cfg[c]["active_layers"]) or "none",
                   "n_layers": len(cfg[c]["active_layers"]),
                   "has_L2": bool(cfg[c]["bits"]["L2_retrieval_redaction"]),
                   **security_score(c, fm)}
    measured = {c: utility_measured(c, ut) for c in ("C00000", "C11111")}
    for c in ORDER:
        rows[c].update(measured[c] if c in measured else utility_proxy(c, cfg, measured))

    # ── near-tie clusters on the PRIMARY judged-ASR floor; security TIER (higher = more secure) ──
    clusters = near_tie_clusters(rows)
    n_clu = len(clusters)
    for i, cl in enumerate(clusters):
        for c in cl:
            rows[c]["near_tie_cluster"] = i
            rows[c]["security_tier"] = n_clu - 1 - i

    # ── NOISE-AWARE Pareto over (security_tier, U4 level): within-floor security edges do NOT
    #    dominate. Operating point = (tier, U4). ──
    def op_key(c):
        return (rows[c]["security_tier"], round(rows[c]["U4_incl_cp"], 3))
    op_groups = {}
    for c in ORDER:
        op_groups.setdefault(op_key(c), []).append(c)
    keys = list(op_groups)
    front_ops = [k for k in keys if not any(o != k and o[0] >= k[0] and o[1] >= k[1] for o in keys)]
    parsimony = lambda c: (rows[c]["n_layers"], rows[c]["judged_asr"], -rows[c]["U4_incl_cp"])
    front_reps = {k: min(op_groups[k], key=parsimony) for k in front_ops}
    front_cells = {c for k in front_ops for c in op_groups[k]}
    for c in ORDER:
        rows[c]["on_frontier_U4"] = c in front_cells
        rows[c]["frontier_representative"] = c in front_reps.values()

    # ── KNEE (RQ5): entry into the next-higher-security frontier op-point, taken only when that op's
    #    ASR step from the lower op's representative EXCEEDS the floor (else the gain is within noise). ──
    fops = sorted(front_ops, key=lambda k: k[0])
    knee_minimal, steps = front_reps[fops[0]], []
    for lo, hi in zip(fops, fops[1:]):
        rlo, rhi = front_reps[lo], front_reps[hi]
        d_asr = rows[rlo]["judged_asr"] - rows[rhi]["judged_asr"]
        d_util = rows[rlo]["U4_incl_cp"] - rows[rhi]["U4_incl_cp"]
        real = d_asr > JUDGED_FLOOR
        steps.append({"from": rlo, "to": rhi, "d_judged_asr_drop": round(d_asr, 4),
                      "d_U4_util_cost": round(d_util, 4), "exceeds_floor": real,
                      "sec_per_util": round(d_asr / d_util, 2) if abs(d_util) > 1e-9 else None})
        if real:
            knee_minimal = rhi
    # the recommended config co-located with the knee op-point is the headline knee (defense framing)
    knee_op = (rows[knee_minimal]["security_tier"], round(rows[knee_minimal]["U4_incl_cp"], 3))
    recommended = next((c for c in op_groups[knee_op] if cfg[c].get("recommended")), None)
    knee = recommended or knee_minimal

    # ── roles (clear thesis labels) ──
    sec_tier = rows[knee]["security_tier"]
    for c in ORDER:
        if c == knee:
            role = "knee-recommended (RQ5 optimum)"
        elif c == knee_minimal:
            role = "knee-minimal (co-located, fewer layers)"
        elif rows[c]["security_tier"] == sec_tier:
            role = "defense-in-depth (co-located; within-noise of knee)"
        elif c == "C00000":
            role = "baseline (frontier: max-utility endpoint)"
        else:
            role = "redundant in aggregate (~C00000; no measured aggregate gain on this single-turn-dominated mix)"
        rows[c]["role"] = role
        rows[c]["is_knee_RQ5"] = c == knee
    redundant = [c for c in ORDER if rows[c]["role"].startswith("redundant")]

    # ── GUARDRAIL: composite security ranking == pure (1 - judged_ASR) ranking ──
    rank_comp = sorted(ORDER, key=lambda c: -rows[c]["security_composite"])
    rank_pure = sorted(ORDER, key=lambda c: rows[c]["judged_asr"])
    guard_ok = rank_comp == rank_pure
    assert guard_ok, f"RANKING DRIFT: composite {rank_comp} != pure {rank_pure}"

    # ── CSV (self-contained) ──
    cols = ["cell", "bit_vector", "active_layers", "n_layers", "has_L2",
            "judged_asr", "engine_asr", "precision", "residual_leak_rate", "prevention_rate",
            "security_composite", "faithfulness", "relevancy", "query_success", "context_precision",
            "latency_ms_mean", "U3_spec", "U4_incl_cp", "utility_source", "security_tier",
            "near_tie_cluster", "on_frontier_U4", "frontier_representative", "is_knee_RQ5", "role"]
    with open(os.path.join(OUT, "pareto_data.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for c in ORDER:
            w.writerow({k: rows[c].get(k) for k in cols})

    meta = {
        "purpose": "RQ5 security-utility Pareto, 6 cells (L6 never measured -> not 7). Pure synthesis, $0.",
        "metric_primacy": "JUDGED augmented ASR is PRIMARY (judge-human kappa=0.827); engine ASR is a "
                          "SECONDARY ANNOTATION (not scored).",
        "weights": {"security": W_SEC, "utility_U3_spec": W_U3, "utility_U4_incl_cp": W_U4},
        "polarity_fix": "detection 'Recall_residual_rate' is inverted (=residual leak rate, higher=worse); "
                        "user 'Recall(prevention)' == '(1-FNR)' == prevention_rate (=1-residual), included once; "
                        "prevention_rate is engine-derived (NOT independent of judged), kept minor (0.15).",
        "noise_floor_judged_asr": JUDGED_FLOOR,
        "guardrail_composite_rank_eq_pure_judged_rank": guard_ok,
        "security_ranking": rank_pure,
        "near_tie_clusters_by_judged_asr": [{"cells": cl, "label": (
            "secure (with-L2)" if rows[cl[0]]["has_L2"] else "~baseline (no-L2)"),
            "judged_asr_range": [rows[cl[-1]]["judged_asr"], rows[cl[0]]["judged_asr"]]} for cl in clusters],
        "pivot_finding": "the two security clusters align EXACTLY with L2 presence: adding L2 is the single "
                         "move that crosses from ~baseline to secure; L1/L3 (and L4/L5 in the full stack) move "
                         "neither axis beyond noise.",
        "frontier_operating_points": [{"security_tier": k[0], "U4": k[1], "cells": op_groups[k],
                                       "representative": front_reps[k]} for k in fops],
        "knee_RQ5": {"recommended": knee, "minimal_co_located": knee_minimal,
                     "definition": "entry into the higher-security frontier op-point whose ASR step exceeds the "
                     "0.08 judged floor; the step beyond it (to the full stack) is within noise",
                     "steps": steps},
        "roles": {c: rows[c]["role"] for c in ORDER},
        "redundant_cells": redundant,
        "utility_proxy_note": "middle 4 cells: utility PROXIED (mechanistic: L2-bearing~C11111, non-L2~C00000); "
                              "faithfulness/relevancy/context_precision NOT measured on them; query_success=1.0 "
                              "by monotonicity. Marked hollow on plot.",
        "context_precision_caveat": "U3 (the 3 SPECIFIED metrics) is ~flat (gap %.4f) because all three are blind "
                          "to L2's faithful-non-answer failure mode; context_precision (gap -0.097) is the real "
                          "utility cost. U4 includes it. Do NOT read U3's flatness as 'defenses are free'."
                          % (rows["C00000"]["U3_spec"] - rows["C11111"]["U3_spec"]),
        "latency_caveat": "latency ~1.9x (C00000 %dms -> C11111 %dms), concentrated in L2/full-stack cells; "
                          "annotated not scored; middle cells unmeasured."
                          % (ut["C00000"]["latency_ms_mean"], ut["C11111"]["latency_ms_mean"]),
        "structural_benign_caveat": "utility measured on 30 STRUCTURAL/aggregate low-PII benign queries -> "
                          "'cheap for structural use', NOT 'defenses are free' on PII-adjacent traffic (Task 3.1).",
        "recommendations": {
            "high_risk_orgs": {"config": "C11111 (full stack)", "rationale": "lowest judged ASR (0.173); but the "
                               "+0.019 ASR gain over the knee is WITHIN the 0.08 floor -> a DEFENSE-IN-DEPTH "
                               "argument (L1/L4/L5 cover surfaces not exercised here), NOT a measured ASR win. "
                               "Costs ~0.10 context-precision + ~1.9x latency."},
            "utility_sensitive_orgs": {"config": "%s (L2+L3, the knee) — or %s (L2 alone, minimal)" % (knee, knee_minimal),
                               "rationale": "captures the entire MEASURED security benefit (judged ASR 0.192, "
                               "statistically tied with the full stack) at fewer layers -> lower latency and no "
                               "L1/L4 over-refusal risk on genuine benign traffic. It still pays L2's context-"
                               "precision cost (security here REQUIRES L2). L3 adds no measurable aggregate ASR "
                               "over L2 alone; it is retained for multi-turn conversation-state coverage."},
        },
    }
    json.dump(meta, open(os.path.join(OUT, "tradeoff_meta.json"), "w"), indent=2, ensure_ascii=False)

    _plot(rows, ut, cfg, knee, knee_minimal, clusters, fops, front_reps)
    _readout(rows, ut, knee, knee_minimal, clusters, redundant, meta)
    return 0


def _plot(rows, ut, cfg, knee, knee_minimal, clusters, fops, front_reps):
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(16, 6.6), gridspec_kw={"width_ratios": [1.32, 1]})

    # ===== LEFT: noise-aware Pareto (security_composite vs U4) =====
    for cl in clusters:                                   # near-tie shaded bands (security axis)
        xs = [rows[c]["security_composite"] for c in cl]
        if len(cl) > 1:
            axL.axvspan(min(xs) - 0.005, max(xs) + 0.005, color="#f1c40f", alpha=0.10, zorder=0)
    # frontier path: baseline -> knee (solid, the real trade) -> full stack (dotted, within-noise)
    base = front_reps[fops[0]]
    axL.plot([rows[base]["security_composite"], rows[knee]["security_composite"]],
             [rows[base]["U4_incl_cp"], rows[knee]["U4_incl_cp"]],
             "-", color="#2c3e50", lw=2.0, zorder=2)
    axL.plot([rows[knee]["security_composite"], rows["C11111"]["security_composite"]],
             [rows[knee]["U4_incl_cp"], rows["C11111"]["U4_incl_cp"]],
             ":", color="#7f8c8d", lw=1.8, zorder=2)
    for c in ORDER:                                        # markers + proxy bands
        x, y = rows[c]["security_composite"], rows[c]["U4_incl_cp"]
        meas = rows[c]["utility_source"] == "measured"
        face = "#2c3e50" if (meas and rows[c]["on_frontier_U4"]) else "white"
        axL.scatter([x], [y], s=265 if meas else 215, marker="o" if meas else "s",
                    facecolors=face, edgecolors="#2c3e50" if meas else "#7f8c8d",
                    linewidths=2.4 if meas else 1.6, zorder=5, hatch=None if meas else "////")
        if not meas:                                       # proxy uncertainty band [C11111, C00000]
            axL.plot([x, x], [rows["C11111"]["U4_incl_cp"], rows["C00000"]["U4_incl_cp"]],
                     color="#7f8c8d", lw=1.0, alpha=0.4, zorder=1)
    axL.scatter([rows[knee]["security_composite"]], [rows[knee]["U4_incl_cp"]], s=680, marker="*",
                facecolors="none", edgecolors="#e67e22", linewidths=2.8, zorder=6)

    def lab(text, c, dx, dy, ha, color="#222", fw="normal", fs=8.7):
        axL.annotate(text, (rows[c]["security_composite"], rows[c]["U4_incl_cp"]),
                     textcoords="offset points", xytext=(dx, dy), ha=ha, fontsize=fs, color=color, fontweight=fw)
    lab("C00000  baseline\nASR 0.288", "C00000", 10, 7, "left", "#2c3e50", "bold")
    lab("C10000 · ASR 0.365", "C10000", 0, 14, "center", "#c0392b")
    lab("C00100 · ASR 0.346", "C00100", 0, -26, "center", "#c0392b")
    lab("C11111  full stack\nASR 0.173", "C11111", 11, 9, "left", "#2c3e50", "bold")
    lab("C01000 / C01100  ★ KNEE (RQ5)\nL2(+L3) · ASR 0.192", "C01100", -16, -46, "right", "#e67e22", "bold")
    axL.annotate("C10000, C00100: redundant (≈C00000) — layer adds no measured gain",
                 (0.015, 0.95), xycoords="axes fraction", fontsize=7.8, color="#c0392b", style="italic")
    axL.set_xlim(0.645, 0.915)
    axL.set_ylim(0.818, 0.872)
    axL.set_xlabel("Security score  (0.70·(1−judged ASR) + 0.15·Precision + 0.15·prevention)  →", fontsize=10)
    axL.set_ylabel("Utility  U4 = faith+relevancy+qsucc+context-precision  →", fontsize=10)
    axL.set_title("Security–Utility Pareto (noise-aware; utility incl. context-precision)",
                  fontsize=11, fontweight="bold")
    axL.grid(alpha=0.25)
    axL.legend(handles=[
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#2c3e50", markeredgecolor="#2c3e50",
               markersize=11, label="measured (C00000, C11111)"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor="white", markeredgecolor="#7f8c8d",
               markersize=10, label="proxy (utility ~ L2-anchor)"),
        Line2D([0], [0], marker="*", color="w", markerfacecolor="none", markeredgecolor="#e67e22",
               markersize=16, label="knee (RQ5)"),
        Line2D([0], [0], color="#2c3e50", lw=2, label="real trade-off"),
        Line2D([0], [0], color="#7f8c8d", lw=2, ls=":", label="within-noise (defense-in-depth)"),
        Line2D([0], [0], color="#f1c40f", lw=8, alpha=0.3, label="judged-ASR near-tie (<0.08)"),
    ], fontsize=7.6, loc="lower left")

    # ===== RIGHT: why the 3 spec-metrics understate the cost (C00000 vs C11111) =====
    dims = [("faithfulness", "faithfulness"), ("response_relevancy", "relevancy"),
            ("query_success_rate", "query-\nsuccess"), ("context_precision", "context-\nprecision*")]
    x = np.arange(len(dims))
    b, f = ut["C00000"], ut["C11111"]
    axR.bar(x - 0.2, [b[k] for k, _ in dims], 0.4, label="C00000 (no defense)", color="#3498db")
    axR.bar(x + 0.2, [f[k] for k, _ in dims], 0.4, label="C11111 (full stack)", color="#e74c3c")
    for xi, (k, _) in enumerate(dims):
        d = f[k] - b[k]
        axR.annotate(f"{d:+.3f}", (xi, max(b[k], f[k]) + 0.02), ha="center", fontsize=8.5,
                     color="#c0392b" if d < -0.03 else "#555", fontweight="bold" if d < -0.03 else "normal")
    axR.set_xticks(x); axR.set_xticklabels([n for _, n in dims], fontsize=9)
    axR.set_ylim(0, 1.14); axR.set_ylabel("score", fontsize=10)
    axR.set_title("Why U3 looks 'free': the 3 spec metrics miss L2's cost\n(*only context-precision drops)",
                  fontsize=10.5, fontweight="bold")
    axR.legend(fontsize=8.5); axR.grid(alpha=0.25, axis="y")
    axR.annotate("L2 → faithful but\nempty non-answers\n(faithfulness stays 1.0)", (0, 0.42),
                 fontsize=8, color="#c0392b", ha="center",
                 bbox=dict(boxstyle="round", fc="#fdf2f2", ec="#e74c3c", alpha=0.9))

    fig.suptitle("Phase-3 RQ5 — Defense security vs utility (6 cells; judged-primary; $0 synthesis)",
                 fontsize=12.5, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(os.path.join(OUT, "pareto.png"), dpi=150)
    fig.savefig(os.path.join(OUT, "pareto.pdf"))
    plt.close(fig)


def _readout(rows, ut, knee, knee_minimal, clusters, redundant, meta):
    g_u3 = rows["C00000"]["U3_spec"] - rows["C11111"]["U3_spec"]
    lat = ut["C11111"]["latency_ms_mean"] / ut["C00000"]["latency_ms_mean"]
    secure = [c for c in ORDER if rows[c]["has_L2"]]
    p = (
        f"## RQ5 — Security–utility Pareto (one-paragraph readout)\n\n"
        f"**Lead with the real cost, not the flat axis.** On the three SPECIFIED utility metrics "
        f"(faithfulness, relevancy, query-success) the gap across all 6 cells is essentially zero "
        f"(U3: C00000 {rows['C00000']['U3_spec']:.3f} vs C11111 {rows['C11111']['U3_spec']:.3f}, "
        f"Δ {g_u3:+.3f}) — but that flatness is an **artifact**: all three are blind to L2 retrieval-"
        f"redaction's actual failure mode, where the model returns *faithful but empty* non-answers "
        f"(BEN-007/009/025 under the full stack score faithfulness 1.0 and count as query-success "
        f"'wins', yet context-precision 0.0). The dimension that exposes it, context-precision, drops "
        f"~0.10 (0.755→0.658) and latency rises ~{lat:.1f}× "
        f"({ut['C00000']['latency_ms_mean']:.0f}→{ut['C11111']['latency_ms_mean']:.0f} ms); both costs "
        f"sit in the L2-bearing cells ({', '.join(secure)}). On the honest utility axis U4 (adds "
        f"context-precision) the full stack visibly trades {rows['C00000']['U4_incl_cp']:.3f}→"
        f"{rows['C11111']['U4_incl_cp']:.3f}. **On the security axis (judged-primary) the cells split "
        f"into two near-tie clusters separated by a real >0.08 gap, and the split aligns EXACTLY with "
        f"L2 presence:** a 'with-L2' secure cluster (C01000/C01100/C11111, judged ASR ≈0.17–0.19) and a "
        f"'~baseline' cluster (C00000/C10000/C00100, ≈0.29–0.37). Adding L2 is the *single* move that "
        f"buys security; on this single-turn-dominated scenario mix L1-only (C10000) and L3-only (C00100) "
        f"are **redundant in aggregate** — same utility, security no better than baseline within noise "
        f"({', '.join(redundant)}); this bounds their *aggregate* value, not L3's per-family / multi-turn "
        f"role (which is why L3 is retained in the recommended knee). **The noise-aware "
        f"Pareto frontier runs C00000 → {knee} (knee) → C11111, and the knee / RQ5 optimum is {knee} "
        f"(L2+L3)**: it captures the entire *measured* security benefit (judged ASR 0.192, tied with "
        f"the full stack's 0.173, Δ within the 0.08 floor) at the lowest layer count "
        f"({knee_minimal} = L2 alone is co-located and even more minimal). **Recommendation — (a) "
        f"high-risk orgs: C11111**, on a *defense-in-depth* basis (its ASR edge over the knee is within "
        f"noise, not a measured win; justified by L1/L4/L5 covering attack surfaces this benign set "
        f"doesn't exercise), accepting the ~0.10 context-precision and ~{lat:.1f}× latency cost; **(b) "
        f"utility-sensitive orgs: {knee}** (or {knee_minimal}), the knee — all the measured security at "
        f"fewer layers, lower latency, no L1/L4 over-refusal risk on genuine benign traffic. Caveats: "
        f"utility is measured only on 30 *structural/low-PII* benign queries ('cheap for structural "
        f"use', not 'defenses are free'); the 4 middle cells' utility is a **mechanistic proxy** "
        f"(faithfulness/relevancy/context-precision not measured on them; shown hollow); judged ASR is "
        f"primary (engine ASR is annotation-only — and although the composite includes engine-derived "
        f"Precision + prevention per the spec's component list, the ranking, clusters, frontier and knee "
        f"are all **invariant** to dropping those terms, as judged ASR dominates: see "
        f"`guardrail_composite_rank_eq_pure_judged_rank` in tradeoff_meta.json); L6 was never measured, so "
        f"this is 6 cells, not 7.\n"
    )
    open(os.path.join(OUT, "READOUT.md"), "w").write(p)
    print("=" * 80)
    print("RQ5 PARETO — built (pure synthesis, $0). Files in results/phase3/tradeoff/")
    print("=" * 80)
    print(f"{'cell':8}{'jASR':>7}{'sec':>7}{'U3':>7}{'U4':>7}{'tier':>5}{'front':>6}  role")
    for c in ORDER:
        r = rows[c]
        print(f"{c:8}{r['judged_asr']:>7.3f}{r['security_composite']:>7.3f}{r['U3_spec']:>7.3f}"
              f"{r['U4_incl_cp']:>7.3f}{r['security_tier']:>5}{str(r['on_frontier_U4']):>6}  {r['role']}")
    print("-" * 80)
    print(f"GUARDRAIL composite-rank == pure-judged-rank: {meta['guardrail_composite_rank_eq_pure_judged_rank']}")
    for cl in meta["near_tie_clusters_by_judged_asr"]:
        print(f"  near-tie {cl['label']:18}: {cl['cells']}  ASR{cl['judged_asr_range']}")
    print(f"PIVOT: {meta['pivot_finding']}")
    print(f"knee (RQ5) = {knee}  (minimal co-located = {knee_minimal}) | redundant = {redundant}")
    print(f"U3 spec-utility gap (artifact) = {g_u3:+.4f}; context-precision is the real cost (-0.097)")


if __name__ == "__main__":
    sys.exit(main())
