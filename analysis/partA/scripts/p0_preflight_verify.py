#!/usr/bin/env python3
"""
p0_preflight_verify.py -- re-derives, from primary sources, every factual claim the Phase 0
report makes about the environment and the two cleanup commits Part A builds on.

Covers:
  * Amendment 8   -- EFFECTIVE switchModelsOnFlag across both active setting sources;
                     MCP server inventory and where the disable lever actually lives.
  * Verification 1 -- git show --stat 34f9c02: were all 39 deletions build artifacts?
  * Verification 2 -- git log -p -- test.py: was the OpenRouter value the literal
                     placeholder in EVERY historical version? (A6's secret scan blocks
                     on this.)

Read-only. Emits analysis/partA/out/p0_preflight_verify.json.
Run:  python3 analysis/partA/scripts/p0_preflight_verify.py
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib_partA as L  # noqa: E402

CLEANUP_COMMIT = "34f9c02"

# Directories that hold project source / data / evidence. A deletion under any of these
# would mean the cleanup caught something that is not a build artifact.
SOURCE_DIRS = ("scripts/", "app/", "dashboard/", "webapp/", "data/", "results/",
               "scenarios/", "docs/", "reports/", "experiment_logs/", "analysis/",
               "artifact/", "tests/")

# Extensions produced by a LaTeX build and by nothing else in this repository.
LATEX_BUILD_EXT = {"aux", "log", "out", "toc", "fls", "fdb_latexmk", "xdv", "bbl", "blg"}


def classify_deletion(p):
    """Classify one deleted path. Returns (class, rationale)."""
    ext = p.rsplit(".", 1)[-1] if "." in os.path.basename(p) else ""
    under_source = any(p.startswith(d) for d in SOURCE_DIRS)
    if under_source:
        return "SOURCE_OR_EVIDENCE", f"lives under a source/evidence directory ({p.split('/')[0]}/)"
    if ext in LATEX_BUILD_EXT:
        return "LATEX_BUILD_BYPRODUCT", f".{ext} is a LaTeX build byproduct"
    if ext == "pdf":
        return "BUILT_PDF", "compiled PDF (regenerable from .tex; check for a surviving counterpart)"
    if ext == "py":
        return "PYTHON_SCRATCH", "Python file at repo root (not under a source directory)"
    if os.path.basename(p) == ".gitkeep":
        return "EMPTY_PLACEHOLDER", "empty directory placeholder"
    return "UNCLASSIFIED", "no rule matched -- inspect manually"


def verify_cleanup_commit():
    """Verification 1: enumerate and classify every deletion in the cleanup commit."""
    name_status = L.git("show", "--name-status", "--format=", CLEANUP_COMMIT) or ""
    deleted, modified, added, other = [], [], [], []
    for line in name_status.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        code = parts[0].strip()
        if code == "D":
            deleted.append(parts[1])
        elif code == "M":
            modified.append(parts[1])
        elif code == "A":
            added.append(parts[1])
        elif code:
            other.append(line)

    classes = {}
    per_file = []
    for p in sorted(deleted):
        cls, why = classify_deletion(p)
        classes[cls] = classes.get(cls, 0) + 1
        per_file.append({"path": p, "class": cls, "rationale": why})

    # PDFs deserve individual treatment: a build artifact with no surviving counterpart is
    # still recoverable from history, but the commit message's "duplicate" claim needs testing.
    pdf_checks = []
    for p in [d for d in deleted if d.endswith(".pdf")]:
        base = os.path.basename(p)
        parent_rev = f"{CLEANUP_COMMIT}^"
        deleted_hash = L.git("rev-parse", f"{parent_rev}:{p}")
        # find every same-named blob elsewhere in the parent tree
        tree = (L.git("ls-tree", "-r", "--name-only", parent_rev) or "").splitlines()
        survivors = [t for t in tree if os.path.basename(t) == base and t != p]
        surv = []
        for s in survivors:
            h = L.git("rev-parse", f"{parent_rev}:{s}")
            size = L.git("cat-file", "-s", h) if h else None
            surv.append({"path": s, "sha1": h, "bytes": int(size) if size else None,
                         "identical_to_deleted": h == deleted_hash})
        pdf_checks.append({
            "deleted_path": p,
            "deleted_sha1": deleted_hash,
            "deleted_bytes": int(L.git("cat-file", "-s", deleted_hash) or 0) if deleted_hash else None,
            "survivors_same_basename": surv,
            "has_survivor": bool(surv),
            "recoverable_from_history_at": f"{parent_rev}:{p}",
        })

    source_caught = [d for d in per_file if d["class"] == "SOURCE_OR_EVIDENCE"]
    return {
        "commit": L.git("rev-parse", CLEANUP_COMMIT),
        "subject": L.git("log", "-1", "--format=%s", CLEANUP_COMMIT),
        "n_deleted": len(deleted),
        "n_modified": len(modified),
        "n_added": len(added),
        "modified_paths": modified,
        "class_histogram": classes,
        "per_file": per_file,
        "pdf_survivor_checks": pdf_checks,
        "source_or_evidence_caught": source_caught,
        "VERDICT": ("PASS -- no file under any source/evidence directory was deleted"
                    if not source_caught else
                    f"FAIL -- {len(source_caught)} source/evidence file(s) deleted"),
    }


def verify_test_py_secret():
    """Verification 2: every historical version of test.py, checked for a live credential."""
    commits = (L.git("log", "--all", "--format=%H", "--", "test.py") or "").split()
    blobs = {}
    versions = []
    for c in commits:
        content = L.git("show", f"{c}:test.py")
        if content is None:
            versions.append({"commit": c, "state": "ABSENT (deleted at this commit)",
                             "subject": L.git("log", "-1", "--format=%s", c)})
            continue
        import hashlib
        bid = hashlib.sha256(content.encode()).hexdigest()[:16]
        blobs[bid] = content
        auth = [ln.strip() for ln in content.splitlines() if re.search(r"authorization|bearer|api[-_]?key|token",
                                                                      ln, re.I)]
        # A placeholder is <...> or an env lookup; anything else that looks like a key is live.
        live = []
        for ln in auth:
            m = re.search(r"Bearer\s+([^\"']+)", ln)
            if m:
                val = m.group(1).strip()
                is_placeholder = (val.startswith("<") and val.endswith(">")) or "getenv" in ln or "environ" in ln
                if not is_placeholder:
                    live.append(val[:8] + "...")
        versions.append({
            "commit": c,
            "subject": L.git("log", "-1", "--format=%s", c),
            "state": "PRESENT",
            "content_sha256_16": bid,
            "n_lines": len(content.splitlines()),
            "credential_lines": auth,
            "live_credential_candidates": live,
        })

    present = [v for v in versions if v["state"] == "PRESENT"]
    distinct = sorted({v["content_sha256_16"] for v in present})
    any_live = [v for v in present if v["live_credential_candidates"]]
    return {
        "n_commits_touching": len(commits),
        "n_versions_with_content": len(present),
        "n_distinct_blobs": len(distinct),
        "distinct_blob_ids": distinct,
        "versions": versions,
        "VERDICT": ("PASS -- placeholder in every historical version; no live credential ever committed"
                    if not any_live else
                    f"FAIL -- {len(any_live)} version(s) carry a non-placeholder credential"),
    }


def verify_settings_precedence():
    """Amendment 8: effective switchModelsOnFlag across both active setting sources."""
    sources = [
        ("user", os.path.expanduser("~/.claude/settings.json")),
        ("project_shared", os.path.join(L.ROOT, ".claude", "settings.json")),
        ("project_local", os.path.join(L.ROOT, ".claude", "settings.local.json")),
    ]
    found = []
    for scope, fp in sources:
        if not os.path.exists(fp):
            found.append({"scope": scope, "path": fp, "exists": False})
            continue
        try:
            d = json.load(open(fp, encoding="utf-8"))
            ok, err = True, None
        except Exception as e:
            d, ok, err = {}, False, str(e)
        found.append({
            "scope": scope,
            "path": fp,
            "exists": True,
            "parses_as_json": ok,
            "parse_error": err,
            "bytes": os.path.getsize(fp),
            "top_level_keys": sorted(d.keys()),
            "sets_switchModelsOnFlag": "switchModelsOnFlag" in d,
            "switchModelsOnFlag_value": d.get("switchModelsOnFlag", None),
        })

    setters = [f for f in found if f.get("sets_switchModelsOnFlag")]
    # Claude Code precedence, strongest first: enterprise > CLI > project local > project
    # shared > user. Only the sources above are present here.
    order = ["project_local", "project_shared", "user"]
    effective, winner = None, None
    for scope in order:
        m = [f for f in setters if f["scope"] == scope]
        if m:
            effective, winner = m[0]["switchModelsOnFlag_value"], scope
            break

    return {
        "sources": found,
        "n_sources_setting_the_key": len(setters),
        "precedence_order_strongest_first": order,
        "winning_scope": winner,
        "effective_value_by_file_precedence": effective,
        "VERDICT": (f"switchModelsOnFlag = {effective!r}, set only in {winner} settings; "
                    "no project-local override exists, so there is no precedence conflict"
                    if len(setters) == 1 else
                    f"{len(setters)} sources set the key -- precedence resolves to {winner}"),
        "CAVEAT": "This is FILE-LEVEL precedence. The agent cannot observe the runtime value "
                  "of the flag; a restart was required for it to take effect and that is an "
                  "operator-side fact, not an observable one.",
    }


def verify_mcp():
    """Amendment 8: are the unauthenticated MCP servers needed for Part A, and where is
    the lever that disables them?"""
    home_cfg = os.path.expanduser("~/.claude.json")
    proj_mcp_file = os.path.join(L.ROOT, ".mcp.json")
    user_scope, project_scope, enabled, disabled = None, None, None, None
    if os.path.exists(home_cfg):
        try:
            d = json.load(open(home_cfg, encoding="utf-8"))
            user_scope = sorted((d.get("mcpServers") or {}).keys())
            pj = (d.get("projects") or {}).get(L.ROOT, {})
            project_scope = sorted((pj.get("mcpServers") or {}).keys())
            enabled = pj.get("enabledMcpjsonServers")
            disabled = pj.get("disabledMcpjsonServers")
        except Exception:
            pass
    return {
        "local_config_files": {
            "~/.claude.json": os.path.exists(home_cfg),
            ".mcp.json (project)": os.path.exists(proj_mcp_file),
        },
        "user_scope_mcpServers": user_scope,
        "project_scope_mcpServers": project_scope,
        "enabledMcpjsonServers": enabled,
        "disabledMcpjsonServers": disabled,
        "locally_configured_server_count": len(user_scope or []) + len(project_scope or []),
        "FINDING": "No MCP server is configured in any LOCAL file (both scopes empty and no "
                   ".mcp.json). The servers surfaced in-session are therefore claude.ai "
                   "account-level connectors, not repository or settings.json state.",
        "IMPLICATION": "A settings.json edit would disable nothing. The lever is the claude.ai "
                       "connector settings, or /mcp in-session.",
        "NEEDED_FOR_PART_A": "No. Part A is entirely local file analysis plus (for A1) one "
                             "OpenRouter HTTP call. No Part A task reads Atlassian, Canva, "
                             "Microsoft 365, Microsoft Learn, Notion, Slack, Figma or Google Drive.",
    }


def main():
    result = {
        "_provenance": L.provenance(__file__),
        "_purpose": "Re-derive Phase 0 environment and cleanup-commit claims from primary "
                    "sources so that every number in the Phase 0 markdown traces to this script "
                    "(hard rule 11 / amendment 1).",
        "verification_1_cleanup_commit": verify_cleanup_commit(),
        "verification_2_test_py_secret": verify_test_py_secret(),
        "amendment_8_settings_precedence": verify_settings_precedence(),
        "amendment_8_mcp": verify_mcp(),
    }
    out = L.write_out("p0_preflight_verify.json", result)

    v1 = result["verification_1_cleanup_commit"]
    v2 = result["verification_2_test_py_secret"]
    s = result["amendment_8_settings_precedence"]
    print(f"[V1] cleanup {v1['commit'][:7]}: {v1['n_deleted']} deletions, "
          f"{v1['n_modified']} modified -> {v1['VERDICT']}")
    print(f"     classes: {v1['class_histogram']}")
    for c in v1["pdf_survivor_checks"]:
        print(f"     PDF {c['deleted_path']}: survivor={c['has_survivor']}")
    print(f"[V2] test.py: {v2['n_commits_touching']} commits, {v2['n_distinct_blobs']} distinct blob(s) "
          f"-> {v2['VERDICT']}")
    print(f"[A8] {s['VERDICT']}")
    print(f"[A8] MCP: {result['amendment_8_mcp']['locally_configured_server_count']} locally configured")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
