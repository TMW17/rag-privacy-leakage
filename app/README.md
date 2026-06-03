# Secure RAG Chatbot — C01100 (demonstration)

A runnable FastAPI chatbot that wires the **RQ5-recommended defense config C01100** in front of the
synthetic-corpus RAG system:

- **L2** — retrieval-time PII redaction (Microsoft Presidio, run in the `.venv-presidio` subprocess
  worker, **fail-closed**: on any worker error the chunk is not passed through),
- **L3** — conversation-state refusal,
- **audit_log** — a structured per-turn record (timestamp, profile, layers fired, retrieved doc-ids,
  engine verdict, severity *S*, confidence gate),
- **confidence_threshold** — a severity-*S* circuit-breaker (default *S* > 10 → suppress).

SUT = **Claude Sonnet 4.6** (temp 0). Index = the **clean** (non-poisoned) synthetic collection
`phase2_baseline_seed42`. ACL is off (`l5_acl=False`) — the synthetic corpus is uniformly sev≥3, so
per-profile ACL has nothing to bite on (provenance-only; see the Sprint-3 report §8).

> **This is a demonstration of the recommended configuration, not a certified system.** It does
> **not** solve cross-document **linkability** — the report's F2 finding (linkability survives the
> redaction stack) stands. The prototype shows the config's behaviour; it adds a runnable artifact,
> not a new result. The 17.3 % judged-ASR headline is unchanged.

## Prerequisites

- `ANTHROPIC_API_KEY` set in the environment (the SUT makes live Claude calls).
- The `.venv-presidio` worker (Python 3.11) — already used by the ablation; L2 calls it as a
  subprocess.
- Deps: `pip install fastapi uvicorn` (already present here: fastapi 0.135, uvicorn 0.41).

## 1. Pre-flight (free, no API)

```bash
python3 app/preflight.py
```
Confirms deps + API key + that the clean index responds and the Presidio worker redacts — so the
paid smoke calls don't fail mid-run.

## 2. Run the chatbot

```bash
# from the repo root
python3 -m uvicorn app.server:app --port 8000
```
Open **http://localhost:8000**. Type a question; the response and the **per-turn audit entry** appear
side by side. Use the profile selector (Internal / External / Admin) and **Reset** to clear the
session. Stop with `Ctrl+C`.

## 3. Smoke test (paid: ~3 SUT calls)

```bash
python3 app/smoke.py
```
Runs three queries — benign / direct-PII (national IDs) / F2-linkability — prints each response with
its audit entry, computes cost from token usage, and writes `app/smoke/smoke_results.json`.

## Files

- `pipeline.py` — shared C01100 pipeline factory (used by server + smoke).
- `server.py` — FastAPI backend + inline chat UI (`/chat`, `/reset`, `/health`, `/`).
- `preflight.py` — free pre-flight checks.
- `smoke.py` — the 3-call smoke test.
- `smoke/` — smoke output (`smoke_results.json`).
