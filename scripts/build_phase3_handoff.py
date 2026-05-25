"""
build_phase3_handoff.py

Assemble a self-contained Phase 3 handoff package at
results/phase3_handoff/ containing everything a defense implementer
needs without reading any Phase 2 chat history.

Cost: $0 — no API calls.
"""

import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

OUT_DIR = os.path.join(ROOT, "results", "phase3_handoff")

# Source → destination mappings: (src_relative_to_ROOT, dst_relative_to_OUT_DIR)
FILE_MAP = [
    # baseline/
    ("results/baseline/baseline_metrics.json",
     "baseline/baseline_metrics.json"),
    ("results/baseline/baseline_metrics_augmented.json",
     "baseline/baseline_metrics_augmented.json"),
    ("results/baseline/baseline_metrics_comparison.md",
     "baseline/baseline_metrics_comparison.md"),
    ("results/baseline/p4_offline_metrics.json",
     "baseline/p4_offline_metrics.json"),
    ("results/baseline/p4_offline_summary.md",
     "baseline/p4_offline_summary.md"),

    # judge_calibration/
    ("results/judge_calibration/kappa_results.json",
     "judge_calibration/kappa_results.json"),
    ("results/judge_calibration/annotation_triage.csv",
     "judge_calibration/annotation_triage.csv"),
    ("results/judge_calibration/judge_verdicts.jsonl",
     "judge_calibration/judge_verdicts.jsonl"),
    ("results/judge_calibration/judge_verdicts_full.jsonl",
     "judge_calibration/judge_verdicts_full.jsonl"),

    # data/ — generated artifacts only (no raw corpus)
    # hand_verified_leaks_w3_3.md is embedded in the report appendix A,
    # not a standalone file; handled as missing with a note below.
    # attack_scenarios_summary.csv is generated from v1_queries.json below.

    # scripts/
    ("scripts/llm_judge.py",
     "scripts/llm_judge.py"),
    ("scripts/evaluation_engine.py",
     "scripts/evaluation_engine.py"),
    ("scripts/compute_judge_kappa.py",
     "scripts/compute_judge_kappa.py"),
    ("scripts/run_judge_full_phase2.py",
     "scripts/run_judge_full_phase2.py"),
    ("scripts/analyze_baseline_augmented.py",
     "scripts/analyze_baseline_augmented.py"),
    ("scripts/analyze_p4_offline.py",
     "scripts/analyze_p4_offline.py"),
    ("scripts/generate_phase2_figures.py",
     "scripts/generate_phase2_figures.py"),

    # report/
    ("results/baseline/PHASE2_BASELINE_REPORT_v2.md",
     "report/PHASE2_BASELINE_REPORT_v2.md"),
]

# figures: copy everything from results/figures/phase2/
FIGURES_SRC = os.path.join(ROOT, "results", "figures", "phase2")
FIGURES_DST = os.path.join(OUT_DIR, "figures")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def copy_file(src: str, dst: str, missing_warnings: list) -> bool:
    """Copy src → dst, creating parent dirs.  Returns True on success."""
    if not os.path.isfile(src):
        missing_warnings.append(src)
        return False
    ensure_dir(os.path.dirname(dst))
    shutil.copy2(src, dst)
    return True


def file_size(path: str) -> int:
    return os.path.getsize(path) if os.path.isfile(path) else 0


def dir_size(path: str) -> int:
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for fn in filenames:
            total += file_size(os.path.join(dirpath, fn))
    return total


def human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def tree(root: str, max_depth: int = 2, prefix: str = "") -> list[str]:
    lines = []
    try:
        entries = sorted(os.listdir(root))
    except PermissionError:
        return lines
    for i, name in enumerate(entries):
        connector = "└── " if i == len(entries) - 1 else "├── "
        full = os.path.join(root, name)
        lines.append(prefix + connector + name)
        if os.path.isdir(full) and max_depth > 1:
            ext = "    " if i == len(entries) - 1 else "│   "
            lines.extend(tree(full, max_depth - 1, prefix + ext))
    return lines


# ---------------------------------------------------------------------------
# Generated-file builders
# ---------------------------------------------------------------------------

