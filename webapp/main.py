"""
main.py — the UNIFIED web app: one FastAPI server, one visual language, over two existing layers:

  • the LIVE secure-RAG chatbot  (app/  — FastAPI; the C01100 pipeline)        → real Claude calls
  • the STATIC results dashboard (dashboard/ — committed results/phase3/ reads) → no recomputation

Design = "port the dashboard's views into the FastAPI app" (architecture option b). It reuses the
two committed code paths UNCHANGED:
  - the chatbot's request handlers are RE-REGISTERED here as the *exact same function objects* from
    app/server.py (so `/chatbot/chat` drives the identical C01100 pipeline — the .venv-presidio L2
    subprocess, the lazy begin_scenario, the audit_records[-1] read — with zero behavioural drift);
  - the dashboard's data layer (dashboard/loaders.py) is imported UNCHANGED via webapp/views.py,
    which only reshapes loader output for templates and never fabricates a value.

Run:  python3 -m uvicorn webapp.main:app --port 8000   (from the repo root)  →  http://localhost:8000
Headless check (free):  python3 webapp/check_web.py
Live end-to-end turn (paid ~$0.01):  python3 webapp/check_web.py --live
"""
import base64
import os
import secrets
import sys

from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))            # webapp/
ROOT = os.path.dirname(HERE)                                 # repo root
load_dotenv(os.path.join(ROOT, ".env"))                      # DEMO_PASSWORD / ANTHROPIC_API_KEY
sys.path.insert(0, ROOT)                                     # so `app.*` and `dashboard.*` resolve
sys.path.insert(0, HERE)                                     # so `import views` resolves

import markdown as _md                                       # noqa: E402
from fastapi import FastAPI, Request                         # noqa: E402
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, Response  # noqa: E402
from fastapi.staticfiles import StaticFiles                  # noqa: E402
from fastapi.templating import Jinja2Templates               # noqa: E402

from app import server as chatbot                            # noqa: E402  — reuse handlers UNCHANGED
from dashboard import loaders as L                           # noqa: E402  — for /dashboard/img only
import views                                                 # noqa: E402  — dashboard view-models

templates = Jinja2Templates(directory=os.path.join(HERE, "templates"))
app = FastAPI(title="Privacy leakage in enterprise RAG — demonstration & results")
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")

CONFIG_LABEL = "C01100 (L2 retrieval-redaction + L3 refusal · audit_log + confidence_threshold ON)"


# ── optional password gate (HTTP Basic Auth) ─────────────────────────────────────────────────────
# Active ONLY when DEMO_PASSWORD is set in the environment (.env, gitignored). Gates the whole app —
# including the PAID chatbot endpoints — so a public tunnel link can be shared without exposing the
# Anthropic tokens to anyone who has the URL. /health stays open for liveness checks. Constant-time
# credential comparison; a missing/wrong credential returns 401 so the browser shows a login prompt.
_DEMO_USER = os.environ.get("DEMO_USER", "demo")
_DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "")


@app.middleware("http")
async def _password_gate(request: Request, call_next):
    if _DEMO_PASSWORD and request.url.path != "/health":
        ok = False
        header = request.headers.get("authorization", "")
        if header.startswith("Basic "):
            try:
                user, _, pw = base64.b64decode(header[6:]).decode("utf-8").partition(":")
                ok = (secrets.compare_digest(user, _DEMO_USER)
                      and secrets.compare_digest(pw, _DEMO_PASSWORD))
            except Exception:
                ok = False
        if not ok:
            return Response("Authentication required.", status_code=401,
                            headers={"WWW-Authenticate": 'Basic realm="RAG privacy demonstration"'})
    return await call_next(request)


# ── chatbot endpoints: the EXACT committed handler objects, re-registered (behaviour unchanged) ──
app.add_api_route("/chatbot/chat", chatbot.chat, methods=["POST"])
app.add_api_route("/chatbot/judge", chatbot.judge, methods=["POST"])   # second-pass Opus judge verdict
app.add_api_route("/chatbot/history", chatbot.history, methods=["GET"])         # all prompts + results
app.add_api_route("/chatbot/history/clear", chatbot.history_clear, methods=["POST"])
app.add_api_route("/chatbot/reset", chatbot.reset, methods=["POST"])
app.add_api_route("/health", chatbot.health, methods=["GET"])


def _render(request, template, nav, ctx=None):
    payload = {"request": request, "nav": nav}
    if ctx:
        payload.update(ctx)
    # request-first signature (required by current Starlette; the old (name, context) form was removed)
    return templates.TemplateResponse(request, template, payload)


def _reading_html():
    """Render the committed app/smoke/READING.md (honest reading) → HTML; explicit None if missing."""
    p = os.path.join(ROOT, "app", "smoke", "READING.md")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return _md.markdown(f.read(), extensions=["tables"])


# ── pages ──
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return _render(request, "landing.html", "home", views.overview())


@app.get("/chatbot", response_class=HTMLResponse)
def chatbot_page(request: Request):
    return _render(request, "chat.html", "chatbot",
                   {"config": CONFIG_LABEL, "reading_html": _reading_html()})


@app.get("/dashboard/ablation", response_class=HTMLResponse)
def page_ablation(request: Request):
    return _render(request, "dash_ablation.html", "ablation", views.ablation())


@app.get("/dashboard/rq5", response_class=HTMLResponse)
def page_rq5(request: Request):
    return _render(request, "dash_rq5.html", "rq5", views.rq5())


@app.get("/dashboard/risk", response_class=HTMLResponse)
def page_risk(request: Request):
    return _render(request, "dash_risk.html", "risk", views.risk())


@app.get("/dashboard/rq3", response_class=HTMLResponse)
def page_rq3(request: Request):
    return _render(request, "dash_rq3.html", "rq3", views.rq3())


@app.get("/dashboard/probes", response_class=HTMLResponse)
def page_probes(request: Request):
    return _render(request, "dash_probes.html", "probes", views.probes())


@app.get("/dashboard/img/{name}")
def dashboard_img(name: str):
    """Serve a committed artifact PNG by loader name; missing → explicit 404 error, never fabricated."""
    try:
        path = L.image_path(name)
    except L.MissingArtifact as e:
        return JSONResponse({"error": str(e)}, status_code=404)
    except KeyError:
        return JSONResponse({"error": f"unknown image artifact: {name}"}, status_code=404)
    return FileResponse(path)
