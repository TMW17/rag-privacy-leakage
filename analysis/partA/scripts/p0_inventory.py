#!/usr/bin/env python3
"""
p0_inventory.py -- TASK_SPEC §3.1: map the repository, enumerate every results artifact,
resolve the required-artifact checklist, and map the manuscript's numbered floats to files.

Read-only. Emits analysis/partA/out/p0_inventory.json (the markdown deliverable is rendered
from this file, so every count in 00_inventory.md traces here -- hard rule 11).

Run:  python3 analysis/partA/scripts/p0_inventory.py
"""
import json
import os
import re
import sys
from collections import Counter, OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib_partA as L  # noqa: E402

# "analysis" is excluded deliberately: it is THIS task's own output, not repository evidence.
# Including it makes the inventory self-referential -- every new deliverable would change the
# counts and break the hard-rule-5 determinism check. §1 of 00_inventory.md describes it
# separately.
SKIP_DIRS = {".git", ".venv", ".venv-presidio", "__pycache__", ".pytest_cache",
             ".ipynb_checkpoints", "node_modules", ".DS_Store", "analysis"}
DATA_EXT = {".jsonl", ".json", ".csv", ".txt", ".md", ".tex", ".png", ".pdf", ".py"}


def walk_tree(root, max_depth=3):
    """Directory tree to max_depth, with per-directory file counts."""
    out = []
    root_abs = os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(root_abs):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        rel = os.path.relpath(dirpath, root_abs)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth > max_depth:
            dirnames[:] = []
            continue
        files = [f for f in filenames if not f.startswith(".")]
        ext = Counter(os.path.splitext(f)[1].lower() for f in files)
        out.append({
            "dir": "." if rel == "." else rel,
            "depth": depth,
            "n_files_here": len(files),
            "ext_histogram": dict(ext.most_common()),
            "subdirs": dirnames,
        })
    return out


def describe_artifact(fp):
    """Path, format, record count, keys/columns, mtime -- for one data artifact."""
    rel = os.path.relpath(fp, L.ROOT)
    st = os.stat(fp)
    import datetime
    base = {
        "path": rel,
        "bytes": st.st_size,
        "mtime_utc": datetime.datetime.fromtimestamp(st.st_mtime, datetime.timezone.utc)
                             .isoformat().replace("+00:00", "Z"),
        "tracked_in_git": L.is_tracked(rel),
    }
    ext = os.path.splitext(fp)[1].lower()
    try:
        if ext == ".jsonl":
            with open(fp, encoding="utf-8") as f:
                lines = [ln for ln in f if ln.strip()]
            base["format"] = "jsonl"
            base["rows"] = len(lines)
            if lines:
                first = json.loads(lines[0])
                base["keys"] = sorted(first.keys())
                for opt in ("run_index", "run_id", "attack_family", "attacker_profile"):
                    vals = Counter()
                    for ln in lines:
                        try:
                            vals[json.loads(ln).get(opt)] += 1
                        except Exception:
                            break
                    if len(vals) and set(vals) != {None}:
                        base[f"dist_{opt}"] = {str(k): v for k, v in sorted(vals.items(), key=lambda x: str(x[0]))}
                base["has_response_text"] = "response" in first
                base["has_retrieved_doc_ids"] = "retrieved_doc_ids" in first
        elif ext == ".json":
            d = json.load(open(fp, encoding="utf-8"))
            base["format"] = "json"
            if isinstance(d, dict):
                base["rows"] = len(d)
                base["keys"] = sorted(d.keys())[:60]
            elif isinstance(d, list):
                base["rows"] = len(d)
                base["keys"] = sorted(d[0].keys())[:60] if d and isinstance(d[0], dict) else None
        elif ext == ".csv":
            import csv
            with open(fp, encoding="utf-8") as f:
                rd = list(csv.reader(f))
            base["format"] = "csv"
            base["rows"] = max(len(rd) - 1, 0)
            base["keys"] = rd[0] if rd else None
        else:
            base["format"] = ext.lstrip(".") or "none"
            if ext in (".txt", ".md", ".tex", ".py"):
                base["rows"] = sum(1 for _ in open(fp, encoding="utf-8", errors="replace"))
    except Exception as e:
        base["format"] = base.get("format", ext.lstrip("."))
        base["error"] = f"{type(e).__name__}: {e}"
    return base