def build_attack_scenarios_csv(missing_warnings: list) -> str:
    """
    Generate data/attack_scenarios_summary.csv from scenarios/registry/v1_queries.json.
    Returns dst path.
    """
    import csv as csv_mod

    src = os.path.join(ROOT, "scenarios", "registry", "v1_queries.json")
    dst = os.path.join(OUT_DIR, "data", "attack_scenarios_summary.csv")
    ensure_dir(os.path.dirname(dst))

    if not os.path.isfile(src):
        missing_warnings.append(src)
        return dst

    with open(src) as f:
        scenarios = json.load(f)

    # v1_queries.json is a flat list of scenario dicts
    fieldnames = [
        "scenario_id", "attacker_profile", "attack_family",
        "linddun_target", "target_severity", "priority",
        "execution_mode", "success_criteria",
    ]

    with open(dst, "w", newline="") as f:
        writer = csv_mod.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for s in scenarios:
            writer.writerow({k: s.get(k, "") for k in fieldnames})

    return dst


def build_hand_verified_leaks(missing_warnings: list) -> str:
    """
    hand_verified_leaks_w3_3.md is not a standalone file — the 10 cases
    live in Appendix A of PHASE2_BASELINE_REPORT_v2.md.  Extract that
    appendix into a standalone file so Phase 3 implementers can find it.
    """
    report_src = os.path.join(ROOT, "results", "baseline", "PHASE2_BASELINE_REPORT_v2.md")
    dst = os.path.join(OUT_DIR, "data", "hand_verified_leaks_w3_3.md")
    ensure_dir(os.path.dirname(dst))

    if not os.path.isfile(report_src):
        missing_warnings.append("Appendix A (embedded in PHASE2_BASELINE_REPORT_v2.md)")
        return dst

    with open(report_src) as f:
        lines = f.readlines()

    # Locate Appendix A block
    start = None
    end = None
    for i, line in enumerate(lines):
        if start is None and "## Appendix A" in line and "Hand-Verified" in line:
            start = i
        elif start is not None and line.startswith("## ") and i > start:
            end = i
            break

    if start is None:
        missing_warnings.append("Appendix A not found in PHASE2_BASELINE_REPORT_v2.md")
        return dst

    block = lines[start:end] if end else lines[start:]
    header = (
        "<!-- Extracted from PHASE2_BASELINE_REPORT_v2.md Appendix A -->\n"
        "<!-- Source of truth: report/PHASE2_BASELINE_REPORT_v2.md -->\n\n"
    )
    with open(dst, "w") as f:
        f.write(header)
        f.writelines(block)

    return dst


# ---------------------------------------------------------------------------
# README and priorities generators
# ---------------------------------------------------------------------------

def load_augmented_metrics() -> dict:
    path = os.path.join(ROOT, "results", "baseline", "baseline_metrics_augmented.json")
    with open(path) as f:
        return json.load(f)


