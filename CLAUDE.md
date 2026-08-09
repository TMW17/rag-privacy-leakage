# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Operational Guide for AI Coding Agents

> **What this file is.** Contracts, invariants, and conventions for any AI coding agent working on this codebase. For the scientific background and motivation, read `PROJECT.md`. For what the experiments actually found, read `results/phase3/FINDINGS.md`.
>
> **Stale-doc warning.** Everything under `docs/plans/` (`Phase1.md`, `Phase2.md`, `Phase5.md`, `PHASE5_PLAN.md`, `PHASE1_INTERFACE.md`) and the module docstrings in `scripts/config.py` were written mid-project and describe a state that no longer holds. Where they disagree with this file or with what is on disk, they are wrong. §12 lists what is currently authoritative.

---

## 1. Project in one paragraph

Master's thesis at ESI Sidi Bel Abbès (AI & Data Science, 2025–2026). Author: TADJ Mohamed Walid.
Goal: measure and mitigate privacy leakage in enterprise RAG systems using two formal metrics — binary leakage function **L** (did any unauthorized entity leak?) and severity score **S** (how bad?) — applied across four attacker profiles against a 155-document synthetic PII corpus, then quantify how much a layered defense stack removes.

**Current state: all experiments are complete and committed.** The measurement work is finished; remaining work is writing, presentation, and demonstration. The two shipped deliverables are `Master_Report.pdf` (65 pp) and `PFE_Report.pdf` (160 pp) at the repo root. **Default assumption for any new task: you are editing prose, figures, or demo apps — not producing new numbers.** Generating a new number means paid API calls and breaks the "every number traces to a committed artifact" discipline (§11).

---

## 2. Non-obvious layout

```
Code/
├── CLAUDE.md  PROJECT.md  Makefile  requirements.txt
├── Master_Report.pdf   PFE_Report.pdf        ← the two shipped deliverables
├── SUPERVISOR_DEMO.md  Speaker_Notes.md  DASHBOARD_APP_REPORT.md
├── docs/        plans/ (mid-project roadmaps, stale) · notes/ (reasoning spines)
├── reports/     phase1/ · phase2/ · sprints/  (superseded report sets, kept for provenance)
├── scripts/     Phase-1 pipeline + Phase-2 RAG + phase3/ defenses
├── app/  dashboard/  webapp/                 ← the three demos (§8)
└── data/  results/  scenarios/  experiment_logs/
```

The final thesis sources live in `results/phase3_4/report/thesis/`, **not** in `reports/` — that directory holds the older phase and sprint reports.

Beyond that, these are the parts that are not self-describing.

| Path | What it actually is |
| ---- | ------------------- |
| `scripts/` | Phase 1 pipeline **and** the Phase 2 RAG system (`rag_system.py`, `campaign_runner.py`, `llm_judge.py`). Not just Phase 1. |
| `scripts/phase3/` | ~40 files: defense layers, ablation, probes. See naming convention below. |
| `experiments/` | **Empty.** Historical placeholder — nothing lives here. Do not put new code in it. |
| `scenarios/registry/` | `v0_skeletons.json`, `v1_queries.json` — the attack scenario definitions. |
| `scenarios/judge_prompts/` | `judge_v1.txt`, `judge_v2.txt`. There is no `judge_v3.txt`. |
| `data/rag_index/` | `chromadb/` holds **three** collections — `phase2_baseline_seed42`, `phase2_poisoned_p3`, `enron_slice` (the poisoned index builder writes *here*, despite the name). `sanitized_chromadb/` holds `phase3_sanitized_seed42`. `poisoned_chromadb/` is written by nothing in `scripts/` — treat as stale. |
| `results/phase3_4/report/thesis/` | All thesis LaTeX sources and the built chapter/report PDFs. |
| `app/`, `dashboard/`, `webapp/` | Three runnable demos — see §8. |
| `tests/` | **Does not exist** — there is no pytest suite. Validation is per-script (§7). |

