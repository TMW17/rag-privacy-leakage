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
    return {"fam": fam, "fam_err": fam_err, "prof": prof, "prof_err": prof_err,
            "img": img, "img_err": img_err}


def rq5():
    img, img_err = _image("pareto_png")
    pt, pt_err = guard(L.pareto_table)
    return {"img": img, "img_err": img_err, "pt": pt, "pt_err": pt_err}


def risk():
    fam, fam_err = guard(L.risk_families)
    ent, ent_err = guard(L.risk_entities)
    return {"fam": fam, "fam_err": fam_err, "ent": ent, "ent_err": ent_err}


def rq3():
    data, err = guard(L.kappa)
    if err:
        return {"rows": None, "k": None, "err": err}
    rows, k = data
    return {"rows": rows, "k": k, "err": None}


def probes():
    l2, l2_err = guard(L.l2llm)
    en, en_err = guard(L.enron)
    img, img_err = _image("l2llm_png")
    u = (l2 or {}).get("utility_benign", {}).get("context_precision", {})
    f = (en or {}).get("per_family", {})
    return {"l2": l2, "l2_err": l2_err, "u": u,
            "en": en, "en_err": en_err, "f1": f.get("F1", {}), "f2": f.get("F2", {}),
            "img": img, "img_err": img_err}