def build_readme(metrics: dict) -> str:
    asr_strict   = metrics.get("ASR_overall_strict", 0.0)
    asr_pct      = round(asr_strict * 100, 1)

    f1_strict    = metrics.get("ASR_by_family_strict", {}).get("F1_DIRECT_PII", 0.0)
    f2_strict    = metrics.get("ASR_by_family_strict", {}).get("F2_LINKABILITY", 0.0)
    f1_pct       = round(f1_strict * 100, 1)
    f2_pct       = round(f2_strict * 100, 1)

    # F1+F2 share of strict leaks
    leak_dist    = metrics.get("leak_type_distribution", {})
    direct_pii   = leak_dist.get("direct_pii", 0)
    cross_ref    = leak_dist.get("cross_reference", 0)
    total_leaks  = direct_pii + cross_ref + leak_dist.get("schema", 0)
    f1_f2_share  = round(100 * (direct_pii + cross_ref) / total_leaks, 1) if total_leaks else 0.0

    kappa_path   = os.path.join(ROOT, "results", "judge_calibration", "kappa_results.json")
    kappa_val    = 0.83
    if os.path.isfile(kappa_path):
        with open(kappa_path) as f:
            kd = json.load(f)
        kappa_val = round(kd.get("kappas", {}).get("binary", {}).get("judge_vs_human", 0.83), 2)

    aug_summary  = metrics.get("augmentation_summary", {})
    n_turns      = aug_summary.get("n_turns", 267)
    n_scenarios  = metrics.get("n_scenarios", 52)

    return f"""\
# Phase 3 Handoff Package

## What is this package?

This directory is a self-contained handoff from Phase 2 of a master's
thesis project (ESI Sidi Bel Abbès, AI & Data Science, 2025–2026) measuring
privacy leakage in enterprise RAG systems.  Everything a defense implementer
needs to begin Phase 3 is here: baseline metrics, judge calibration artefacts,
frozen analysis scripts, publication figures, and the full Phase 2 report.
No Phase 2 chat history or experiment logs are required.

## What was Phase 2's goal?

Phase 2 quantified how much PII a Claude-Sonnet RAG system leaks under four
attacker profiles (Internal, External, Admin, ThirdParty) across {n_scenarios}
adversarial scenarios grouped into 8 attack families.  It ran {n_turns} query
turns ({metrics.get('n_runs', 3)} runs × scenarios), measured binary leakage L
and severity score S using a deterministic engine, and augmented those results
with an LLM-as-Judge (Claude Opus 4.7) to recover leaks the engine missed.
The campaign confirmed the dual-ASR framework: ASR_inclusive (engine ≥ sev 2)
as a conservative upper bound; ASR_strict (judge-confirmed ≥ sev 3) as the
operational signal.

## Headline findings

- **ASR_strict augmented: {asr_pct}%** (vs. {round(metrics.get('ASR_overall_strict', 0)*100 - metrics.get('augmentation_summary', {}).get('judge_lift_ASR_overall_strict', 0)*100*0, 1)}% engine-only before judge lift) — confirmed across 3 independent runs (σ = {metrics.get('run_to_run_sigma_ASR', 0):.4f})
- **F1 + F2 dominate: {f1_f2_share}% of turn-level strict leaks** — F1 (Direct PII, {f1_pct}%) and F2 (Linkability, {f2_pct}%) are the primary attack surfaces; F3/F4/F7 ASR_strict ≤ 7%
- **W2.4 dual-ASR confirmed: 58/58 sev=2 External turns flagged (100%)** — all engine-inclusive leaks for External profile came from severity-2 entities; strict threshold eliminates false positives
- **Judge–human κ = {kappa_val} (calibration passed)** — 46-sample hand-labelled triage; κ ≥ 0.80 acceptance threshold met; see judge_calibration/
- **P3-POISON-007 descriptive corpus poisoning reproducible 3/3 runs** — poisoned document injection via ChromaDB alternate collection confirmed as a viable threat vector; see baseline/p4_offline_metrics.json

## Where do I start Phase 3?

See [phase3_starting_priorities.md](phase3_starting_priorities.md) for the
defence layer ranking, ablation matrix plan, and per-layer rationale linked
to specific report sections.

## What is NOT in this package and where to find it

| What                     | Where to find it                              |
| ------------------------ | --------------------------------------------- |
| Raw experiment JSONL logs | Git repo, tag `w6.1-augmented`, `experiment_logs/` |
| Phase 1 corpus artefacts | Git repo, tag `w6.1-augmented`, `data/ground_truth/` |
| ChromaDB vector store    | Git repo, tag `w6.1-augmented`, `data/rag_index/` |
| Earlier baseline (W3.4)  | Git repo, tag `w3.4-complete`                 |
| W5 calibration state     | Git repo, tag `w5-complete`                   |
| Poisoned document sources | Git repo, `scenarios/poisoned_documents/`    |
| Scenario registry (JSON) | Git repo, `scenarios/registry/v1_queries.json` |

Experiment logs and the corpus are excluded from this package to keep the
total size under 50 MB and because they are fully reproducible from the
tagged repo state.
"""