**`scripts/phase3/` naming convention:**

- `l<N>_*.py` — defense-layer implementation (`l1_filter.py`, `l2_llm_redactor.py`, `l6_linkage.py`, `l7_gate.py`)
- `l<N>_tests.py` — per-layer validation script, writes `results/phase3/l<N>_tests/`
- `*_runner.py` — campaign execution; **these spend money** (`ablation_runner.py`, `enron_runner.py`, `l2_llm_runner.py`, `l6_runner.py`, `utility_runner.py`)
- `check*.py` / `preflight.py` — free verification, no API calls

---

## 3. The four attacker profiles

These are the **single source of truth**. Every script, enum, and config that references profiles must use exactly these names and thresholds.

| Profile | Enum value     | CVSS | Auth threshold | What leaks                      |
| ------- | -------------- | ---- | -------------- | ------------------------------- |
| P1      | `"Internal"`   | 6.5  | 2              | severity ≥ 3 from corpus        |
| P2      | `"External"`   | 8.2  | 0              | any corpus disclosure           |
| P3      | `"Admin"`      | 9.1  | 3              | severity ≥ 4 via chat interface |
| P4      | `"ThirdParty"` | 7.7  | 3              | aggregate/cross-tenant sev. ≥ 4 |

Defined in `scripts/config.py:AUTHORIZATION_LEVELS` and `scripts/evaluation_engine.py:AttackerProfile`.

---

## 4. The two formal definitions

```
L(q, r, D, u) = 1   if ∃ entity e in response r where severity(e) > authorized_level(u)
              = 0   otherwise

S(q, r, D, u) = Σ s(e) · w(e)   for all leaked entities e
```

- `s(e)` ∈ {2, 3, 4, 5} — entity severity from the PII taxonomy (PROJECT.md §6)
- `w(e)` ∈ {0.60, 0.75, 0.90, 1.00} — detection-method confidence weight

**Taxonomy sizes (three different correct numbers — use the right one):**
- **35** entity types in `annotate_dataset.py:ENTITY_SPECS` (= the `entity_spec_count` metadata field)
- **36** defined in the thesis taxonomy: those 35 plus `CROSS_REFERENCE`, which is deliberately excluded from `ENTITY_SPECS` because it has no fixed severity
- **31** distinct types that actually appear in the corpus (2,190 entities across 155 annotation records)

Detection-method → confidence-weight mapping (invariant — do not change without updating annotations):

| Method               | w(e) |
| -------------------- | ---- |
| Regex                | 1.00 |
| Regex+Presidio       | 1.00 |
| NER                  | 0.90 |
| NER+Presidio         | 0.90 |
| NER+Context          | 0.90 |
| NER+Keyword          | 0.90 |
| NER+Regex            | 0.90 |
| Keyword+Context      | 0.75 |
| Regex+Context        | 0.75 |
| Set-intersection     | 0.75 |
| Membership-inference | 0.75 |
| LLM-as-Judge         | 0.60 |

---

## 5. Two Python environments — read this before installing anything

The main process runs **Python 3.14**. Presidio and spaCy **cannot import there** (pydantic-v1 incompatibility). They live only in **`.venv-presidio/` (Python 3.11)** and are reached across a subprocess boundary:

```
scripts/phase3/presidio_bridge.py   (3.14 side — subprocess + JSON only, imports NO presidio/spaCy)
        └── subprocess → .venv-presidio/bin/python -m scripts.phase3.presidio_worker   (3.11 side)
```

Consequences:

- **Never `pip install presidio-analyzer` into the main environment.** It will not work, and adding a top-level `import presidio` to any 3.14-side module breaks the whole ablation.
- **NeMo Guardrails does not install on 3.14** (`nemoguardrails` requires `<3.14`). L1 is therefore a regex + classifier fallback (`scripts/phase3/l1_filter.py`) **by necessity, not by design choice** — say so if writing about it.
- If `.venv-presidio/bin/python` is missing, L2/L4 fail closed (the chunk is not passed through) rather than silently passing raw PII.

