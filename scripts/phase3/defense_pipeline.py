"""
defense_pipeline.py — toggleable defense pipeline wrapping the Phase 2 RAG flow.

Sprint-0 status: EVERY layer is a LOGGED no-op STUB. With ``DefenseConfig`` all-False
the pipeline returns ``RAGSystem.query()``'s ``RAGResponse`` VERBATIM, so it reproduces
the Phase 2 baseline exactly (GUARD: F1 engine-inclusive ASR = 0.7407 ± 0.05).

Pipeline order (each step a no-op when its toggle is False):

    query -> [L1 input filter] -> retrieve(k=5) -> [L5 provenance/ACL] ->
    [context_minimization] -> [L2 retrieval redaction] -> LLM(SUT) with
    [L3 conversation-state refusal] -> [L4 output filter] ->
    [confidence_threshold] -> response          ; [audit_log] records every step.

ARCHITECTURE (read before extending in Sprint 1)
------------------------------------------------
``RAGSystem.query()`` is FROZEN Phase-2 code that performs retrieve + prompt + SUT
atomically.  In this stub phase the pipeline routes the SUT interaction through
``rag.query()`` UNCHANGED — this is what guarantees baseline reproduction (there is no
wrapper code path that could diverge).  Around that atomic core:

  * L1_input_filter      — real seam on the *inbound query string* (no-op stub).
  * L4_output_filter     — real seam on the *outbound response string* (no-op stub).
  * confidence_threshold — real seam on the *outbound response string* (no-op stub).

The MID-FLOW layers (L5_provenance_check, context_minimization, L2_retrieval_redaction,
L3_conversation_refusal) act on retrieved context / message state BEFORE the SUT call.
Because the atomic ``rag.query()`` has *already* run the SUT on the original context,
these layers CANNOT affect output in this stub phase.  When toggled True here they log
honestly that they are inert and that the real effect requires the Sprint-1
retrieve()/generate() split (see SPRINT1_CONTRACT) — they do NOT pretend to have acted.

PRESIDIO BOUNDARY (L2 / L4)
---------------------------
L2/L4 will redact PII with Presidio, which only imports under ``.venv-presidio`` (Py 3.11);
spaCy/Presidio CANNOT import under this Python 3.14 process.  This module therefore imports
NOTHING from presidio/spaCy.  The real redaction is a SUBPROCESS boundary defined in
``scripts/phase3/presidio_bridge.py`` (invoked via ``.venv-presidio/bin/python``).

SPRINT1_CONTRACT
----------------
To activate mid-flow layers without modifying frozen ``rag_system.py``, Sprint 1 will add a
decomposed path that reuses the same retrieval (embed + Chroma top-k + dedup) and the same
generation (system-prompt template + ``messages`` + Sonnet 4.6 @ temp=0/max_tokens=1024),
inserting L5/context_minimization/L2 between them and L3 into message assembly.  All-False
must still match baseline; the decomposed path is validated by re-running this GUARD.
"""
import json
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, asdict, field, replace, fields

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from scripts.rag_system import (  # noqa: E402
    RAGSystem, RAGResponse, _SYSTEM_PROMPT_TEMPLATE, _LLM_MODEL,
)
# 3.14-safe: presidio_bridge runs Presidio in a .venv-presidio SUBPROCESS (no spaCy here).
from scripts.phase3.presidio_bridge import redact as _presidio_redact  # noqa: E402
# L3 reuses the frozen evaluation engine (real-PII, per-document attribution; catches
# MEDICAL via Keyword+Context; FP-safe). Engine import pulls in NO spaCy/Presidio.
from scripts.evaluation_engine import check_response_for_leakage  # noqa: E402
# L1 input rail — regex+classifier FALLBACK (NeMo Guardrails unsupported on Py 3.14). Pure stdlib.
from scripts.phase3.l1_filter import classify_input as _l1_classify, ENGINE as _L1_ENGINE  # noqa: E402


# =============================================================================
# DefenseConfig — all toggles default False == Phase 2 baseline
# =============================================================================
@dataclass
class DefenseConfig:
    L1_input_filter: bool = False
    L2_retrieval_redaction: bool = False
    L3_conversation_refusal: bool = False
    L4_output_filter: bool = False
    L5_provenance_check: bool = False
    context_minimization: bool = False
    confidence_threshold: bool = False
    audit_log: bool = False

    def active_layers(self):
        return [f.name for f in fields(self) if getattr(self, f.name)]

    def is_baseline(self):
        # audit_log is a logging toggle, not a transform — baseline = no transform layer on
        transforms = [f.name for f in fields(self) if f.name != "audit_log"]
        return not any(getattr(self, n) for n in transforms)


