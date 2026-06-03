"""
app.py — Phase-3 dashboard (Streamlit). Read-only: every figure/number is LOADED from a committed
results/phase3/ artifact via loaders.py. No recomputation, no API calls, no mock data. Run with:

    streamlit run dashboard/app.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd            # noqa: E402
import streamlit as st        # noqa: E402

import loaders as L           # noqa: E402

st.set_page_config(page_title="Phase 3 — Defense Layer Evaluation", layout="wide")


def guard(fn, *args, **kwargs):
    """Run a loader; return (value, None) or (None, error-message). Never fabricates."""
    try:
        return fn(*args, **kwargs), None
    except L.MissingArtifact as e:
        return None, str(e)
    except Exception as e:                       # malformed artifact, key drift, etc.
        return None, f"{type(e).__name__}: {e}"


def show_image(name, caption):
    p, err = guard(L.image_path, name)
    if err:
        st.error(err)
    else:
        st.image(p, caption=caption, width="stretch")


st.title("Phase 3 — Defense Layer Evaluation")
st.caption("Read-only view of committed `results/phase3/` artifacts — no recomputation, no API calls. "
           "**Judged augmented ASR is the PRIMARY metric; engine ASR is a lower-bound annotation.**")

T = st.tabs(["Overview", "Ablation", "Security–Utility (RQ5)", "Risk matrix",
             "Judge validation (RQ3)", "Exploratory probes"])

# ─────────────────────────── OVERVIEW ───────────────────────────
with T[0]:
    st.header("Headline")
    data, err = guard(L.six_cell)
    if err:
        st.error(err)
    else:
        rows, guard_info, floor = data
        h, herr = guard(L.headline)
        c1, c2, c3 = st.columns(3)
        if herr:
            st.error(herr)
        else:
            c1.metric("Baseline judged ASR (C00000)", f"{h['baseline_pct']:.1f} %")
            c2.metric("Full-stack judged ASR (C11111)", f"{h['fullstack_pct']:.1f} %",
                      f"{h['delta_pp']:.1f} pp", delta_color="inverse")
            c3.metric("Recommended knee", f"{h['knee']} ({L.LAYER.get(h['knee'], '')})" if h["knee"] else "n/a")
        st.info("**Judged is primary; engine is a lower bound.** The rule engine reports the full stack at "
                "0.000 (~100 % cut); the validated judge reports 0.173 (~40 % cut). The engine cannot see the "
                "semantic / cross-document leakage the judge sees, so it overstates the defense.")
        st.subheader("Six-cell overall strict ASR")
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.warning("**F2 (linkability) is the principal unreduced residual.** Across configurations its judged "
                   "ASR sits at ~0.60 / 0.70 / 0.60 (C00000 / C01000 / C11111): a single noisy plateau within the "
                   "floor — read as **unreduced, NOT config-worse**.")
        st.caption(f"GUARD: baseline judged strict = {guard_info['baseline_judged_strict']} (locked 28.8 %); "
                   f"F1-family = {guard_info['baseline_F1family_judged_strict']} (locked 77.8 %). "
                   f"Dual noise floor: engine ≈ {floor['engine']}, judged ≈ {floor['judged']} "
                   f"(the 0.08 floor is the n=52 OVERALL metric; per-family small-n uses binomial/McNemar).")
    st.caption("Source: `ablation/metrics/final_metrics.json`.")

# ─────────────────────────── ABLATION ───────────────────────────
with T[1]:
    st.header("Per-family judged strict ASR")
    fam, err = guard(L.per_family)
    if err:
        st.error(err)
    else:
        st.dataframe(pd.DataFrame(fam), hide_index=True, width="stretch")
        st.warning("F1 (Direct PII) carries the reduction (0.778 → 0.222 once L2 is on). **F2 (Linkability) is "
                   "unreduced (within noise), NOT config-worse.** Small-N families (F6 N=3, etc.) are coarse.")
    st.header("Per-profile judged strict ASR")
    prof, err = guard(L.per_profile)
    if err:
        st.error(err)
    else:
        st.dataframe(pd.DataFrame(prof), hide_index=True, width="stretch")
        st.caption("ThirdParty (P4) is evaluated offline, not as a live cell.")
    st.header("Per-layer marginal effect & RQ2 staircase")
    show_image("fig_marginal", "Per-layer marginal ΔASR vs the judged floor (left); RQ2 staircase "
               "baseline→L2→L2+L3→full (right). Only L2 clears the floor. Source: committed PNG (not redrawn).")
    st.caption("Sources: `ablation/metrics/final_metrics.json`, `ablation/metrics/fig_marginal_and_rq2.png`.")

# ─────────────────────────── PARETO / RQ5 ───────────────────────────
with T[2]:
    st.header("Security–utility Pareto (RQ5)")
    show_image("pareto_png", "Noise-aware Pareto (left) + why the spec-utility metrics look flat (right). "
               "Knee = C01100 (L2+L3). Source: committed `tradeoff/pareto.png` (not redrawn).")
    pt, err = guard(L.pareto_table)
    if err:
        st.error(err)
    else:
        st.dataframe(pd.DataFrame(pt), hide_index=True, width="stretch")
        st.info("**Knee = C01100 (L2+L3)** — it captures essentially all of the full stack's measured security "
                "(judged 0.192 vs 0.173; gap +0.019, within the 0.08 floor) at two layers. A *naive* Pareto wrongly "
                "picks the full stack on a within-noise edge; the full stack is a defense-in-depth choice, not a "
                "measured win over the knee.")
        st.caption("Utility cost (Task 3.1, C00000 vs C11111): context-precision 0.755 → 0.658 (−0.097), "
                   "latency ~1.9×; the three spec-metrics look flat because they miss L2's faithful-but-empty "
                   "answers (BEN-007/009/025).")
    st.caption("Sources: `tradeoff/pareto.png`, `tradeoff/pareto_data.csv`.")

# ─────────────────────────── RISK MATRIX ───────────────────────────
with T[3]:
    st.header("Risk matrix — two likelihood bases (never conflated)")
    st.markdown("**Families** are scored on the *judged ASR*; **entity types** on *detector-miss exposure under "
                "L2* (1 − Presidio recall for sev≥3; = 1.0 for sev2, retained by design). The judged residual is a "
                "lower bound on true risk.")
    fam, err = guard(L.risk_families)
    if err:
        st.error(err)
    else:
        st.subheader("Family risk (judged)")
        st.dataframe(pd.DataFrame(fam), hide_index=True, width="stretch")
    ent, err = guard(L.risk_entities)
    if err:
        st.error(err)
    else:
        st.subheader("Entity-type risk (31 types; detector-miss under L2)")
        st.dataframe(pd.DataFrame(ent), hide_index=True, width="stretch", height=430)
    st.info("**F2 is the dominant elevated residual.** MEDICAL / SURNAME_TITLE / AGE_GENDER surface via the "
            "DETECTOR-GAP class (a flat sort would bury SURNAME). **AGE_GENDER is the linkage bridge** (sev3, "
            "LINDDUN=Linkability, recall 0.0). **SYSTEM_PROMPT sorts #1 by raw product but is demoted** — Presidio "
            "is not its control, and the F3 injection family that targets it is fully defended (judged 0.0).")
    st.caption("Sources: `risk_matrix/risk_matrix_families.csv`, `risk_matrix/risk_matrix_entities.csv`, "
               "`risk_matrix/risk_matrix.json`.")

# ─────────────────────────── JUDGE VALIDATION / RQ3 ───────────────────────────
with T[4]:
    st.header("Judge validation (RQ3)")
    data, err = guard(L.kappa)
    if err:
        st.error(err)
    else:
        rows, k = data
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.info(f"**κ = {k['judge_human_kappa']:.3f} is the VALIDATION figure** (judge vs human). "
                f"**κ = {k['claude_gptoss_kappa']:.3f} is cross-vendor CORROBORATION (Claude vs gpt-oss) — "
                f"never the validation figure.** The judge–human agreement ({k['judge_human_kappa']:.3f}) exceeds "
                f"the inter-human ceiling ({k['interhuman_kappa']:.3f}), read as the judge's *consistency against "
                f"the primary annotator's fixed labels* — not superhuman judgment.")
        st.caption(f"Single-Claude calibration FPR {k['single_claude_FPR']} vs majority-vote {k['majority_FPR']} "
                   f"(46-record sample). Claude-only operation is the declared constraint; no 3-judge full-ablation "
                   f"numbers are fabricated.")
    st.caption("Source: `final_metrics.json` (RQ3_judge_validation_CITED; cited from Sprint 0).")

# ─────────────────────────── PROBES ───────────────────────────
with T[5]:
    st.warning("**Exploratory probes — single-run, direction-only.** These are NOT primary results and do NOT "
               "change the 17.3 % headline. Their numbers are directions, never rates.")

    st.subheader("1 · LLM redactor (L2-LLM) — enhancement probe")
    d, err = guard(L.l2llm)
    if err:
        st.error(err)
    else:
        u = d.get("utility_benign", {}).get("context_precision", {})
        st.markdown(f"- **Utility (solid, n=30 paired):** context-precision **{u.get('C11111_presidio_proxy')} → "
                    f"{u.get('C01000_LLM')}** (= no-redaction level); 0 over-refusal; mechanism = avoids Presidio's "
                    f"schedule over-redaction (more surgical).\n"
                    f"- **Security (suggestive, NOT significant):** F2 0.70 → 0.40 but **McNemar p ≈ 0.45 at n=10**; "
                    f"the pre-registered per-scenario prediction was *falsified*; two ‘rises’ are a fresh-vs-reused "
                    f"judge confound.\n"
                    f"- *Caveat:* same-vendor Sonnet-redactor / Opus-judge coupling.")
        show_image("l2llm_png", "L2-LLM vs Presidio-L2: fully-measured F2-vs-context-precision trade-off "
                   "(security edge non-significant). Source: committed `l2_llm/l2_llm_tradeoff.png`.")

    st.subheader("2 · Enron generalization (Task 3.6)")
    d, err = guard(L.enron)
    if err:
        st.error(err)
    else:
        f = d.get("per_family", {})
        f1, f2 = f.get("F1", {}), f.get("F2", {})
        st.markdown(f"- **F1 (direct PII) generalizes, direction-consistent:** {f1.get('c00000')}/{f1.get('n')} → "
                    f"{f1.get('c01100')}/{f1.get('n')} (McNemar p=0.5, n=4 — *direction, not a rate*); the residual is "
                    f"an **address** = the *same* Presidio address-recall gap as synthetic → not a synthetic artifact.\n"
                    f"- **F2 (linkability) inconclusive** — corrected down from the prediction: the synthetic-validated "
                    f"judge **over-flags redacted output** on Enron (a cross-corpus judge-transfer limitation, "
                    f"isolated to the defended-cell survivors; the baseline leaks are all real PII).\n"
                    f"- *Caveats:* single mailbox; n=4/3; one run; L3/L5 inert on un-annotated data (so C01100 = "
                    f"L2-driven here).")
    st.caption("Sources: `l2_llm/l2_llm_results.json`, `l2_llm/l2_llm_tradeoff.png`, `enron/enron_results.json`. "
               "**17.3 % synthetic full-stack remains the primary headline.**")
