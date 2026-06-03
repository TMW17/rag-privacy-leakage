# Phase-3 Dashboard

A read-only Streamlit dashboard that **loads the committed `results/phase3/` artifacts** and presents
the Phase-3 (Defense Layer Evaluation) story. It **never recomputes a metric, makes an API call, or
fabricates data** — every number and figure is read from a committed artifact, and a missing file is
shown as an explicit error rather than a made-up value.

## Run

```bash
# from the repository root
pip install streamlit pandas          # if not already installed
streamlit run dashboard/app.py
```

Then open the URL Streamlit prints (default `http://localhost:8501`).

## Headless check (no browser)

```bash
python3 dashboard/check.py
```

Verifies that `app.py` parses, the dependencies are present, and **every artifact loads and every
JSON/CSV → table transform runs**. Exits non-zero if any artifact is missing or malformed.

## Tabs

| Tab | Shows | Source artifact(s) |
|-----|-------|--------------------|
| Overview | Headline (28.8 % → 17.3 %), six-cell judged ΔASR table, GUARD, dual noise floor | `ablation/metrics/final_metrics.json` |
| Ablation | Per-family & per-profile judged ASR; per-layer marginal + RQ2 staircase figure | `final_metrics.json`, `ablation/metrics/fig_marginal_and_rq2.png` |
| Security–Utility (RQ5) | Noise-aware Pareto figure + table; knee = C01100 | `tradeoff/pareto.png`, `tradeoff/pareto_data.csv` |
| Risk matrix | Family table + 31-entity table (two likelihood bases) | `risk_matrix/risk_matrix*.csv`, `risk_matrix.json` |
| Judge validation (RQ3) | κ table + RQ3 summary | `final_metrics.json` (RQ3, cited from Sprint 0) |
| Exploratory probes | L2-LLM redactor + Enron generalization (Task 3.6) | `l2_llm/*`, `enron/enron_results.json` |

## Honesty conventions (carried into the UI, matching the reports)

- **Judged augmented ASR is PRIMARY; engine ASR is a lower-bound annotation** — the engine overstates
  the defense.
- **F2 (linkability)** is annotated *unreduced (within noise), NOT config-worse* wherever it appears.
- **κ = 0.827 is the validation** (judge vs human); **κ = 0.843 is cross-vendor corroboration** —
  never the validation figure. The inter-human ceiling is 0.692.
- The **exploratory probes** tab is explicitly *single-run / direction-only* and **does not change the
  17.3 % headline**.
- The **0.08 noise floor** is the *n = 52 overall* floor; per-family small-n significance uses
  binomial / McNemar, not 0.08.

## Files

- `app.py` — the Streamlit UI (rendering only).
- `loaders.py` — pure data layer (artifact paths, loaders, JSON/CSV → table transforms); no Streamlit,
  so it is independently testable.
- `check.py` — headless verification.