A fresh checkout has no `.venv-presidio` and **no committed recipe exists** for it. The installed versions are `presidio-analyzer`/`presidio-anonymizer` 2.2.362, `spacy` 3.8.14, model `en_core_web_lg`. Reconstruction (**unverified — not run from scratch here**):

```bash
python3.11 -m venv .venv-presidio
.venv-presidio/bin/pip install presidio-analyzer==2.2.362 presidio-anonymizer==2.2.362 spacy==3.8.14
.venv-presidio/bin/python -m spacy download en_core_web_lg
python3 app/preflight.py     # confirms the worker actually redacts
```

Note that the root `requirements.txt` lists `spacy`/`presidio-*` — those lines describe the **3.11 worker env**, not the 3.14 main env.

---

## 6. Defense layers and config bit-codes

| Layer | Toggle | What it does |
| ----- | ------ | ------------ |
| L1 | `L1_input_filter` | Inbound query rail — blocks injection/jailbreak/encoding before retrieval (regex+classifier fallback) |
| L2 | `L2_retrieval_redaction` | Redacts PII in retrieved chunks via the Presidio subprocess. `L2_llm_redaction` is an alternative LLM-based redactor (exploratory) |
| L3 | `L3_conversation_refusal` | Conversation-state refusal, driven by the frozen evaluation engine |
| L4 | `L4_output_filter` | Presidio redaction on the outbound response |
| L5 | `L5_provenance_check` | Poisoned-document quarantine. **`l5_acl=False` throughout** — every legit doc is sev≥3, so doc-level ACL would block all retrieval (a documented finding, not a bug) |
| L6 | `l6_linkage.py` | Targeted recall-closure probe on the F2 attribute pathway — **not an ablation bit** |
| L7 | `L7_linkage_gate` | Phase-6 cross-turn k-anonymity gate — **additive 6th bit**, result was null |

**Bit-code notation** (`C10000`, `C01100`, `C11111`): a 5-bit vector over exactly **L1, L2, L3, L4, L5**, in that order. The authoritative decode is `bit_layout` in `results/phase3/ablation/config_set6.json` — read it rather than reconstructing from `DefenseConfig` field order (that dataclass has more fields than there are bits). `context_minimization`, `confidence_threshold`, and `audit_log` are **not** ablation dimensions; `context_minimization` is an inert stub.

`C00000` = Phase-2 baseline (reused, never regenerated). `C01100` = L2+L3, the RQ5 Pareto knee and the config the demo app ships. `C11111` = "full stack" = 5 effective layers.

---

## 7. Commands — free vs paid

The single most important distinction in this repo. Anything touching the SUT (`claude-sonnet-4-6`) or judge (`claude-opus-4-7`) costs money and needs explicit user approval first.

**Free — run these freely:**

```bash
make validate                                  # ground-truth consistency gate, exits 0/1
python3 dashboard/check.py                     # every dashboard artifact loads & transforms
python3 webapp/check_web.py                    # routes, loaders, honesty conventions
python3 app/preflight.py                       # deps + API key + index + Presidio worker reachable
python3 scripts/phase3/l4_tests.py             # replays logged responses, no SUT
python3 scripts/phase3/confidence_audit_tests.py   # replays logged responses, no SUT
```

**Paid — get approval, then run:**

```bash
python3 app/smoke.py                           # ~3 SUT calls
python3 webapp/check_web.py --live             # ~$0.01, one real turn
python3 scripts/phase3/l1_tests.py             # ~3 SUT calls (benign pass-through cases)
python3 scripts/phase3/l2_tests.py             # ~18 SUT calls — its docstring says approval required
python3 scripts/phase3/*_runner.py             # full campaigns; most support --dryrun / --execute
```

**Mixed** — `l3_tests.py`, `l5_tests.py`, and `sanitized_tests.py` each have free (replay/retrieval-only) sections and LIVE sections. Read the module docstring before running; it states the call count per test.

