"""
views.py — dashboard view-models for the unified app.

This is a THIN presentation adapter over dashboard/loaders.py (imported UNCHANGED). It calls the
loaders, guards missing/malformed artifacts into explicit error strings (never fabricates), and
returns plain context dicts for the Jinja templates.

CHECK #3 contract: this module contains NO metric literals. Every displayed value comes from a
loaders.* call; the only constants here are artifact *names* (e.g. "fig_marginal") passed to the
loaders. The honest-framing prose (with its numbers) lives verbatim in the templates, exactly as it
did in dashboard/app.py's st.info/st.warning blocks.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repo root (parent of webapp/)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dashboard import loaders as L          # noqa: E402  — UNCHANGED data layer


def guard(fn, *args, **kwargs):
    """Run a loader; return (value, None) or (None, error-message). Mirrors dashboard/app.py.guard."""
    try:
        return fn(*args, **kwargs), None
    except L.MissingArtifact as e:
        return None, str(e)
    except Exception as e:                  # malformed artifact, key drift, etc.
        return None, f"{type(e).__name__}: {e}"


def _image(name):
    """Resolve an artifact image to a served URL, or surface an explicit error (no broken <img>)."""
    _, err = guard(L.image_path, name)
    if err:
        return None, err
    return f"/dashboard/img/{name}", None


def overview():
    data, six_err = guard(L.six_cell)
    head, head_err = guard(L.headline)
    ctx = {"head": head, "head_err": head_err, "layer": L.LAYER}
    if six_err:
        ctx.update(rows=None, six_err=six_err, guard=None, floor=None)
    else:
        rows, guard_info, floor = data
        ctx.update(rows=rows, six_err=None, guard=guard_info, floor=floor)
    return ctx


def ablation():
    fam, fam_err = guard(L.per_family)
    prof, prof_err = guard(L.per_profile)
    img, img_err = _image("fig_marginal")
    fam_heat, fam_heat_err = _image("fam_heatmap")
    prof_heat, prof_heat_err = _image("profile_heatmap")
    return {"fam": fam, "fam_err": fam_err, "prof": prof, "prof_err": prof_err,
            "img": img, "img_err": img_err,
            "fam_heat": fam_heat, "fam_heat_err": fam_heat_err,
            "prof_heat": prof_heat, "prof_heat_err": prof_heat_err}


def rq5():
    img, img_err = _image("pareto_png")
    pt, pt_err = guard(L.pareto_table)
    sec, sec_err = _image("security_noiseband")
    util, util_err = _image("utility_dumbbell")
    return {"img": img, "img_err": img_err, "pt": pt, "pt_err": pt_err,
            "sec": sec, "sec_err": sec_err, "util": util, "util_err": util_err}


def risk():
    fam, fam_err = guard(L.risk_families)
    ent, ent_err = guard(L.risk_entities)
    ent_fig, ent_fig_err = _image("entity_risk")
    bubble, bubble_err = _image("family_risk_bubble")
    return {"fam": fam, "fam_err": fam_err, "ent": ent, "ent_err": ent_err,
            "ent_fig": ent_fig, "ent_fig_err": ent_fig_err,
            "bubble": bubble, "bubble_err": bubble_err}


def rq3():
    chain, chain_err = _image("kappa_chain")
    degrade, degrade_err = _image("kappa_degradation")
    data, err = guard(L.kappa)
    ctx = {"rows": None, "k": None, "err": err,
           "chain": chain, "chain_err": chain_err, "degrade": degrade, "degrade_err": degrade_err}
    if not err:
        ctx["rows"], ctx["k"] = data
        ctx["err"] = None
    return ctx


def probes():
    l2, l2_err = guard(L.l2llm)
    en, en_err = guard(L.enron)
    img, img_err = _image("l2llm_png")
    ls, ls_err = _image("ls_residual")
    l2vp, l2vp_err = _image("l2llm_vs_presidio")
    enron_fig, enron_fig_err = _image("enron_grid")
    u = (l2 or {}).get("utility_benign", {}).get("context_precision", {})
    f = (en or {}).get("per_family", {})
    return {"l2": l2, "l2_err": l2_err, "u": u,
            "en": en, "en_err": en_err, "f1": f.get("F1", {}), "f2": f.get("F2", {}),
            "img": img, "img_err": img_err,
            "ls": ls, "ls_err": ls_err, "l2vp": l2vp, "l2vp_err": l2vp_err,
            "enron_fig": enron_fig, "enron_fig_err": enron_fig_err}