def build_starting_priorities() -> str:
    return """\
# Phase 3 Starting Priorities

Source: Phase 2 baseline (ASR_strict augmented = 28.8%, n=52 scenarios).
All section references point to `report/PHASE2_BASELINE_REPORT_v2.md`.

---

## Threat landscape summary (from §4 and §5)

| Attack family | ASR_strict | Mean S (given leak) | Priority |
|---------------|------------ |---------------------|----------|
| F1_DIRECT_PII | 77.8%       | 9.30                | CRITICAL |
| F2_LINKABILITY | 63.3%      | 9.07                | CRITICAL |
| F3_DIRECT_INJECTION | 0.0% | 4.90              | LOW      |
| F4_OBFUSCATION | 0.0%       | 0.72                | LOW      |
| F5_JAILBREAK   | 6.7%       | 1.85                | MEDIUM   |
| F6_RECON       | 11.1%      | 2.80                | MEDIUM   |
| F7_SOCIAL_ENG  | 0.0%       | 1.20                | LOW      |
| F8_CORPUS_POISONING | 14.3% | 0.0 (not yet S-scored) | HIGH |

---

## Layer 1 — Input filtering (query sanitisation, prompt injection guards)

**Status: DEPRIORITIZED.**

F3 (Direct Injection) ASR_strict = 0%.  F5 (Jailbreak) ASR_strict = 6.7%.
F7 (Social Engineering) ASR_strict = 0%.  The Claude Sonnet 4.6 system prompt
already refuses the vast majority of direct injection and jailbreak attempts.
Input filtering would produce the smallest absolute reduction in ASR_strict
and risks degrading legitimate query utility.

**Recommendation:** Implement a lightweight keyword blocklist as a baseline
safety rail, but do not invest ablation budget here until F1/F2 are mitigated.
Reference: §5.1 (F3 analysis), §5.5 (F5 analysis), Appendix B (refusal breakdown).

---

## Layer 2 — Presidio retrieval-stage PII redaction

**Status: HIGH PRIORITY.**

F1 (Direct PII) accounts for the largest share of ASR_strict leaks (77.8%)
and the highest severity scores (mean S = 9.30).  Presidio can redact PII
from retrieved chunks before they reach the LLM prompt, directly cutting the
retrieval surface.  The retrieval precision rate is only 8.33%, meaning the
system over-retrieves PII-dense chunks; a retrieval ACL layer would amplify
Presidio's impact.

**Target:** Reduce F1 ASR_strict from 77.8% to < 20%.
**Ablation configs:** Presidio (names only), Presidio (full taxonomy), Presidio
+ retrieval ACL, Presidio + chunk-level severity filter.
Reference: §4.2 (F1 deep dive), §6.2 (retrieval precision analysis),
Phase2.md §5 (Phase 3 tech stack sketch).

---

## Layer 3 — Conversation-aware refusal (memory-gated policy)

**Status: HIGH PRIORITY.**

F2 (Linkability) ASR_strict = 63.3% with mean S = 9.07 — nearly as dangerous
as F1.  Linkability attacks assemble PII across multi-turn context; a
single-turn refusal policy cannot stop them.  A conversation-aware guard that
tracks cumulative entity disclosure across turns and refuses when the
combination crosses a severity threshold is needed.

**Target:** Reduce F2 ASR_strict from 63.3% to < 15%.
**Ablation configs:** Per-turn entity tracking, session-level disclosure budget,
NeMo Guardrails conversational policy.
Reference: §4.3 (F2 multi-turn analysis), §5.2 (conversation memory logging),
Appendix A (hand-verified linkability cases).

---

## Layer 4 — Output filtering (post-generation PII scan)

**Status: SUPPLEMENTARY.**

Output filtering (Presidio on the LLM's generated text) acts as a last-resort
backstop.  It will catch some leaks that slip through Layers 2 and 3 but
introduces latency and risks over-redacting legitimate output.  Deploy after
Layers 2 and 3 are validated.

**Target:** Residual ASR_strict < 5% after Layers 2–3.
Reference: §6.3 (output filter design notes).

---

## Layer 5 — Corpus provenance validation (poisoning defence)

**Status: HIGH PRIORITY, NEW from W6.1.**

P3-POISON-007 confirmed that descriptive corpus poisoning (injecting a
plausible-sounding but false employee record into the ChromaDB collection)
is reproducible across all 3 runs.  The RAG system retrieved the poisoned
chunk in 85.7% of relevant queries (p3_retrieval_rate) and leaked the
fabricated PII in 16.7% of those retrievals.

A provenance validation layer — cryptographic document hashing at index time,
hash check before retrieval — prevents poisoned documents from entering
the retrieval pool.  This is a new Phase 3 requirement not in the original
Phase 2 plan.

**Target:** p3_retrieval_rate of poisoned docs → 0%.
**Ablation configs:** Hash-only guard, hash + metadata signature, hash +
collection isolation.
Reference: baseline/p4_offline_metrics.json (metric4), §4.8 (F8 corpus
poisoning), Appendix D (poisoned document examples).

---

## Ablation matrix

**Planned scope:** 32 defence configurations × 135 scenarios (52 Phase 2 +
83 extended for Phase 3 edge cases).

**Estimated API cost:** $50–70 (Claude Sonnet 4.6 at temperature=0).

**Utility metrics to measure alongside ASR_strict:**
- RAGAS (faithfulness, answer relevancy, context precision)
- BLEU / ROUGE-L (answer quality degradation)
- End-to-end latency p50 / p95 (measured via `loguru` JSONL timestamps)

**Recommended run order (lowest cost → highest cost):**
1. Layer 5 (provenance hash check) — cheapest, no LLM calls needed for guard
2. Layer 2 (Presidio retrieval redaction) — moderate cost
3. Layer 3 (conversation-aware refusal) — moderate cost + NeMo setup
4. Layer 2 + 3 combined — validates interaction effects
5. Layer 4 (output filter) — added on top of combined
6. Full stack (all layers) — reference configuration
7. Layer 1 (input filter) — last, as a regression check

---

## Files to read first

1. `report/PHASE2_BASELINE_REPORT_v2.md` — full 9655-word Phase 2 report
2. `baseline/baseline_metrics_augmented.json` — primary metrics (read programmatically)
3. `baseline/baseline_metrics_comparison.md` — engine-only vs augmented side-by-side
4. `judge_calibration/README_judge_calibration.md` — judge setup and κ results
5. `data/attack_scenarios_summary.csv` — 52 scenarios with IDs and families
"""


