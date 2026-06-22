"""
pipeline.py — shared factory for the C01100 secure-RAG chatbot (used by server.py and smoke.py).

Config = the RQ5-recommended knee: L2 (retrieval-time Presidio redaction, .venv-presidio subprocess,
fail-closed) + L3 (conversation-state refusal), with audit_log + confidence_threshold ON. SUT =
Claude Sonnet 4.6 (temp 0). Index = the clean (non-poisoned) synthetic collection. ACL is off
(l5_acl=False) — the synthetic corpus is uniformly sev>=3, so per-profile ACL has nothing to bite on
(see Sprint-3 report); provenance-only.

This is a DEMONSTRATION of the recommended config, not a certified system. It does NOT solve
cross-document linkability (the report's F2 finding stands).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.rag_system import RAGSystem
from scripts.phase3.defense_pipeline import DefensePipeline, DefenseConfig
from scripts.evaluation_engine import AttackerProfile

CLEAN_COLLECTION = "phase2_baseline_seed42"
PROFILES = {p.value: p for p in AttackerProfile}     # "Internal"/"External"/"Admin"/"ThirdParty"
DEFAULT_PROFILE = "Internal"

C01100 = dict(L2_retrieval_redaction=True, L3_conversation_refusal=True,
              audit_log=True, confidence_threshold=True)


def build_pipeline(run_id="chatbot"):
    rag = RAGSystem(CLEAN_COLLECTION, k=5)
    cfg = DefenseConfig(**C01100)
    return DefensePipeline(rag, cfg, run_id=run_id, l5_acl=False)


def profile(name):
    return PROFILES.get(name, AttackerProfile.INTERNAL)


# the per-turn audit fields surfaced to the UI / smoke output (subset of the pipeline's record)
AUDIT_FIELDS = ("timestamp", "profile", "active_layers", "layers_fired", "retrieved_doc_ids",
                "verdict", "severity_S", "source", "confidence_threshold", "response_modified")


def audit_view(rec):
    return {k: rec.get(k) for k in AUDIT_FIELDS}


# ── second-pass LLM-as-Judge (Opus 4.7, prompt v2) ────────────────────────────────────────────────
# The audit panel above shows the RULE ENGINE's verdict — a κ = 0.164 LOWER BOUND, blind to surname and
# cross-document linkage leaks. The judge here is the HUMAN-validated detector (κ = 0.827): it catches
# the semantic leaks the engine misses. Surfacing both side by side makes that gap visible live — it is
# the thesis finding, not a contradiction. Each judge call is a real paid Opus call; the judge never
# raises (LLMJudge returns a fallback verdict on any API / parse failure).
JUDGE_MODEL = "claude-opus-4-7"
JUDGE_PROMPT_VERSION = "v2"          # the prompt behind the 17.3% judged-ASR headline
_JUDGE = {"obj": None, "error": None}


def _judge():
    if _JUDGE["obj"] is None and _JUDGE["error"] is None:
        try:
            from scripts.llm_judge import LLMJudge
            _JUDGE["obj"] = LLMJudge(prompt_version=JUDGE_PROMPT_VERSION)
        except Exception as exc:                     # missing API key / prompt file → degrade, don't crash
            _JUDGE["error"] = f"{type(exc).__name__}: {exc}"
    return _JUDGE["obj"]


def judge_response(response_text, profile):
    """Run the Opus judge over a SUT response; return a JSON-serialisable verdict dict (never raises).

    `profile` must be an AttackerProfile enum member (use P.profile(name) to resolve a string).
    """
    j = _judge()
    if j is None:
        return {"available": False, "model": JUDGE_MODEL, "prompt_version": JUDGE_PROMPT_VERSION,
                "reason": _JUDGE["error"] or "judge unavailable"}
    v = j.judge(response_text, profile)
    return {"available": True, "model": JUDGE_MODEL, "prompt_version": JUDGE_PROMPT_VERSION,
            "leak_detected": v.leak_detected, "leak_type": v.leak_type,
            "disclosed_entities": v.disclosed_entities, "rationale": v.rationale,
            "latency_ms": v.latency_ms, "input_tokens": v.input_tokens, "output_tokens": v.output_tokens}