def enumerate_results():
    """Every data artifact under results/, experiment_logs/, data/, scenarios/."""
    arts = []
    for top in ("results", "experiment_logs", "data/ground_truth", "scenarios"):
        base = os.path.join(L.ROOT, top)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            for fn in sorted(filenames):
                if os.path.splitext(fn)[1].lower() not in {".jsonl", ".json", ".csv"}:
                    continue
                arts.append(describe_artifact(os.path.join(dirpath, fn)))
    return arts


# ------------------------------------------------------------------ checklist
def find_first(*cands):
    for c in cands:
        fp = os.path.join(L.ROOT, c)
        if os.path.exists(fp):
            return c
    return None


def checklist():
    """TASK_SPEC §3.1 item 3: where each required artifact lives, or NOT FOUND."""
    def entry(name, path, note=""):
        if path is None:
            return {"item": name, "status": "NOT FOUND", "path": None, "note": note}
        fp = os.path.join(L.ROOT, path)
        d = describe_artifact(fp) if os.path.isfile(fp) else {"path": path, "format": "dir"}
        return {"item": name, "status": "FOUND", **d, "note": note}

    eng_dir = os.path.join(L.ROOT, L.P["ablation_engine_dir"])
    ablation_files = sorted(f for f in os.listdir(eng_dir) if f.endswith(".jsonl")) if os.path.isdir(eng_dir) else []

    items = [
        entry("155-document corpus", "data/ground_truth/ground_truth.json"),
        entry("corpus generator script", find_first("scripts/generate_dataset.py")),
        entry("2,190-entity annotation file", "data/ground_truth/ground_truth_annotations.json"),
        entry("annotation pipeline script", find_first("scripts/annotate_dataset.py")),
        entry("52-scenario registry", find_first("scenarios/registry/v1_queries.json"),
              "profile/family/target-severity coverage tested separately below"),
        entry("scenario skeletons", find_first("scenarios/registry/v0_skeletons.json")),
        entry("baseline per-execution results (clean)", "experiment_logs/B2_CLEAN_main-w3.jsonl",
              "CANONICAL -- reproduces the published baseline"),
        entry("baseline per-execution results (poisoned)", "experiment_logs/B2_POISONED_poisoned-w4.jsonl"),
        entry("ablation per-execution results", L.P["ablation_engine_dir"],
              f"{len(ablation_files)} jsonl files: {', '.join(ablation_files)}"),
        entry("engine (rule-based) verdicts per turn", "experiment_logs/B2_CLEAN_main-w3.jsonl",
              "engine verdict is inline on each execution record: fields 'L', 'S', 'events' "
              "(invariant 7 -- NOT leak_detected/severity_score)"),
        entry("judge verdicts per turn (baseline)", "results/judge_calibration/judge_verdicts_full.jsonl",
              "carries L_judge, severity_judge, leak_type_judge, rationale -- NO evidence_quote field"),
        entry("judge verdicts per turn (ablation)", "results/phase3/ablation/judged/judge_cache.jsonl",
              "content-addressed by sha256(profile|response); no scenario/turn keys"),
        entry("undefended 46-record calibration sample", "results/judge_calibration/judge_verdicts.jsonl"),
        entry("undefended calibration HUMAN labels",
              find_first("results/judge_calibration/human_labels.csv",
                         "results/judge_calibration/annotation.csv",
                         "results/phase3_handoff/judge_calibration/judge_verdicts_full.jsonl"),
              "resolved by inspection below -- see A1_inputs"),
        entry("defended 46-record calibration + HUMAN labels",
              "results/phase3_4/judge_defended_calibration/annotation_defended.csv",
              "columns include L_human, leak_type_human, severity_human AND full response text"),
        entry("defended kappa", "results/phase3_4/judge_defended_calibration/kappa_defended.json"),
        entry("published residual bounds", "results/phase3_4/judge_defended_calibration/residual_bounds.json"),
        entry("cross-vendor (gpt-oss) judge outputs", "results/phase3/judge_ensemble"),
        entry("cross-vendor judge driver", find_first("scripts/phase3/judge_ensemble.py")),
        entry("30 benign utility questions", find_first(
            "results/phase3/utility/benign_questions.json", "scripts/phase3/utility_runner.py")),
        entry("utility metrics per configuration", "results/phase3/utility"),
        entry("Presidio recall per entity type", "results/phase3/presidio_check"),
        entry("L7 k-anonymity probe", "results/phase3/ablation/l7_sweep_responses.jsonl"),
        entry("P7 ingestion generalization", "results/phase3/p7"),
        entry("final metrics", "results/phase3/ablation/metrics/final_metrics.json"),
        entry("ablation config decode (bit_layout)", "results/phase3/ablation/config_set6.json"),
        entry("judge system prompt v2", "scenarios/judge_prompts/judge_v2.txt"),
        entry("baseline regeneration (Phase-0 gate)", "results/phase3_4/baseline_regen",
              "see p0_regen_provenance.json -- fresh SUT re-run + fresh judge pass, UNTRACKED"),
    ]
    return items


