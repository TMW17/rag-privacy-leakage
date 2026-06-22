# Unified web app — defense demonstration & results

One FastAPI server, one visual language, presenting the two committed Phase-3/4 deliverables together:

- the **LIVE secure-RAG chatbot** (`app/`) — the recommended config **C01100**, making real Claude
  Sonnet 4.6 calls through the L2 (`.venv-presidio`) + L3 pipeline;
- the **STATIC results dashboard** (`dashboard/`) — read-only views of the committed
  `results/phase3/` artifacts.

It is an **additive layer**: it does not modify `app/` or `dashboard/`. Both still run standalone
(`python3 -m uvicorn app.server:app` and `streamlit run dashboard/app.py`). This app reuses their code:

- the chatbot's request handlers (`app/server.py:chat/reset/health`) are **re-registered here as the
  exact same function objects**, so `/chatbot/chat` drives the identical C01100 pipeline with zero
  behavioural drift (same lazy `begin_scenario`, same `audit_records[-1]`, same Presidio subprocess);
- the dashboard's data layer (`dashboard/loaders.py`) is **imported unchanged** via `webapp/views.py`,
  which only reshapes loader output for templates and **never fabricates a value** — a missing
  artifact surfaces as an explicit error.

## Run

```bash
# from the repository root
python3 -m uvicorn webapp.main:app --port 8000
```

Open **http://localhost:8000**. Navigation: **Home** (headline) · **Live Chatbot** · **Ablation** ·
**Security–Utility (RQ5)** · **Risk matrix** · **Judge validation (RQ3)** · **Exploratory probes**.

A coloured ribbon on every page says which mode you are looking at: **LIVE** (amber — real Claude
calls) vs **STATIC** (slate — committed artifact reads).

Prereqs: `ANTHROPIC_API_KEY` set (for the live chatbot only); the `.venv-presidio` worker (used by L2);
`fastapi uvicorn jinja2 markdown` (all already present here).

A header toggle (🌙 / ☀️) switches the dark-navy ⇄ light theme (defaults to dark, persisted per browser).

## Demonstrating to supervisors

For a guided, copy-paste walkthrough — launch commands, five demo prompts with expected results and how
to interpret them, the engine-vs-judge reading, and honest talking points — see
[`../SUPERVISOR_DEMO.md`](../SUPERVISOR_DEMO.md).

## Verify

```bash
python3 webapp/check_web.py          # FREE: routes, loaded values, loader-diff, honesty, no-green, missing→error
python3 webapp/check_web.py --live   # PAID (~$0.01): one real turn; asserts audit == committed smoke
```

## Honesty conventions (carried verbatim from the committed deliverables)

- **Judged augmented ASR is PRIMARY; engine ASR is a lower-bound annotation.**
- The chatbot's **engine-blindness caption is promoted**, not buried: the audit verdict is the rule
  engine's view (κ = 0.164, a lower bound); **`no_leak` is not a safety guarantee** and renders
  **amber, never green**. There is **no Protected/Safe/Secure** framing, by design.
- **F2 (linkability) is unreduced (within noise), NOT config-worse.**
- **κ = 0.827 (judge–human) is the validation; κ = 0.843 (cross-vendor) is corroboration** — never
  the validation figure.
- The **exploratory probes** are single-run / direction-only and do **not** change the 17.3 % headline.
- **Live chatbot responses vary run-to-run** (temp-0 nondeterminism, varying retrieval), so a single live answer
  may look cleaner or leakier than another. The **frozen smoke evidence** in `app/smoke/` is the reproducible
  demonstration — the F2 linkability finding rests on it, not on any single live generation.

## Files

- `main.py` — the FastAPI app: landing + re-registered chatbot endpoints + dashboard routes.
- `views.py` — dashboard view-models over `dashboard/loaders.py` (no metric literals).
- `templates/` — Jinja2 templates (the honest-framing prose lives here, reviewable as plain HTML).
- `static/style.css` — the single stylesheet (no success-green token, by design).
- `check_web.py` — headless verification (+ optional `--live` turn).