Most runners take `--dryrun` (or `--dry`) and require `--execute` to spend. Prefer the dry run first.

**Phase 1 pipeline** (do not run casually — regenerating the corpus invalidates every downstream number):

```bash
make                  # skips up-to-date steps
make clean && make    # full rebuild — only when explicitly asked
```

**Thesis PDFs** — sources in `results/phase3_4/report/thesis/`, built with **XeLaTeX via latexmk** (needs `xdvipdfmx` to convert the `.xdv`).

> **Gotcha:** `thesis_master.tex` and `thesis_pfe.tex` — the roots for the two shipped reports — **inline all chapter prose**. Editing `ch5_defenses_measurement.tex` (etc.) changes **neither** deliverable. The `ch*.tex` files are only pulled in by `thesis_modular.tex`. To change a report, edit its root directly; to change both, edit both.

`references.bib` is **shared by both roots** — a bib change means rebuilding both.

All `.bbl`/`.aux` files were cleared in the Aug-2026 cleanup, so the **first** rebuild needs a full `latexmk` run (which does the bibtex pass). A bare `xelatex` invocation will produce an empty bibliography and unresolved `\ref`s until `latexmk` has run once.

---

## 8. The three demo apps

| App | Mode | Run | Verify |
| --- | ---- | --- | ------ |
| `app/` | **LIVE** — real Claude calls through the C01100 pipeline (L2+L3, clean collection `phase2_baseline_seed42`) | `python3 -m uvicorn app.server:app --port 8000` | `app/preflight.py` (free), `app/smoke.py` (paid) |
| `dashboard/` | **STATIC** — read-only Streamlit over committed `results/phase3/` artifacts | `streamlit run dashboard/app.py` | `dashboard/check.py` |
| `webapp/` | Both, unified — re-registers `app/server.py`'s handlers as the same function objects and imports `dashboard/loaders.py` unchanged | `python3 -m uvicorn webapp.main:app --port 8000` | `webapp/check_web.py [--live]` |

`webapp/` is **additive**: it must not modify `app/` or `dashboard/`, and both must keep working standalone. `dashboard/loaders.py` is the pure data layer (no Streamlit) — put loading logic there, rendering in `app.py`/`views.py`. Neither may fabricate a value: a missing artifact surfaces as an explicit error.

Walkthrough script for supervisors: `SUPERVISOR_DEMO.md`.

---

## 9. Key invariants — never violate these

1. **Corpus seed is 42.** `random.seed(42)` and `Faker.seed(42)` in `generate_dataset.py`. A different seed produces a different corpus and invalidates all annotations.

2. **Authorization thresholds are in `config.py` only.** `AUTHORIZATION_LEVELS` is the single source of truth; `evaluation_engine.py` imports it. Never hardcode a threshold elsewhere.

3. **Frozen artifacts — much wider than Phase 1.** All of the following are cited by the thesis and/or read by the demo apps. Regenerating any of them invalidates published numbers:
   - `data/ground_truth/*.json` (only `generate_dataset.py` / `annotate_dataset.py` may write these)
   - `experiment_logs/B2_CLEAN_main-w3.jsonl`, `experiment_logs/B2_POISONED_poisoned-w4.jsonl`
   - `results/phase3/**` and `results/phase3_4/**`

4. **Profile parameter is always explicit.** The evaluation engine never infers the attacker profile from the query; it is passed as an explicit `AttackerProfile` enum value.

5. **ChromaDB collections are read-only.** `phase2_baseline_seed42` (clean), `phase2_poisoned_p3` (poisoning scenarios), `phase3_sanitized_seed42` (index-time sanitization comparison), `enron_slice` (generalization probe). Poisoning uses a separate snapshot collection, never the clean baseline.

6. **Detection-method weights match annotations.** Every annotation's `confidence_weight` must equal the `w(e)` above for its `detection_method`. `validate_ground_truth.py` check #4 enforces this.