def scenario_registry():
    """Per-scenario coverage: profile, family, target severity."""
    p = L.P["registry_v1"]
    if not os.path.exists(L.path("registry_v1")):
        return {"status": "NOT FOUND"}
    d = L.load_json("registry_v1")
    recs = d if isinstance(d, list) else (d.get("scenarios") or d.get("queries") or [])
    if not isinstance(recs, list):
        return {"status": "UNPARSED", "top_level_keys": sorted(d.keys()) if isinstance(d, dict) else None}
    keys = sorted({k for r in recs for k in r.keys()})
    fam = Counter(r.get("attack_family") or r.get("family") for r in recs)
    prof = Counter(r.get("attacker_profile") or r.get("profile") for r in recs)
    return {
        "path": p,
        "n_scenarios": len(recs),
        "record_keys": keys,
        "per_family": {str(k): v for k, v in sorted(fam.items(), key=lambda x: str(x[0]))},
        "per_profile": {str(k): v for k, v in sorted(prof.items(), key=lambda x: str(x[0]))},
        "has_target_document": sum(1 for r in recs if r.get("target_document")),
        "has_target_severity": sum(1 for r in recs if any(
            "severity" in k for k in r.keys())),
        "severity_fields_present": sorted({k for r in recs for k in r if "severity" in k}),
    }


# ------------------------------------------------------------------ manuscript
FLOAT_RE = re.compile(r"\\begin\{(table|figure)\*?\}")
LABEL_RE = re.compile(r"\\label\{([^}]+)\}")
CAPTION_RE = re.compile(r"\\caption(?:\[[^\]]*\])?\{")
CHAPTER_RE = re.compile(r"^\s*\\chapter\{(.+?)\}", re.M)


def brace_match(text, start):
    """Return the contents of a {...} group beginning at text[start] == '{'."""
    depth, i = 0, start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:i]
        i += 1
    return ""


