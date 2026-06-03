"""
check_web.py — verification for the unified app.

FREE (default):  python3 webapp/check_web.py
  - every route returns 200; /health reports config C01100;
  - every dashboard page renders a LOADED loader value (proves artifact-loading, not error panels);
  - CHECK #3 loader-diff: every dashboard/loaders.* call used by dashboard/app.py is still used by
    webapp/views.py, and views.py contains NO metric literals;
  - honesty strings present & prominent (engine-blindness band, judged-primary, kappa 0.827 vs 0.843,
    probes direction-only); NO success framing (Protected/Safe/Secure); NO green token in the CSS;
  - /dashboard/img/<missing> returns an explicit 404 error, never a fabricated value.

PAID (~$0.01, one Sonnet turn):  python3 webapp/check_web.py --live
  - one real turn through the unified /chatbot/chat; asserts the audit verdict + severity match the
    committed standalone smoke (app/smoke/smoke_results.json) → proves the reused handler drives the
    identical C01100 pipeline (Presidio subprocess + live SUT) end-to-end.
"""
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from fastapi.testclient import TestClient            # noqa: E402
import main as webmain                               # noqa: E402  (sets up paths, builds app)
from dashboard import loaders as L                   # noqa: E402

client = TestClient(webmain.app)
_fail = []


