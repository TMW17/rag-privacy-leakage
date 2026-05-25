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