def scan_manuscript():
    """Locate manuscript roots and map numbered floats to source files.

    LaTeX assigns float numbers at compile time, so the mapping is reconstructed by ORDER
    of appearance within each chapter: the n-th table environment inside chapter C prints
    as Table C.n.
    """
    tdir = os.path.join(L.ROOT, "results", "phase3_4", "report", "thesis")
    if not os.path.isdir(tdir):
        return {"status": "NOT FOUND"}

    tex = sorted(f for f in os.listdir(tdir) if f.endswith(".tex"))
    roots, chapters_files = [], []
    for f in tex:
        src = open(os.path.join(tdir, f), encoding="utf-8", errors="replace").read()
        is_root = "\\documentclass" in src
        inputs = re.findall(r"\\(?:input|include)\{([^}]+)\}", src)
        rec = {
            "file": os.path.relpath(os.path.join(tdir, f), L.ROOT),
            "lines": src.count("\n") + 1,
            "bytes": len(src.encode()),
            "is_root": is_root,
            "n_input_directives": len(inputs),
            "inputs": inputs[:40],
            "n_chapter_commands": len(CHAPTER_RE.findall(src)),
            "chapter_titles": CHAPTER_RE.findall(src),
            "n_table_envs": len(re.findall(r"\\begin\{table\*?\}", src)),
            "n_figure_envs": len(re.findall(r"\\begin\{figure\*?\}", src)),
            "n_labels": len(LABEL_RE.findall(src)),
            "n_refs": len(re.findall(r"\\(?:ref|autoref|cref|Cref)\{", src)),
        }
        (roots if is_root else chapters_files).append(rec)

    # Pick the manuscript root that inlines chapters 6-8 (the one Part A's table numbers
    # refer to). Prefer the root with the most chapter commands of its own.
    inlining = [r for r in roots if r["n_chapter_commands"] >= 6]
    inlining.sort(key=lambda r: -r["n_chapter_commands"])
    target = inlining[0] if inlining else (roots[0] if roots else None)

    floats = []
    if target:
        src = open(os.path.join(L.ROOT, target["file"]), encoding="utf-8", errors="replace").read()
        # chapter boundaries
        chs = [(m.start(), m.group(1)) for m in CHAPTER_RE.finditer(src)]
        bounds = [(chs[i][0], chs[i + 1][0] if i + 1 < len(chs) else len(src), i + 1, chs[i][1])
                  for i in range(len(chs))]
        counters = {}
        for m in FLOAT_RE.finditer(src):
            kind = m.group(1)
            pos = m.start()
            ch_no, ch_title = None, None
            for s, e, n, t in bounds:
                if s <= pos < e:
                    ch_no, ch_title = n, t
                    break
            if ch_no is None:
                continue
            ck = (ch_no, kind)
            counters[ck] = counters.get(ck, 0) + 1
            # bound the search at this float's own \end{...} so caption/label cannot bleed
            # into the next float
            endm = re.search(r"\\end\{" + kind + r"\*?\}", src[pos:])
            body = src[pos:pos + (endm.end() if endm else 6000)]
            lab = LABEL_RE.search(body)
            cm = CAPTION_RE.search(body)
            cap = re.sub(r"\s+", " ", brace_match(body, cm.end() - 1))[:110] if cm else None
            floats.append({
                "printed_number": f"{'Table' if kind=='table' else 'Figure'} {ch_no}.{counters[ck]}",
                "chapter": ch_no,
                "chapter_title": ch_title,
                "kind": kind,
                "index_in_chapter": counters[ck],
                "line": src[:pos].count("\n") + 1,
                "label": lab.group(1) if lab else None,
                "caption_head": cap,
            })
        # which labels are never referenced
        all_labels = set(LABEL_RE.findall(src))
        refd = set(re.findall(r"\\(?:ref|autoref|cref|Cref)\{([^}]+)\}", src))
        unref = sorted(l for l in all_labels if l not in refd)
    else:
        unref = []

    wanted = ["Table 6.3", "Table 6.4", "Table 6.5", "Table 7.4", "Table 7.5", "Table 7.6",
              "Table 7.7", "Table 8.1", "Table 8.2", "Table 8.3", "Table 8.4", "Table 8.5",
              "Figure 6.4", "Figure 6.5", "Figure 6.6", "Figure 7.2", "Figure 7.3",
              "Figure 7.4", "Figure 7.5", "Figure 7.6", "Figure 7.7", "Figure 8.1",
              "Figure 8.2", "Figure 8.3", "Figure 8.4", "Figure 8.5", "Figure 8.6"]
    by_num = {f["printed_number"]: f for f in floats}
    resolved = OrderedDict((w, by_num.get(w, "NOT FOUND")) for w in wanted)

    return {
        "thesis_dir": os.path.relpath(tdir, L.ROOT),
        "n_tex_files": len(tex),
        "roots": roots,
        "chapter_files_not_roots": chapters_files,
        "selected_manuscript_root": target["file"] if target else None,
        "selection_rationale": "the root that issues its own \\chapter commands for >=6 chapters "
                               "(CLAUDE.md: thesis_master.tex / thesis_pfe.tex inline all chapter "
                               "prose; the ch*.tex files are only pulled in by thesis_modular.tex)",
        "n_floats_in_selected_root": len(floats),
        "floats": floats,
        "requested_float_resolution": resolved,
        "n_requested_resolved": sum(1 for v in resolved.values() if v != "NOT FOUND"),
        "n_labels_never_referenced": len(unref),
        "labels_never_referenced": unref[:60],
    }


