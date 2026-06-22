"""
server.py — FastAPI backend + minimal chat UI for the C01100 secure-RAG chatbot.

Run:  python3 -m uvicorn app.server:app --port 8000   (from the repo root)
Then open http://localhost:8000

Every turn passes through the C01100 pipeline (L2 redaction + L3 refusal, audit_log +
confidence_threshold). The response and the per-turn audit entry are returned to the UI. This is a
demonstration of the recommended config; it does not solve linkability (see the Sprint-3 report).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fastapi import FastAPI                       # noqa: E402
from fastapi.responses import HTMLResponse        # noqa: E402
from pydantic import BaseModel                    # noqa: E402

import pipeline as P                              # noqa: E402

app = FastAPI(title="Secure RAG Chatbot (C01100 = L2+L3)")
_STATE = {"pipe": None, "history": [],            # single demo session
          "log": []}                              # session history: every prompt + engine/judge result
                                                  # (the last entry, if not yet judged, is the /judge target)


def _pipe():
    if _STATE["pipe"] is None:
        p = P.build_pipeline(run_id="chatbot")
        p.begin_scenario("chat-session", 0, family="chat")
        _STATE["pipe"] = p
    return _STATE["pipe"]


class ChatReq(BaseModel):
    message: str
    profile: str = P.DEFAULT_PROFILE


@app.post("/chat")
def chat(req: ChatReq):
    p = _pipe()
    resp = p.query(req.message, P.profile(req.profile), _STATE["history"] or None)
    audit = P.audit_view(p.audit_records[-1])
    _STATE["history"] += [{"role": "user", "content": req.message},
                          {"role": "assistant", "content": resp.response_text}]
    _STATE["log"].append({                           # append to the session history (judge filled in by /judge)
        "n": len(_STATE["log"]) + 1, "ts": audit.get("timestamp"), "profile": req.profile,
        "prompt": req.message, "response": resp.response_text,
        "engine_verdict": audit.get("verdict"), "severity_S": audit.get("severity_S"),
        "retrieved_doc_ids": audit.get("retrieved_doc_ids"), "judge": None})
    return {"response": resp.response_text, "audit": audit}


@app.post("/judge")
def judge():
    """Second-pass Opus judge over the LAST turn's response (a real paid Opus call). Returned as a
    separate request so the answer + engine audit render immediately, then the judge verdict streams in.
    Lets the UI show ENGINE (κ=0.164 lower bound) and JUDGE (κ=0.827, human-validated) side by side.
    The target is the last log entry while it is still unjudged. In the normal flow the previous turn
    is already judged, so after /reset this reports 'no turn' until a fresh message arrives."""
    log = _STATE["log"]
    if not log or log[-1].get("judge") is not None:
        return {"available": False, "reason": "no turn to judge yet — send a message first"}
    last = log[-1]
    verdict = P.judge_response(last["response"], P.profile(last["profile"]))
    last["judge"] = verdict
    return verdict


def _eng_leak(t):
    return t.get("engine_verdict") not in (None, "no_leak")


def _judge_leak(t):
    return bool(t.get("judge") and t["judge"].get("leak_detected"))


def _history_summary(turns):
    """Aggregate counts for the history panel's chips + charts (computed server-side so the --live
    check can assert them). A 'disagreement' is any turn where the engine and the judge differ on
    whether it leaked — EITHER direction (engine-blind: engine no_leak + judge leak; or engine
    over-flag: engine leak + judge no_leak) — counted only once the judge has run."""
    eng = sum(1 for t in turns if _eng_leak(t))
    jud = sum(1 for t in turns if _judge_leak(t))
    dis = sum(1 for t in turns if t.get("judge") and _eng_leak(t) != _judge_leak(t))
    return {"total": len(turns), "engine_leaks": eng, "judge_leaks": jud, "disagreements": dis}


@app.get("/history")
def history():
    """All prompts + their engine/judge results for this server run (in-memory; survives /reset,
    cleared only by /history/clear)."""
    turns = _STATE["log"]
    return {"turns": turns, "summary": _history_summary(turns)}


@app.post("/history/clear")
def history_clear():
    _STATE["log"] = []
    return {"ok": True}


@app.post("/reset")
def reset():
    """Reset the CONVERSATION (context) but keep the history log — the audit trail of all prompts
    persists across resets; use /history/clear to wipe it. In the normal flow the kept log's last
    entry is already judged, so /judge reports 'no turn' until a fresh message arrives."""
    _STATE["pipe"] = None
    _STATE["history"] = []
    return {"ok": True}


@app.get("/health")
def health():
    return {"ok": True, "config": "C01100", "layers": list(P.C01100)}


HTML = """<!doctype html><html><head><meta charset="utf-8"><title>Secure RAG Chatbot — C01100</title>
<style>
 body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#f5f6f8;color:#1c2330}
 header{background:#1c2330;color:#fff;padding:12px 18px}
 header b{font-size:16px} header span{opacity:.7;font-size:12px;margin-left:8px}
 .wrap{max-width:1100px;margin:0 auto;display:grid;grid-template-columns:1.4fr 1fr;gap:14px;padding:14px}
 .panel{background:#fff;border:1px solid #e3e6ea;border-radius:10px;display:flex;flex-direction:column}
 #log{padding:14px;height:62vh;overflow:auto} .msg{margin:8px 0;padding:9px 12px;border-radius:10px;max-width:85%;white-space:pre-wrap;line-height:1.4}
 .u{background:#2563eb;color:#fff;margin-left:auto} .a{background:#eef1f5}
 .bar{display:flex;gap:8px;padding:10px;border-top:1px solid #e3e6ea}
 #q{flex:1;padding:9px;border:1px solid #cdd3da;border-radius:8px;font-size:14px}
 button{background:#2563eb;color:#fff;border:0;border-radius:8px;padding:9px 14px;cursor:pointer}
 select{padding:8px;border:1px solid #cdd3da;border-radius:8px}
 #audit{padding:14px;height:62vh;overflow:auto;font:12px/1.5 ui-monospace,Menlo,monospace}
 h3{margin:10px 14px 0;font-size:13px;color:#556} pre{background:#0f1626;color:#cfe;padding:10px;border-radius:8px;overflow:auto}
 .note{font-size:12px;color:#8a93a0;padding:0 14px 10px} .pill{display:inline-block;background:#e8f0fe;color:#1a56db;border-radius:10px;padding:1px 8px;font-size:11px}
</style></head><body>
<header><b>Secure RAG Chatbot</b><span>config C01100 (L2 retrieval-redaction + L3 refusal · audit_log + confidence_threshold ON) · SUT Claude Sonnet 4.6 · clean synthetic index</span></header>
<div class="wrap">
 <div class="panel">
   <div id="log"></div>
   <div class="bar">
     <select id="prof"><option>Internal</option><option>External</option><option>Admin</option></select>
     <input id="q" placeholder="Ask the assistant…" onkeydown="if(event.key==='Enter')send()">
     <button onclick="send()">Send</button><button onclick="reset()" style="background:#6b7280">Reset</button>
   </div>
   <div class="note">Demonstration of the recommended config — <b>not a certified system</b>; it does not solve cross-document linkability (Sprint-3 F2 finding stands).</div>
 </div>
 <div class="panel"><h3>Per-turn audit log <span class="pill">last turn</span></h3>
   <div class="note">timestamp · profile · layers fired · retrieved doc_ids · engine verdict · severity S · confidence gate</div>
   <div class="note" style="color:#b45309"><b>⚠ The audit verdict is the rule engine's view (κ=0.164, a lower bound).</b> It misses semantic / linkage leaks — e.g. surviving surnames, or age+role+performance re-association — so <b>"no_leak" is not a safety guarantee</b>. Linkability survives this config (see the Sprint-3 report).</div>
   <div id="audit">— send a message —</div>
   <h3>Second-pass judge <span class="pill">Opus 4.7 · κ=0.827</span></h3>
   <div class="note">the <b>human-validated</b> detector — catches the semantic / linkage leaks the engine misses. When it disagrees with the engine above, the judge (κ=0.827) is the one to trust, not the engine (κ=0.164).</div>
   <div id="judge">— judge runs after each turn —</div></div>
</div>
<script>
const log=document.getElementById('log'),aud=document.getElementById('audit'),jud=document.getElementById('judge'),q=document.getElementById('q');
function add(t,c){const d=document.createElement('div');d.className='msg '+c;d.textContent=t;log.appendChild(d);log.scrollTop=log.scrollHeight;}
function renderJudge(jv,engineVerdict){
 if(!jv||jv.available===false){jud.innerHTML='<pre>judge unavailable: '+((jv&&jv.reason)||'no verdict')+'</pre>';return;}
 const leak=jv.leak_detected===true;
 let h='<b style="color:'+(leak?'#b91c1c':'#334155')+'">judge verdict: '+(leak?'LEAK DETECTED':'no_leak')+'</b>'
      +' <span style="font-size:11px;color:#667">Opus 4.7 · prompt '+jv.prompt_version+' · validated κ=0.827</span>';
 if(leak&&engineVerdict==='no_leak'){h+='<div style="background:#fffbeb;border:1px solid #f59e0b;color:#92400e;padding:8px;border-radius:8px;margin:6px 0;font-weight:600">⚠ ENGINE–JUDGE DISAGREEMENT — the engine said no_leak, the judge caught a leak. This is the κ 0.164 vs 0.827 gap, live.</div>';}
 h+='<pre>'+JSON.stringify(jv,null,2)+'</pre>';jud.innerHTML=h;}
async function send(){const m=q.value.trim();if(!m)return;q.value='';add(m,'u');add('…','a');
 const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({message:m,profile:document.getElementById('prof').value})});
 const j=await r.json();log.lastChild.textContent=j.response;
 aud.innerHTML='<pre>'+JSON.stringify(j.audit,null,2)+'</pre>';
 jud.innerHTML='<pre>judge evaluating… (real Opus call, ~5–15s)</pre>';
 try{const jr=await fetch('/judge',{method:'POST'});const jv=await jr.json();renderJudge(jv,j.audit.verdict);}
 catch(e){jud.innerHTML='<pre>[judge error: '+e+']</pre>';}}
async function reset(){await fetch('/reset',{method:'POST'});log.innerHTML='';aud.textContent='— reset —';jud.textContent='— reset —';}
</script></body></html>"""


@app.get("/", response_class=HTMLResponse)
def index():
    return HTML
