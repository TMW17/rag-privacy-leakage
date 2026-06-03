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