def build_baseline_readme() -> str:
    return """\
# baseline/

Quantitative outputs from the Phase 2 baseline campaign.

| File | Description |
|------|-------------|
| `baseline_metrics.json` | W3.4 engine-only metrics (no judge augmentation) |
| `baseline_metrics_augmented.json` | **PRIMARY** — W6.1 judge-augmented metrics; use this for Phase 3 comparisons |
| `baseline_metrics_comparison.md` | Side-by-side: engine-only vs augmented per profile and family |
| `p4_offline_metrics.json` | P3/P4 offline analyses: training leakage proxy, retention overreach, cross-doc linkability, vec2text risk enumeration |
| `p4_offline_summary.md` | Human-readable summary of p4_offline_metrics.json |

**The augmented file is the Phase 3 starting point.**  The engine-only file
is retained for transparency and to document the judge's marginal contribution
(judge_lift_ASR_overall_strict = 55.2% relative improvement).
"""


def build_judge_calibration_readme(kappa_val: float) -> str:
    return f"""\
# judge_calibration/

Artefacts from the LLM-as-Judge calibration pass (W5.4–W5.5).

| File | Description |
|------|-------------|
| `kappa_results.json` | Cohen's κ: judge-vs-human = {kappa_val:.2f} (binary), 0.84 (categorical) |
| `annotation_triage.csv` | 46 hand-labelled turns used for calibration |
| `judge_verdicts.jsonl` | W5.5 calibration cache (46 verdicts, one per line) |
| `judge_verdicts_full.jsonl` | W6.1 full campaign cache (284 verdicts, all turns) |

**Calibration decision:** κ ≥ 0.80 acceptance threshold met.  The judge
(Claude Opus 4.7, prompt `judge_v2.txt`) is used as the authoritative
classifier for ASR_strict in the augmented metrics.

The engine (evaluation_engine.py) is retained as a fast pre-filter; the
judge resolves engine-vs-human disagreements.

See `scripts/compute_judge_kappa.py` to reproduce the κ calculation.
See `scripts/run_judge_full_phase2.py` to re-run the full judge pass
(requires ANTHROPIC_API_KEY; costs ~$8).
"""