# Mid-flow layers that act before the SUT (cannot affect the atomic core in Sprint 0)
_MID_FLOW = ("L5_provenance_check", "context_minimization",
             "L2_retrieval_redaction", "L3_conversation_refusal")
_STUB_NOOP = "STUB no-op (passthrough)"
_STUB_MIDFLOW = ("STUB no-op — INERT in Sprint 0; real effect requires the Sprint-1 "
                 "retrieve()/generate() split (SUT already ran on original context)")

# ── L5 provenance + role-based ACL references ────────────────────────────────
_CLEARANCE = {"Internal": 2, "External": 0, "Admin": 3}   # P1 / P2 / P3 clearance levels
_L5_REFS = None


def _load_l5_refs():
    """Return (trusted_allow_list:set of 155 doc_ids, doc_id->max_severity). Cached."""
    global _L5_REFS
    if _L5_REFS is None:
        idx = json.load(open(os.path.join(ROOT, "data/ground_truth/ground_truth_index.json")))
        ann = json.load(open(os.path.join(ROOT, "data/ground_truth/ground_truth_annotations.json")))
        allow = set(idx.keys())
        maxsev = {a["document_id"]: int(a.get("max_severity", 0) or 0)
                  for a in ann["annotations"]}
        _L5_REFS = (allow, maxsev)
    return _L5_REFS


def l5_decision(doc_id, profile_value, acl=True):
    """Per-doc L5 decision: 'quarantine' (not in the trusted 155 allow-list),
    'acl_block' (doc max_severity > profile clearance), or 'pass'.
    profile_value is 'Internal' | 'External' | 'Admin'."""
    allow, maxsev = _load_l5_refs()
    if doc_id not in allow:
        return "quarantine"
    if acl and maxsev.get(doc_id, 99) > _CLEARANCE.get(profile_value, 0):
        return "acl_block"
    return "pass"

_L1_BLOCK_TEXT = (
    "I can't process that request. It was flagged by the input filter as a likely prompt-"
    "injection or jailbreak attempt and was blocked before reaching the system."
)

_L4_SUPPRESS_TEXT = (
    "I'm sorry, but I can't share that response. The output filter detected personal "
    "information in the drafted answer and suppressed it. Please contact HR through an "
    "authorized channel for records you're entitled to."
)

_L3_REFUSAL_TEXT = (
    "I'm sorry, but I can't provide that. Combining an individual's identity with their "
    "sensitive attributes (e.g. salary, medical, or other protected details) would disclose "
    "personal information beyond what this interface is authorized to share. Please contact "
    "HR through the appropriate authorized channel."
)


@dataclass
class L3Config:
    """TUNABLE conversation-refusal thresholds (engine-based, per-document person).

    Default: refuse if (NAME + a sev>=4 *attribute* in one turn) OR (>=2 distinct sev>=3
    disclosures accumulated about one person across the conversation). The NAME itself is a
    sev>=3 disclosure, so 'name + salary(sev3)' = 2 distinct sev>=3 -> rule_b fires.
    """
    rule_a_name_plus_sev4: bool = True
    rule_b_cumulative_sev3: int = 2
    name_types: tuple = ("PERSON", "SURNAME_TITLE")


