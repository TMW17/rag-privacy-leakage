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
_STATE = {"pipe": None, "history": []}            # single demo session


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
    _STATE["history"] += [{"role": "user", "content": req.message},
                          {"role": "assistant", "content": resp.response_text}]
    return {"response": resp.response_text, "audit": P.audit_view(p.audit_records[-1])}


@app.post("/reset")
def reset():
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
   <div id="audit">— send a message —</div></div>
</div>
<script>
const log=document.getElementById('log'),aud=document.getElementById('audit'),q=document.getElementById('q');
function add(t,c){const d=document.createElement('div');d.className='msg '+c;d.textContent=t;log.appendChild(d);log.scrollTop=log.scrollHeight;}
async function send(){const m=q.value.trim();if(!m)return;q.value='';add(m,'u');add('…','a');
 const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({message:m,profile:document.getElementById('prof').value})});
 const j=await r.json();log.lastChild.textContent=j.response;
 aud.innerHTML='<pre>'+JSON.stringify(j.audit,null,2)+'</pre>';}
async function reset(){await fetch('/reset',{method:'POST'});log.innerHTML='';aud.textContent='— reset —';}
</script></body></html>"""


@app.get("/", response_class=HTMLResponse)
def index():
    return HTML