def ok(cond, label, detail=""):
    print(f"  [{'OK ' if cond else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not cond:
        _fail.append(label)
    return cond


def section(t):
    print("\n" + t)


# ── 1. routes load ──────────────────────────────────────────────────────────
section("1 · routes return 200")
PAGES = {"/": "home", "/chatbot": "chatbot", "/dashboard/ablation": "ablation",
         "/dashboard/rq5": "rq5", "/dashboard/risk": "risk", "/dashboard/rq3": "rq3",
         "/dashboard/probes": "probes"}
HTML = {}
for route in PAGES:
    r = client.get(route)
    HTML[route] = r.text
    ok(r.status_code == 200, f"GET {route}", f"{r.status_code}, {len(r.text)} B")

h = client.get("/health")
ok(h.status_code == 200 and h.json().get("config") == "C01100",
   "GET /health is C01100", json.dumps(h.json()))

# ── 2. dashboard pages render LOADED loader values (not error panels, not fabricated) ─────────────
section("2 · loaded values are rendered (loaders → page)")
try:
    head = L.headline()
    land = HTML["/"]
    ok(f"{head['baseline_pct']:.1f} %" in land, "landing baseline card = loaders.headline", f"{head['baseline_pct']:.1f} %")
    ok(f"{head['fullstack_pct']:.1f} %" in land, "landing full-stack card = loaders.headline", f"{head['fullstack_pct']:.1f} %")
    ok(f"{head['delta_pp']:+.1f} pp" in land, "landing delta card = loaders.headline", f"{head['delta_pp']:+.1f} pp")
    ok(bool(head["knee"]) and head["knee"] in land, "landing knee card = loaders (pareto is_knee)", head["knee"])
    ok("Judged ASR (PRIMARY)" in land and "C11111" in land, "landing six-cell table rendered", "from loaders.six_cell")
    _, k = L.kappa()
    rq3 = HTML["/dashboard/rq3"]
    ok(f"{k['judge_human_kappa']:.3f}" in rq3, "RQ3 judge–human κ = loaders.kappa", f"{k['judge_human_kappa']:.3f}")
    ok(f"{k['claude_gptoss_kappa']:.3f}" in rq3, "RQ3 cross-vendor κ = loaders.kappa", f"{k['claude_gptoss_kappa']:.3f}")
    u = L.l2llm()["utility_benign"]["context_precision"]
    ok(str(u["C01000_LLM"]) in HTML["/dashboard/probes"], "probe context-precision = loaders.l2llm", str(u["C01000_LLM"]))
except Exception as e:
    ok(False, "loaded-value rendering", f"{type(e).__name__}: {e}")

# ── 3. CHECK #3 — loader-diff + no metric literals in views.py ────────────────────────────────────
section("3 · CHECK #3 — loader-usage diff (dashboard/app.py vs webapp/views.py)")


def loaders_used(path):
    # capture every `L.<name>` reference — the dashboard passes loaders as references
    # (guard(L.six_cell)), NOT as `L.six_cell(...)`, so requiring a trailing "(" would match
    # nothing and make this diff vacuously true. Match the attribute, call or not.
    with open(path, encoding="utf-8") as f:
        return set(re.findall(r"\bL\.([a-zA-Z_][a-zA-Z0-9_]*)", f.read()))


app_loaders = loaders_used(os.path.join(ROOT, "dashboard", "app.py"))
view_loaders = loaders_used(os.path.join(HERE, "views.py"))
missing = app_loaders - view_loaders
print(f"     dashboard/app.py uses : {sorted(app_loaders)}")
print(f"     webapp/views.py uses  : {sorted(view_loaders)}")
ok(not missing, "every dashboard loader still used by the unified app", f"missing={sorted(missing)}" if missing else "none missing")

with open(os.path.join(HERE, "views.py"), encoding="utf-8") as f:
    view_src = f.read()
metric_literals = re.findall(r"(?<![\w.])\d+\.\d+", view_src)     # float literals = would-be hardcoded metrics
ok(not metric_literals, "views.py contains NO metric literals (values come from loaders only)",
   f"found {metric_literals}" if metric_literals else "zero floats")

# ── 4. honesty survived the redesign (present AND prominent) ──────────────────────────────────────
section("4 · honesty framing present")
chat = HTML["/chatbot"]
ok("κ = 0.164" in chat and "NOT a safety guarantee" in chat.replace("\n", " "),
   "chatbot engine-blindness band present (κ=0.164, no_leak not a guarantee)")
ok('class="audit-warn"' in chat, "engine-blindness band is the prominent .audit-warn callout (not a footnote)")
ok("'v-engineblind'" in chat and "v-engineblind" in chat,
   "no_leak renders AMBER (v-engineblind), never green")
ok("not a certified system" in chat and "does <b>not</b> solve cross-document linkability" in chat,
   "chatbot 'demonstration, not certified / does not solve linkability' present")
ok(("READING" in chat or "How to read this" in chat) and "the demonstration, not a" in chat,
   "READING.md honest reading embedded on the chatbot page")
no_success = not any(w in chat for w in ["Protected", "Safe ✓", "Secure ✓", "✅ Safe", "All clear"])
ok(no_success, "NO Protected/Safe/Secure success framing on the chatbot")

ok("Judged augmented ASR is the PRIMARY metric" in HTML["/"], "landing: judged-primary framing")
ok("unreduced, NOT config-worse" in HTML["/"].replace("\n", " "), "landing: F2 unreduced-not-worse framing")
ok("VALIDATION figure" in HTML["/dashboard/rq3"] and "never the validation figure" in HTML["/dashboard/rq3"],
   "RQ3: κ validation vs corroboration framing")
ok("single-run, direction-only" in HTML["/dashboard/probes"] and "17.3" in HTML["/dashboard/probes"],
   "probes: single-run/direction-only + 17.3% headline unchanged")
ok("not a measured win over the knee" in HTML["/dashboard/rq5"], "RQ5: knee within-noise framing")

# ── 5. no green-as-success token anywhere in the CSS ──────────────────────────────────────────────
section("5 · no success-green in the stylesheet")
with open(os.path.join(HERE, "static", "style.css"), encoding="utf-8") as f:
    css = f.read()
greenish = []
for hx in re.findall(r"#([0-9a-fA-F]{6})\b", css):
    r_, g_, b_ = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
    if g_ == max(r_, g_, b_) and g_ - r_ > 30 and g_ - b_ > 30:        # green-dominant
        greenish.append("#" + hx)
ok(not greenish, "CSS has no green-dominant color token", f"found {greenish}" if greenish else "none")

# ── 6. missing artifact → explicit error (never fabricated) ───────────────────────────────────────
section("6 · images + missing-artifact behaviour")
for name in ("fig_marginal", "pareto_png", "l2llm_png"):
    r = client.get(f"/dashboard/img/{name}")
    ok(r.status_code == 200 and r.headers.get("content-type", "").startswith("image/"),
       f"GET /dashboard/img/{name}", f"{r.status_code} {r.headers.get('content-type')}")
miss = client.get("/dashboard/img/__does_not_exist__")
ok(miss.status_code == 404 and "error" in miss.json(), "missing image → explicit 404 error (not fabricated)",
   json.dumps(miss.json()))


# ── optional: one LIVE turn (paid) ────────────────────────────────────────────────────────────────
def live_turn():
    section("LIVE · one real turn through /chatbot/chat (PAID ~$0.01)")
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        ok(False, "ANTHROPIC_API_KEY set", "missing — cannot run the live turn")
        return
    smoke = json.load(open(os.path.join(ROOT, "app", "smoke", "smoke_results.json")))
    q2 = next(t for t in smoke["turns"] if t["id"] == "Q2-direct-PII")
    t0 = time.time()
    r = client.post("/chatbot/chat", json={"message": q2["query"], "profile": "Internal"})
    dt = time.time() - t0
    ok(r.status_code == 200, "live POST /chatbot/chat", f"{r.status_code}, {dt:.1f}s wall-clock")
    j = r.json()
    a = j["audit"]
    print(f"     response (first 240 chars): {j['response'][:240].replace(chr(10), ' ')}…")
    print(f"     layers_fired   : {a['layers_fired']}")
    print(f"     retrieved_ids  : {a['retrieved_doc_ids']}")
    print(f"     engine verdict : {a['verdict']}  |  severity_S = {a['severity_S']}")
    ok(dt > 1.0, "real latency (a live Claude call, not a mock)", f"{dt:.1f}s")
    ok("L2_retrieval_redaction" in a["layers_fired"] and "LLM_SUT" in a["layers_fired"],
       "L2 subprocess + live SUT both fired", str(a["layers_fired"]))
    ok(len(a["retrieved_doc_ids"]) > 0, "retrieval ran (k chunks)", str(a["retrieved_doc_ids"]))
    exp = q2["audit"]
    ok(a["verdict"] == exp["verdict"] and a["severity_S"] == exp["severity_S"],
       "audit verdict + severity match committed standalone smoke",
       f"unified=({a['verdict']}, S={a['severity_S']})  smoke=({exp['verdict']}, S={exp['severity_S']})")
    print("     NOTE: response prose may vary turn-to-turn; the engine verdict + severity are the "
          "behaviour-equivalence check (same pipeline). 'no_leak' here is the engine's lower-bound view.")


if "--live" in sys.argv:
    live_turn()

print("\n" + ("=" * 70))
print("RESULT:", "ALL PASS" if not _fail else f"{len(_fail)} FAILURE(S): {_fail}")
sys.exit(0 if not _fail else 1)
