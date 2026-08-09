# Part A analysis scripts

Every statistic in a Part A markdown deliverable is emitted by one of these scripts
(hard rule 11 / amendment 1). Nothing is typed from memory.

All scripts are **read-only** with respect to `data/`, `results/` and `experiment_logs/`.
Output goes to `analysis/partA/out/*.json` only.

| Script | Emits | Answers |
|---|---|---|
| `lib_partA.py` | — | shared paths, io, and the canonical scoring path (a deliberate mirror of `scripts/phase3_4/baseline_regen_judge_and_score.py`, guarded by `verify_scorer_matches_published()`) |
| `p0_preflight_verify.py` | `out/p0_preflight_verify.json` | cleanup-commit deletion audit, `test.py` history secret scan, effective `switchModelsOnFlag` precedence, MCP inventory |
| `p0_sanity_checks.py` | `out/p0_sanity_checks.json` | the three TASK_SPEC §3.2 sanity checks + the amendment 3(c) canonicity gate + per-run baseline decomposition |
| `p0_regen_provenance.py` | `out/p0_regen_provenance.json` | what `baseline_regen` is, byte-identity vs the canonical log, the judge-determinism test, the amendment 4 truncation audit |
| `p0_inventory.py` | `out/p0_inventory.json` | repo tree, 154 data artifacts, the 28-item required-artifact checklist, frozen-artifact tracking status, registry-vs-executed reconciliation, manuscript float mapping |
| `d1_engine_arithmetic.py` | `out/d1_engine_arithmetic.json` | directive D1: every defensible reading of baseline strict ASR (scenario/execution/turn, per-run/pooled/union), which reading each published figure equals, and a sweep over alternate strict definitions |
| `p0_verify_followups.py` | `out/p0_verify_followups.json` | four checks that qualify the above: locked-verdict per-run independence, true distinct-input n for the judge-determinism test, which manuscript the review's float numbers fit, and the distinct unjudged non-empty responses |

Re-run all four (free, no API calls, deterministic):

```bash
python3 analysis/partA/scripts/p0_preflight_verify.py
python3 analysis/partA/scripts/p0_sanity_checks.py
python3 analysis/partA/scripts/p0_regen_provenance.py
python3 analysis/partA/scripts/p0_inventory.py
python3 analysis/partA/scripts/p0_verify_followups.py
python3 analysis/partA/scripts/d1_engine_arithmetic.py
```

No script uses wall-clock time or an RNG, so output is byte-stable for a given repository
state (file mtimes are reported as data, not used in any figure).