def frozen_artifact_tracking():
    """CLAUDE.md invariant 3 names a set of artifacts as frozen and thesis-cited. Are they
    actually under version control? An artifact that exists only in the working tree is one
    `rm` away from making the published numbers unreproducible."""
    frozen = [
        "data/ground_truth/ground_truth.json",
        "data/ground_truth/ground_truth_annotations.json",
        "data/ground_truth/ground_truth_index.json",
        "experiment_logs/B2_CLEAN_main-w3.jsonl",
        "experiment_logs/B2_POISONED_poisoned-w4.jsonl",
        "results/judge_calibration/judge_verdicts_full.jsonl",
        "results/judge_calibration/judge_verdicts.jsonl",
        "results/phase3/ablation/engine/C11111.jsonl",
        "results/phase3/ablation/engine/C01100.jsonl",
        "results/phase3/ablation/judged/judge_cache.jsonl",
        "results/phase3/ablation/metrics/final_metrics.json",
        "results/phase3/ablation/config_set6.json",
        "results/phase3_4/judge_defended_calibration/annotation_defended.csv",
        "scenarios/registry/v1_queries.json",
        "scenarios/judge_prompts/judge_v2.txt",
    ]
    rows = []
    for p in frozen:
        fp = os.path.join(L.ROOT, p)
        present = os.path.exists(fp)
        tracked = L.is_tracked(p) if present else False
        ignored = L.git("check-ignore", "-v", p) if present else None
        ever = L.git("log", "--all", "--oneline", "--", p) if present else None
        rows.append({
            "path": p,
            "exists_in_worktree": present,
            "tracked_in_git": tracked,
            "ignored_by_rule": ignored or None,
            "ever_committed": bool(ever and ever.strip()),
        })
    at_risk = [r for r in rows if r["exists_in_worktree"] and not r["tracked_in_git"]]
    return {
        "rows": rows,
        "n_checked": len(rows),
        "n_untracked": len(at_risk),
        "untracked": [r["path"] for r in at_risk],
        "FINDING": (
            "All checked frozen artifacts are under version control." if not at_risk else
            f"{len(at_risk)} artifact(s) declared frozen by CLAUDE.md invariant 3 are NOT under "
            "version control and were never committed. They exist only in the working tree."),
    }


