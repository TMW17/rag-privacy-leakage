"""
presidio_bridge.py — SUBPROCESS boundary contract for the Presidio-backed layers (L2/L4).

WHY A SUBPROCESS: Presidio + spaCy CANNOT import under the project's Python 3.14
(pydantic-v1 incompatibility). They run ONLY under ``.venv-presidio`` (Python 3.11).
Therefore the 3.14 defense pipeline MUST NOT import presidio/spaCy. L2 (retrieval
redaction) and L4 (output filter) redact text by invoking a worker under the OTHER
interpreter as a subprocess, exchanging JSON over stdin/stdout.

This module is a STUB: ``redact()`` raises ``NotImplementedError`` so nothing imports
spaCy into the 3.14 process before the Sprint-1 worker exists. It imports NOTHING from
presidio/spaCy — only stdlib.

SPRINT-1 CONTRACT
-----------------
Worker (new file, runs under .venv-presidio):  scripts/phase3/presidio_worker.py
  - reads JSON  {"texts": [str, ...], "entities": [str, ...] | null}  from stdin
  - builds AnalyzerEngine (en_core_web_lg) + the custom recognizers from
    scripts/phase3/presidio_recall.py (NNI_DZ, EMPLOYEE_ID, HEALTH_RECORD_ID, IBAN_DZ,
    and the bin-(a) secret detectors) + AnonymizerEngine
  - writes JSON  {"redacted": [str, ...]}  to stdout

Bridge (this file, runs under Python 3.14):
    redact(texts, entities=None) ->
        subprocess.run([VENV_PY, "-m", "scripts.phase3.presidio_worker"],
                       input=json.dumps({"texts": texts, "entities": entities}),
                       capture_output=True, text=True, cwd=ROOT, timeout=...)
        return json.loads(proc.stdout)["redacted"]
  The 3.14 side does ONLY subprocess + JSON; it never imports presidio/spaCy.
"""
import json
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VENV_PY = os.path.join(ROOT, ".venv-presidio", "bin", "python")
WORKER_MODULE = "scripts.phase3.presidio_worker"


def redact(texts, sev_threshold=3, timeout=300):
    """
    Redact entities with taxonomy severity >= sev_threshold in each of ``texts``,
    by running presidio_worker under .venv-presidio (Python 3.11) as a subprocess.

    The 3.14 caller does ONLY subprocess + JSON — it never imports presidio/spaCy.

    Returns the worker's full result dict:
      {"redacted": [str,...], "stats": [...], "threshold": int,
       "unknown_labels_failclosed": [...], "label_severity": {...}}
    """
    if not isinstance(texts, list):
        raise TypeError("texts must be a list[str]")
    if not os.path.exists(VENV_PY):
        raise RuntimeError(f".venv-presidio interpreter not found at {VENV_PY}")
    proc = subprocess.run(
        [VENV_PY, "-m", WORKER_MODULE],
        input=json.dumps({"texts": texts, "sev_threshold": sev_threshold}),
        capture_output=True, text=True, cwd=ROOT, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"presidio_worker failed (rc={proc.returncode}). stderr tail:\n{proc.stderr[-2000:]}")
    out = json.loads(proc.stdout)
    if len(out.get("redacted", [])) != len(texts):
        raise RuntimeError("presidio_worker returned wrong number of redacted texts")
    return out
