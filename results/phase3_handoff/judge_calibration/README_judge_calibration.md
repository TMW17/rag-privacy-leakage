# judge_calibration/

Artefacts from the LLM-as-Judge calibration pass (W5.4–W5.5).

| File | Description |
|------|-------------|
| `kappa_results.json` | Cohen's κ: judge-vs-human = 0.83 (binary), 0.84 (categorical) |
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