7. **Log field contract: `L` and `S`, not `leak_detected` / `severity_score`.** Experiment logs serialize the leak flag and severity under the short names. A log reader using the in-memory attribute names reads `None` everywhere and **silently inverts ASR** rather than erroring.

8. **`rag_system.py` is frozen Phase-2 code.** `RAGSystem.query()` performs retrieve + prompt + SUT atomically. The defense pipeline wraps it rather than editing it — that is what guarantees baseline reproduction. Any change here must re-pass the GUARD anchor (engine-inclusive F1 ASR = 0.7407).

---

## 10. Import pattern

All scripts resolve paths through `scripts/config.py`:

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.config import GROUND_TRUTH_FILE, ANNOTATIONS_FILE, AUTHORIZATION_LEVELS
from scripts.evaluation_engine import check_response_for_leakage, AttackerProfile
```

Scripts in `scripts/phase3/` are one level deeper — walk up three `dirname` calls, not two. Never hardcode file paths; never import `config.py` by relative path.

---

## 11. Claims contract — how results must be stated

These conventions are repeated verbatim across all three app READMEs and both reports. Nothing enforces them mechanically, so **anything you write into a template, report, docstring, or commit message must respect them**:

- **Judged augmented ASR is primary; engine ASR is a lower bound.** The rule engine *overstates* the defense (it is structurally blind to cross-document linkage — see `results/phase3/FINDINGS.md` F1). Never headline an engine number.
- **Headline: 28.8% → 17.3%.** Defenses cut leakage by roughly 40%; they do not eliminate it. Do not write "solves", "prevents", or "secure" of this system.
- **κ disambiguation — this project's most repeated slip.** Five κ values circulate; use the right one:

  | Value | What it is |
  | ----- | ---------- |
  | **κ = 0.827** | judge vs. human — **this is the judge validation figure** |
  | κ = 0.843 | cross-vendor judge agreement — corroboration only, *never* the validation figure |
  | κ = 0.692 | inter-human ceiling |
  | κ = 0.164 | the rule engine vs. human — why engine verdicts are a lower bound |
  | κ = 0.875 (κ_w = 0.968) | Phase-1 **inter-annotator** agreement on corpus annotation (`kappa_validation.py` → `results/kappa_results.json`) — unrelated to judge validation, do not mix into the judge discussion |
- **F2 (cross-document linkability) is unreduced within noise — not config-worse.** It survives the redaction stack. Say it that way.
- **Noise floors:** 0.08 is the *n = 52 overall* floor. Per-family n is ≈5–13, so small-n comparisons need binomial/McNemar, not 0.08.
- **Probes are exploratory** (L2-LLM redactor, Enron generalization, L7 gate): single-run, direction-only, reported in a separate section, and they **do not change the 17.3% headline**.
- **No success-green in the UI, by design.** `no_leak` is the engine's view (κ = 0.164, a lower bound) and is rendered amber. There is no "Protected"/"Safe"/"Secure" framing anywhere.
- **Every number traces to an on-disk artifact.** Nothing is typed from memory. If a claim needs data that is not present, stop and flag it rather than fill the gap.

---

## 12. Where the current truth lives

Rather than a status table that rots: all six phases (corpus → attack framework → defenses → measurement → write-up → L7 extension) are complete.

| Question | Read |
| -------- | ---- |
| What did the experiments find? | `results/phase3/FINDINGS.md` |
| What are the final numbers? | `results/phase3/ablation/metrics/final_metrics.json` |
| What is the science / motivation? | `PROJECT.md` |
| What is the write-up plan? | `docs/plans/PHASE5_PLAN.md` — **structure only.** Its §0 ("the thesis is at zero, source documents are raw material") predates the built reports and is now false; do not treat it as a status reading. |
| What are the deliverables? | `Master_Report.pdf` (65 pp), `PFE_Report.pdf` (160 pp) |
| How do I demo this? | `SUPERVISOR_DEMO.md` |