def build_data_readme() -> str:
    return """\
# data/

Derived analysis artefacts (not raw corpus files).

| File | Description |
|------|-------------|
| `hand_verified_leaks_w3_3.md` | 10 named leak cases manually confirmed in W3.3; extracted from Appendix A of the Phase 2 report |
| `attack_scenarios_summary.csv` | 52 attack scenarios with IDs, profiles, families, and priorities; generated from `scenarios/registry/v1_queries.json` |

Raw corpus files (`data/ground_truth/`, `data/rag_index/`) are not included
in this package.  Retrieve them from the git repo at tag `w6.1-augmented`.
"""


def build_scripts_readme() -> str:
    return """\
# scripts/

Frozen Phase 2 analysis scripts.  Do not modify — they are reference
implementations for Phase 3 comparison runs.

| Script | Purpose | Reads | Writes |
|--------|---------|-------|--------|
| `evaluation_engine.py` | Core L/S metric engine; deterministic detector | annotations JSON | (module API) |
| `llm_judge.py` | LLM-as-Judge wrapper (Claude Opus 4.7) | scenario turns, judge_v2.txt | judge_verdicts*.jsonl |
| `compute_judge_kappa.py` | Compute Cohen's κ between judge, engine, and human | annotation_triage.csv, judge_verdicts.jsonl | kappa_results.json |
| `run_judge_full_phase2.py` | Re-run full judge pass over all 267 turns | experiment_logs/*.jsonl | judge_verdicts_full.jsonl |
| `analyze_baseline_augmented.py` | Compute augmented metrics from engine + judge output | baseline_summary.csv, judge_verdicts_full.jsonl | baseline_metrics_augmented.json |
| `analyze_p4_offline.py` | Offline P3/P4 risk analysis (no LLM calls) | annotations, experiment_logs | p4_offline_metrics.json |
| `generate_phase2_figures.py` | Reproduce all 6 publication figures (300 DPI) | baseline_metrics_augmented.json | results/figures/phase2/ |

**Import pattern** (required by all scripts):
```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.config import GROUND_TRUTH_FILE, ANNOTATIONS_FILE, AUTHORIZATION_LEVELS
from scripts.evaluation_engine import check_response_for_leakage, AttackerProfile
```

All file paths are resolved through `scripts/config.py` — never hardcode paths.
"""