# =============================================================================
# DefensePipeline
# =============================================================================
class DefensePipeline:
    """
    Wraps a RAGSystem with a toggleable defense pipeline.

    Use ``pipeline.query`` as the ``query_fn`` for
    ``campaign_runner.run_single_scenario`` — its scoring is unchanged.
    Call ``begin_scenario(scenario_id, run_index)`` before each scenario so the
    pipeline's own per-turn audit records are joinable to the runner's records.
    """

    def __init__(self, rag: RAGSystem, config: DefenseConfig, run_id: str = "defense",
                 l3_config: "L3Config" = None, l4_mode: str = "redact", l5_acl: bool = True):
        self.rag = rag
        self.cfg = config
        self.run_id = run_id
        self.l3cfg = l3_config or L3Config()
        if l4_mode not in ("redact", "suppress"):
            raise ValueError("l4_mode must be 'redact' or 'suppress'")
        self.l4_mode = l4_mode
        self.l5_acl = l5_acl   # role-based ACL within L5 (separable; provenance always on when L5 on)
        self.audit_records = []          # pipeline's OWN per-turn log (separate from runner)
        self._scenario_id = None
        self._run_index = 0
        self._turn = 0
        self._l3_state = defaultdict(set)   # per-conversation: doc_id -> {sev>=3 entity_types}
        self.last_l1 = None
        self.last_l3 = None
        self.last_l2 = None
        self.last_l4 = None
        self.last_l5 = None

    def begin_scenario(self, scenario_id: str, run_index: int = 0):
        self._scenario_id = scenario_id
        self._run_index = run_index
        self._turn = 0
        self._l3_state = defaultdict(set)   # sensitivity state is per-conversation

    # ── query_fn compatible with run_single_scenario ─────────────────────────
    def query(self, user_query, profile, conversation_history=None) -> RAGResponse:
        steps = []

        def log(layer, fired, action):
            steps.append({"layer": layer, "fired": fired, "action": action})

        # ── L1 input rail (BLOCKING gate on inbound query) ───────────────────
        q = user_query
        l1_blocked, l1_signals = False, []
        if self.cfg.L1_input_filter:
            l1_blocked, l1_signals = _l1_classify(user_query)
            self.last_l1 = {"blocked": l1_blocked, "engine": _L1_ENGINE, "signals": l1_signals}
            cats = [s["category"] for s in l1_signals]
            log("L1_input_filter", True,
                f"BLOCKED {cats}" if l1_blocked else f"allowed ({_L1_ENGINE})")
        else:
            log("L1_input_filter", False, "skip(disabled)")

        # ── retrieve(k) + mid-flow layers + SUT ──────────────────────────────
        if l1_blocked:
            # short-circuit: blocked attacks never reach retrieval or the SUT (no API call)
            for layer in _MID_FLOW:
                log(layer, False, "skip(L1-blocked)")
            log("LLM_SUT", False, "skip(L1-blocked)")
            resp = RAGResponse(_L1_BLOCK_TEXT, [], [], 0, 0, 0, {})
        elif not any(getattr(self.cfg, n) for n in _MID_FLOW):
            # No mid-flow layer active → atomic frozen rag.query() == baseline.
            for layer in _MID_FLOW:
                log(layer, False, "skip(disabled)")
            resp = self.rag.query(
                user_query=q, profile=profile, conversation_history=conversation_history,
            )
            log(f"retrieve_k={self.rag.k}", True, "frozen RAGSystem.query() (atomic)")
            log("LLM_SUT", True, "claude-sonnet-4-6 temp=0 max_tokens=1024 (frozen)")
        else:
            # Decomposed path: retrieve -> [L5] -> [ctx-min] -> [L2 redact] -> generate
            resp = self._decomposed_query(q, profile, conversation_history, log)

        # ── L4 output filter (REAL; Presidio redaction of the RESPONSE) + confidence ─
        text = resp.response_text
        if self.cfg.L4_output_filter:
            text, l4info = self._l4_output_filter(text)
            self.last_l4 = l4info
            log("L4_output_filter", True,
                f"{l4info['mode']}: {l4info['n_redacted']} sev>=3 spans in response "
                f"({sorted(l4info['detected'])})")
        else:
            log("L4_output_filter", False, "skip(disabled)")

        if self.cfg.confidence_threshold:
            text = self._confidence_threshold(text)
            log("confidence_threshold", True, _STUB_NOOP)
        else:
            log("confidence_threshold", False, "skip(disabled)")

        # VERBATIM passthrough when text unchanged → byte-identical baseline
        out = resp if text == resp.response_text else replace(resp, response_text=text)

        # ── pipeline's own per-turn record (does NOT touch run_single_scenario) ─
        rec = {
            "scenario_id": self._scenario_id,
            "run_id": self.run_id,
            "run_index": self._run_index,
            "turn_index": self._turn,
            "config": asdict(self.cfg),
            "active_layers": self.cfg.active_layers(),
            "is_baseline": self.cfg.is_baseline(),
            "retrieved_doc_ids": resp.retrieved_doc_ids,
            "layers_fired": [s["layer"] for s in steps if s["fired"]],
            "response_modified": text != resp.response_text,
            # detailed step-by-step trail only when the audit_log toggle is on
            "audit_trail": steps if self.cfg.audit_log else None,
        }
        self.audit_records.append(rec)
        self._turn += 1
        return out

    # ── decomposed retrieve/generate split (active when a mid-flow layer is on) ─
    def _retrieve(self, user_query):
        """Mirror RAGSystem.query retrieval exactly (reuse its embedder + collection)."""
        qv = self.rag._embedder.encode([user_query])[0].tolist()
        cr = self.rag._collection.query(
            query_embeddings=[qv], n_results=self.rag.k,
            include=["documents", "metadatas", "distances"],
        )
        chunks = list(cr["documents"][0])
        chunk_doc_ids = [m.get("doc_id", "") for m in cr["metadatas"][0]]
        seen, doc_ids = set(), []
        for d in chunk_doc_ids:
            if d and d not in seen:
                seen.add(d)
                doc_ids.append(d)
        return chunks, chunk_doc_ids, doc_ids

    def _generate(self, user_query, chunks, conversation_history):
        """Mirror RAGSystem.query generation exactly (reuse its client + prompt + model)."""
        t0 = time.perf_counter()
        context = "\n\n---\n\n".join(chunks)
        system = _SYSTEM_PROMPT_TEMPLATE.format(context=context, question=user_query)
        messages = list(conversation_history or []) + [{"role": "user", "content": user_query}]
        r = self.rag._anthropic.messages.create(
            model=_LLM_MODEL, temperature=0, max_tokens=1024, system=system, messages=messages,
        )
        ms = int((time.perf_counter() - t0) * 1000)
        text = next((b.text for b in r.content if hasattr(b, "text")), "")
        return RAGResponse(text, [], chunks, ms,
                           r.usage.input_tokens, r.usage.output_tokens, r.model_dump())

    def _l5_filter(self, chunks, chunk_doc_ids, profile):
        """Drop chunks whose doc is not in the trusted 155 allow-list (provenance
        quarantine) and — if self.l5_acl — whose doc max_severity exceeds the profile's
        clearance (role-based ACL). Returns (kept_chunks, kept_doc_ids, audit_info)."""
        allow, maxsev = _load_l5_refs()
        clearance = _CLEARANCE.get(getattr(profile, "value", profile), 0)
        kept_chunks, kept_ids, quarantined, acl_blocked = [], [], [], []
        for ch, d in zip(chunks, chunk_doc_ids):
            if d not in allow:
                quarantined.append(d)
            elif self.l5_acl and maxsev.get(d, 99) > clearance:
                acl_blocked.append(d)
            else:
                kept_chunks.append(ch)
                kept_ids.append(d)
        seen, doc_ids = set(), []
        for d in kept_ids:
            if d and d not in seen:
                seen.add(d)
                doc_ids.append(d)
        info = {"quarantined": sorted(set(quarantined)), "acl_blocked": sorted(set(acl_blocked)),
                "clearance": clearance, "acl_on": self.l5_acl, "kept_doc_ids": doc_ids}
        return kept_chunks, doc_ids, info

    def _decomposed_query(self, q, profile, conversation_history, log):
        chunks, chunk_doc_ids, doc_ids = self._retrieve(q)
        log(f"retrieve_k={self.rag.k}", True,
            "decomposed retrieval (reuses RAGSystem embedder+collection)")
        # L5 provenance quarantine (+ optional role-based ACL) — REAL, before context build
        if self.cfg.L5_provenance_check:
            chunks, doc_ids, l5info = self._l5_filter(chunks, chunk_doc_ids, profile)
            self.last_l5 = l5info
            log("L5_provenance_check", True,
                f"quarantined={l5info['quarantined']} acl_blocked={l5info['acl_blocked']} "
                f"(acl={'on' if self.l5_acl else 'off'}, clearance={l5info['clearance']}, "
                f"kept={len(doc_ids)})")
        else:
            log("L5_provenance_check", False, "skip(disabled)")
        if self.cfg.context_minimization:
            log("context_minimization", True, _STUB_MIDFLOW)
        else:
            log("context_minimization", False, "skip(disabled)")
        # L2 retrieval redaction — REAL (Presidio via .venv-presidio subprocess)
        if self.cfg.L2_retrieval_redaction:
            res = _presidio_redact(chunks, sev_threshold=3)
            chunks = res["redacted"]
            self.last_l2 = res
            n_red = sum(s["n_redacted"] for s in res["stats"])
            log("L2_retrieval_redaction", True,
                f"redacted {n_red} sev>=3 spans across {len(chunks)} chunks (.venv-presidio)")
        else:
            log("L2_retrieval_redaction", False, "skip(disabled)")
        gen = self._generate(q, chunks, conversation_history)
        log("LLM_SUT", True, "claude-sonnet-4-6 temp=0 max_tokens=1024 (decomposed generate)")
        gen = replace(gen, retrieved_doc_ids=doc_ids)

        # ── L3 conversation-state refusal (REAL; engine-based, per-document person) ──
        if self.cfg.L3_conversation_refusal:
            refuse, reason = self._l3_gate(gen.response_text, doc_ids, profile, q)
            self.last_l3 = {"refused": refuse, "reason": reason}
            if refuse:
                gen = replace(gen, response_text=_L3_REFUSAL_TEXT)
                log("L3_conversation_refusal", True,
                    f"REFUSED — {reason['rule']} on {reason['doc_id']} types={reason['types']}")
            else:
                log("L3_conversation_refusal", True, "evaluated; under threshold (no refusal)")
        else:
            log("L3_conversation_refusal", False, "skip(disabled)")
        return gen

    def _l3_gate(self, response_text, doc_ids, profile, query):
        """Engine-based conversation-state gate (real-PII, per-document attribution).

        Updates the per-conversation sensitivity state and returns (refuse, reason).
        rule_a: a NAME (PERSON/SURNAME) + a sev>=4 NON-name attribute in THIS turn.
        rule_b: >= rule_b_cumulative_sev3 distinct sev>=3 entity types accumulated about
                one document across the conversation (the NAME itself counts as one).
        """
        res = check_response_for_leakage(response_text=response_text, document_ids=doc_ids,
                                         profile=profile, query=query)
        per_doc = defaultdict(lambda: {"name": False, "sev4_attr": False, "sev3": set()})
        for e in (res.events or []):
            d = e.get("document_id")
            et = e.get("entity_type")
            sev = e.get("severity", 0)
            if sev >= 3:
                per_doc[d]["sev3"].add(et)
            if et in self.l3cfg.name_types:
                per_doc[d]["name"] = True
            elif sev >= 4:
                per_doc[d]["sev4_attr"] = True
        for d, info in per_doc.items():          # accumulate ALL docs' state first
            self._l3_state[d] |= info["sev3"]
        for d, info in per_doc.items():           # then evaluate thresholds
            if self.l3cfg.rule_a_name_plus_sev4 and info["name"] and info["sev4_attr"]:
                return True, {"rule": "A_name+sev4_attr", "doc_id": d,
                              "types": sorted(info["sev3"])}
            if len(self._l3_state[d]) >= self.l3cfg.rule_b_cumulative_sev3:
                return True, {"rule": f"B_cumulative>={self.l3cfg.rule_b_cumulative_sev3}",
                              "doc_id": d, "types": sorted(self._l3_state[d])}
        return False, None

    # ── layer stubs (HONEST no-ops; L4 real logic = a later sprint) ──────────
    def _l4_output_filter(self, text):
        """Redact sev>=3 PII in the RESPONSE via the Presidio worker (.venv-presidio subprocess).

        mode 'redact' (default): replace each sev>=3 span with a typed placeholder.
        mode 'suppress': if ANY sev>=3 PII is detected, replace the whole response.
        Returns (filtered_text, info). MEDICAL/SURNAME may pass (Presidio blind spots).
        """
        if not text.strip():
            return text, {"mode": self.l4_mode, "n_redacted": 0, "detected": {}}
        res = _presidio_redact([text], sev_threshold=3)
        stats = res["stats"][0]
        info = {"mode": self.l4_mode, "n_redacted": stats["n_redacted"],
                "detected": stats["detected"]}
        if self.l4_mode == "suppress":
            return (_L4_SUPPRESS_TEXT if stats["n_redacted"] > 0 else text), info
        return res["redacted"][0], info

    def _confidence_threshold(self, text):
        # Sprint 1: gate/redact low-confidence disclosures. No-op now.
        return text


def make_query_fn(rag: RAGSystem, config: DefenseConfig, run_id: str = "defense"):
    """Convenience: return (pipeline, pipeline.query) for run_single_scenario."""
    p = DefensePipeline(rag, config, run_id)
    return p, p.query
