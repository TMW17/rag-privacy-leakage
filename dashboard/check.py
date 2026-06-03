"""
check.py — headless verification for the Phase-3 dashboard (no Streamlit runtime, no browser).

Confirms: (1) app.py parses (syntax), (2) deps present, (3) every committed artifact LOADS and every
JSON/CSV->table transform runs. Exits non-zero on any missing/malformed artifact. Run:  python3 dashboard/check.py
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import loaders as L  # noqa: E402

ok = True

# 1. app.py syntax (parse without importing, so no Streamlit render is triggered)
try:
    ast.parse(open(os.path.join(HERE, "app.py")).read())
    print("[OK]   app.py syntax")
except SyntaxError as e:
    ok = False
    print(f"[FAIL] app.py syntax: {e}")

# 2. dependencies
for m in ("streamlit", "pandas"):
    try:
        mod = __import__(m)
        print(f"[OK]   dep {m} {getattr(mod, '__version__', '')}")
    except Exception as e:
        ok = False
        print(f"[FAIL] dep {m}: {e}")

# 3. artifacts load + transforms run
print("--- artifact + transform verification ---")
for name, status, detail in L.verify_all():
    print(f"  [{status:7}] {name}: {detail}")
    if status != "OK":
        ok = False

print("\nRESULT:", "ALL OK — dashboard will load every panel from real artifacts" if ok
      else "ISSUES FOUND (see above)")
sys.exit(0 if ok else 1)