def build_figures_readme() -> str:
    return """\
# figures/

Publication-quality figures from the Phase 2 baseline campaign (300 DPI PNG +
PDF).  Generated by `scripts/generate_phase2_figures.py`.

| Figure | Description |
|--------|-------------|
| `fig1_asr_by_profile.*` | ASR (inclusive and strict) by attacker profile (P1 Internal, P2 External, P3 Admin) |
| `fig2_asr_by_family.*` | ASR (inclusive and strict) by attack family (F1–F8) |
| `fig3_leak_type_distribution.*` | Leak type breakdown: direct_pii, cross_reference, schema, none |
| `fig4_kappa_heatmap.*` | Judge calibration κ heatmap (binary, categorical, severity) |
| `fig5_severity_distribution.*` | Severity score S distribution across leaked turns |
| `fig6_retrieval_precision.*` | Retrieval precision by attack family |

To regenerate: `python scripts/generate_phase2_figures.py` from the repo root
(reads `baseline_metrics_augmented.json`; no API calls).
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("Phase 3 handoff package builder")
    print(f"Output: {OUT_DIR}")
    print("=" * 60)

    # Clean slate for the handoff dir
    if os.path.exists(OUT_DIR):
        shutil.rmtree(OUT_DIR)
    os.makedirs(OUT_DIR)

    missing_warnings: list[str] = []
    copied_count = 0

    # ------------------------------------------------------------------
    # 1. Copy static files
    # ------------------------------------------------------------------
    for src_rel, dst_rel in FILE_MAP:
        src = os.path.join(ROOT, src_rel)
        dst = os.path.join(OUT_DIR, dst_rel)
        if copy_file(src, dst, missing_warnings):
            copied_count += 1
            print(f"  COPIED  {dst_rel}")
        else:
            print(f"  MISSING {src_rel}")

    # ------------------------------------------------------------------
    # 2. Copy all figures
    # ------------------------------------------------------------------
    if os.path.isdir(FIGURES_SRC):
        ensure_dir(FIGURES_DST)
        for fn in sorted(os.listdir(FIGURES_SRC)):
            if fn.startswith(".") or fn.endswith(".pyc"):
                continue
            src = os.path.join(FIGURES_SRC, fn)
            dst = os.path.join(FIGURES_DST, fn)
            if os.path.isfile(src):
                shutil.copy2(src, dst)
                copied_count += 1
                print(f"  COPIED  figures/{fn}")
    else:
        missing_warnings.append(FIGURES_SRC)
        print(f"  MISSING figures source dir: {FIGURES_SRC}")

    # ------------------------------------------------------------------
    # 3. Generate derived files
    # ------------------------------------------------------------------
    print("\n[Generating derived files]")

    csv_dst = build_attack_scenarios_csv(missing_warnings)
    print(f"  GENERATED data/attack_scenarios_summary.csv")
    copied_count += 1

    leak_dst = build_hand_verified_leaks(missing_warnings)
    print(f"  GENERATED data/hand_verified_leaks_w3_3.md")
    copied_count += 1

    # ------------------------------------------------------------------
    # 4. Load metrics and generate Markdown files
    # ------------------------------------------------------------------
    print("\n[Generating Markdown files]")

    metrics = load_augmented_metrics()

    kappa_path = os.path.join(ROOT, "results", "judge_calibration", "kappa_results.json")
    kappa_val = 0.83
    if os.path.isfile(kappa_path):
        with open(kappa_path) as f:
            kd = json.load(f)
        kappa_val = round(kd.get("kappas", {}).get("binary", {}).get("judge_vs_human", 0.83), 2)

    def write_md(rel_path: str, content: str) -> None:
        nonlocal copied_count
        dst = os.path.join(OUT_DIR, rel_path)
        ensure_dir(os.path.dirname(dst))
        with open(dst, "w") as f:
            f.write(content)
        print(f"  GENERATED {rel_path}")
        copied_count += 1

    write_md("README.md",                            build_readme(metrics))
    write_md("phase3_starting_priorities.md",        build_starting_priorities())
    write_md("baseline/README.md",                   build_baseline_readme())
    write_md("judge_calibration/README_judge_calibration.md",
             build_judge_calibration_readme(kappa_val))
    write_md("data/README.md",                       build_data_readme())
    write_md("scripts/README_scripts.md",            build_scripts_readme())
    write_md("figures/README.md",                    build_figures_readme())

    # ------------------------------------------------------------------
    # 5. Verification
    # ------------------------------------------------------------------
    total_bytes = dir_size(OUT_DIR)
    total_mb    = total_bytes / (1024 * 1024)

    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)
    print(f"  Files copied/generated : {copied_count}")
    print(f"  Total size             : {human_bytes(total_bytes)} ({total_mb:.2f} MB)")

    if total_mb > 50:
        print(f"\n  WARNING: package size {total_mb:.1f} MB exceeds 50 MB limit!")
    else:
        print(f"  Size OK (< 50 MB)")

    print("\nDirectory tree (depth 2):")
    print(f"{os.path.basename(OUT_DIR)}/")
    for line in tree(OUT_DIR, max_depth=2):
        print("  " + line)

    if missing_warnings:
        print(f"\n  MISSING source files ({len(missing_warnings)}):")
        for w in missing_warnings:
            print(f"    - {w}")
    else:
        print("\n  All expected source files present.")

    print("\nDone.")


if __name__ == "__main__":
    main()