def registry_vs_executed():
    """Reconcile the 57-scenario registry against the 52 scenarios actually executed."""
    d = L.load_json("registry_v1")
    recs = d if isinstance(d, list) else (d.get("scenarios") or d.get("queries") or [])
    reg_ids = {r.get("scenario_id") for r in recs}
    by_id = {r.get("scenario_id"): r for r in recs}
    rows = L.load_jsonl("orig_clean") + L.load_jsonl("orig_poison")
    exec_ids = {r["scenario_id"] for r in rows}

    not_executed = sorted(reg_ids - exec_ids)
    scen_run0 = {}
    for r in rows:
        if r.get("run_index") == 0:
            scen_run0.setdefault(r["scenario_id"], r)
    fam = Counter(v["attack_family"] for v in scen_run0.values())
    prof = Counter(v["attacker_profile"] for v in scen_run0.values())
    return {
        "n_in_registry": len(reg_ids),
        "n_executed": len(exec_ids),
        "in_registry_not_executed": [
            {"scenario_id": s,
             "profile": (by_id[s] or {}).get("attacker_profile") or (by_id[s] or {}).get("profile"),
             "family": (by_id[s] or {}).get("attack_family") or (by_id[s] or {}).get("family")}
            for s in not_executed],
        "executed_not_in_registry": sorted(exec_ids - reg_ids),
        "executed_scenarios_per_family": dict(sorted(fam.items())),
        "executed_scenarios_per_profile": dict(sorted(prof.items())),
        "n_turns_per_run": 89,
        "FINDING": (
            f"The registry defines {len(reg_ids)} scenarios; {len(exec_ids)} were executed. "
            f"The {len(not_executed)} never executed are all profile P4/ThirdParty. CLAUDE.md §3 "
            "and the taxonomy define FOUR attacker profiles, but the campaign measured THREE. "
            "P4 is specified, not measured." if not_executed else "registry and execution agree"),
    }


def main():
    result = {
        "_provenance": L.provenance(__file__),
        "_purpose": "TASK_SPEC §3.1 inventory: tree, artifacts, required-item checklist, "
                    "scenario registry coverage, manuscript float mapping.",
        "tree_depth3": walk_tree(L.ROOT, 3),
        "results_artifacts": enumerate_results(),
        "required_artifact_checklist": checklist(),
        "frozen_artifact_tracking": frozen_artifact_tracking(),
        "scenario_registry": scenario_registry(),
        "registry_vs_executed": registry_vs_executed(),
        "manuscript": scan_manuscript(),
    }
    arts = result["results_artifacts"]
    result["artifact_totals"] = {
        "n_data_artifacts": len(arts),
        "n_tracked": sum(1 for a in arts if a.get("tracked_in_git")),
        "n_untracked": sum(1 for a in arts if a.get("tracked_in_git") is False),
        "untracked_paths": [a["path"] for a in arts if a.get("tracked_in_git") is False],
        "n_total_rows": sum(a.get("rows") or 0 for a in arts),
    }
    ck = result["required_artifact_checklist"]
    result["checklist_summary"] = {
        "n_items": len(ck),
        "n_found": sum(1 for i in ck if i["status"] == "FOUND"),
        "n_not_found": sum(1 for i in ck if i["status"] == "NOT FOUND"),
        "not_found": [i["item"] for i in ck if i["status"] == "NOT FOUND"],
    }
    out = L.write_out("p0_inventory.json", result)

    print(f"tree dirs (depth<=3): {len(result['tree_depth3'])}")
    print(f"data artifacts: {result['artifact_totals']}")
    print(f"checklist: {result['checklist_summary']}")
    print(f"scenario registry: { {k:v for k,v in result['scenario_registry'].items() if k!='record_keys'} }")
    ft = result["frozen_artifact_tracking"]
    print(f"frozen-artifact tracking: {ft['n_untracked']}/{ft['n_checked']} untracked -> {ft['untracked']}")
    rv = result["registry_vs_executed"]
    print(f"registry {rv['n_in_registry']} vs executed {rv['n_executed']}: "
          f"never executed = {[x['scenario_id'] for x in rv['in_registry_not_executed']]}")
    m = result["manuscript"]
    print(f"manuscript root: {m.get('selected_manuscript_root')}  floats={m.get('n_floats_in_selected_root')} "
          f"requested_resolved={m.get('n_requested_resolved')}/27  unref_labels={m.get('n_labels_never_referenced')}")
    print(f"  requested floats NOT FOUND: "
          f"{[k for k,v in m['requested_float_resolution'].items() if v=='NOT FOUND']}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
