"""
preflight.py — FREE checks before any paid smoke call. No API calls.

Confirms: deps present + ANTHROPIC_API_KEY set; the clean index collection responds; the
.venv-presidio worker answers a stub redaction (fail-closed L2). Exits non-zero on any failure so
the ~3 paid smoke calls don't fail mid-run. Run:  python3 app/preflight.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ok = True


def check(label, fn):
    global ok
    try:
        detail = fn()
        print(f"  [OK]   {label}: {detail}")
    except Exception as e:
        ok = False
        print(f"  [FAIL] {label}: {type(e).__name__}: {e}")


print("=" * 70)
print("PRE-FLIGHT (free, no API) — C01100 chatbot")
print("=" * 70)


def _deps():
    import anthropic, fastapi, uvicorn  # noqa: F401
    return f"anthropic {anthropic.__version__}, fastapi {fastapi.__version__}, uvicorn {uvicorn.__version__}"


def _key():
    k = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not k:
        raise RuntimeError("ANTHROPIC_API_KEY not set (smoke calls would fail)")
    return f"set ({len(k)} chars)"


def _index():
    import pipeline as P
    rag = P.RAGSystem(P.CLEAN_COLLECTION, k=5)
    cr = rag._collection.query(
        query_embeddings=[rag._embedder.encode(["office working hours"])[0].tolist()], n_results=3)
    n = len(cr["documents"][0])
    if n == 0:
        raise RuntimeError("clean index returned 0 chunks")
    return f"collection '{P.CLEAN_COLLECTION}' responded, {n} chunks"


def _worker():
    from scripts.phase3.presidio_bridge import redact
    r = redact(["Employee national ID 249827706."], sev_threshold=3)
    if "<" not in r["redacted"][0]:
        raise RuntimeError("worker did not redact a sev>=3 national ID (fail-closed concern)")
    return f".venv-presidio worker answered; national ID -> {r['redacted'][0]}"


check("dependencies", _deps)
check("ANTHROPIC_API_KEY", _key)
check("clean index responds", _index)
check("Presidio L2 worker (stub redaction)", _worker)

print("\nRESULT:", "PASS — cleared for the ~3-call smoke test" if ok else "FAIL — fix before spending")
sys.exit(0 if ok else 1)
