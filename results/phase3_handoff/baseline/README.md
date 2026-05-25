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
