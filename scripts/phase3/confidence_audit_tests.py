"""
confidence_audit_tests.py — validate confidence_threshold + audit_log (Task 1.7).
Writes results/phase3/audit/. NO new SUT calls — a FakeRAG replays already-logged Phase-2
responses from experiment_logs/B2_CLEAN_main-w3.jsonl.

confidence_threshold: response-level circuit-breaker on the engine leak-severity S
(Σ s(e)·w(e)); S > conf_threshold → suppress (replace) or flag. audit_log: structured
per-turn record (timestamp, profile, family, config, layers_fired, retrieved_doc_ids,
verdict, severity_S, source) appended to results/phase3/audit/<run_id>.jsonl.

5 turns are picked spanning the S range (0 → max). With conf_threshold=10.0 the high-S
turns are suppressed. The engine recompute is cross-checked against the logged L/S, and
the all-False GUARD (byte-identical passthrough, no engine call) is re-verified.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from scripts.rag_system import RAGResponse
from scripts.evaluation_engine import AttackerProfile
from scripts.phase3.defense_pipeline import DefensePipeline, DefenseConfig, _AUDIT_DIR

LOG = os.path.join(ROOT, "experiment_logs", "B2_CLEAN_main-w3.jsonl")
RUN_ID = "conf-audit-test"
CONF_THRESHOLD = 10.0
REQUIRED_FIELDS = ["timestamp", "profile", "family", "config", "layers_fired",
                   "retrieved_doc_ids", "verdict", "severity_S", "source"]
_PROF = {p.value: p for p in AttackerProfile}


class FakeRAG:
    """Replays a logged Phase-2 response verbatim — NO SUT call."""
    def __init__(self, k=5):
        self.k = k
        self._resp = None

    def set(self, response_text, doc_ids):
        self._resp = RAGResponse(response_text, list(doc_ids), [], 0, 0, 0, {})

    def query(self, user_query, profile, conversation_history=None):
        return self._resp


def pick_turns(n=5):
    """Dedup logged turns (with retrieved_doc_ids); pick n spanning distinct S values."""
    seen = {}
    for r in (json.loads(l) for l in open(LOG) if l.strip()):
        if r.get("retrieved_doc_ids"):
            seen[(r["scenario_id"], r["turn_index"], r["run_index"])] = r
    by_s = {}
    for r in seen.values():
        by_s.setdefault(r.get("S", 0.0), r)        # one representative per distinct S
    distinct = sorted(by_s)
    idx = sorted({round(i * (len(distinct) - 1) / (n - 1)) for i in range(n)})
    return [by_s[distinct[i]] for i in idx]


def guard_check():
    """All-False config → byte-identical passthrough + NO engine verdict computed."""
    fake = FakeRAG()
    fake.set("Finance has 12 employees and is located in Building A.", ["hr_file_001"])
    pipe = DefensePipeline(fake, DefenseConfig(), run_id="guard-noop")
    pipe.begin_scenario("guard", 0, family="benign")
    out = pipe.query("How many in Finance?", AttackerProfile.INTERNAL, None)
    rec = pipe.audit_records[-1]
    return {"byte_identical": out.response_text == fake._resp.response_text,
            "engine_not_called": rec["verdict"] is None,
            "is_baseline": rec["is_baseline"]}


def main():
    os.makedirs(_AUDIT_DIR, exist_ok=True)
    audit_file = os.path.join(_AUDIT_DIR, f"{RUN_ID}.jsonl")
    if os.path.exists(audit_file):
        os.remove(audit_file)          # clean: pipeline appends per turn

    turns = pick_turns(5)
    fake = FakeRAG()
    pipe = DefensePipeline(fake, DefenseConfig(confidence_threshold=True, audit_log=True),
                           run_id=RUN_ID, conf_threshold=CONF_THRESHOLD, conf_mode="suppress")

    rows = []
    for t in turns:
        prof = _PROF[t["attacker_profile"]]
        fake.set(t["response"], t["retrieved_doc_ids"])
        pipe.begin_scenario(t["scenario_id"], t["run_index"], family=t.get("attack_family"))
        out = pipe.query(t["query"], prof, None)
        rec = pipe.audit_records[-1]
        ct = rec["confidence_threshold"]
        rows.append({
            "scenario_id": t["scenario_id"], "family": t.get("attack_family"),
            "profile": prof.value,
            "logged_L": t.get("L"), "logged_S": t.get("S"),
            "audit_verdict": rec["verdict"], "audit_severity_S": rec["severity_S"],
            "engine_matches_log": (int(rec["verdict"] == "leak") == int(bool(t.get("L")))
                                   and abs((rec["severity_S"] or 0) - (t.get("S") or 0)) < 1e-6),
            "conf_action": ct["action"], "suppressed": rec["response_modified"],
            "n_source_entities": len(rec["source"] or []),
            "response_head": out.response_text[:70],
        })

    # ── reload what the pipeline wrote to disk ──
    written = [json.loads(l) for l in open(audit_file) if l.strip()]
    fields_ok = all(all(k in r for k in REQUIRED_FIELDS) for r in written)
    n_suppressed = sum(r["suppressed"] for r in rows)
    n_consistent = sum(r["engine_matches_log"] for r in rows)
    guard = guard_check()

    suppressed_row = next((r for r in rows if r["suppressed"]), None)
    suppressed_rec = next((r for r in written
                           if r["scenario_id"] == suppressed_row["scenario_id"]), None) if suppressed_row else None

    PASS = (len(written) == 5 and fields_ok and n_suppressed >= 1 and n_consistent == 5
            and all(guard.values()))

    summary = {
        "run_id": RUN_ID, "conf_threshold": CONF_THRESHOLD, "conf_mode": "suppress",
        "source_log": "B2_CLEAN_main-w3.jsonl (reused; NO new SUT calls)",
        "confidence_metric": "leak_severity_S = Σ s(e)·w(e) (engine)",
        "turns": rows,
        "n_turns": len(rows), "n_suppressed": n_suppressed, "n_engine_consistent_with_log": n_consistent,
        "audit_file": os.path.relpath(audit_file, ROOT),
        "audit_records_written": len(written),
        "required_fields": REQUIRED_FIELDS, "all_required_fields_present": fields_ok,
        "guard_all_false_baseline": guard,
        "example_suppressed_audit_record": suppressed_rec,
        "checks": {
            "audit_5_records_with_all_fields": len(written) == 5 and fields_ok,
            "at_least_one_suppressed": n_suppressed >= 1,
            "engine_recompute_matches_logged_L_S": n_consistent == 5,
            "guard_all_false_byte_identical_no_engine": all(guard.values()),
        },
        "PASS": PASS,
    }
    json.dump(summary, open(os.path.join(_AUDIT_DIR, "confidence_audit_results.json"), "w"),
              indent=2, ensure_ascii=False)

    print(f"confidence_threshold S>{CONF_THRESHOLD} → suppress | audit -> {summary['audit_file']}")
    print(f"{'scenario':14} {'fam':6} {'prof':9} {'logL':4} {'logS':6} {'verdict':8} {'S':6} {'match':5} action")
    for r in rows:
        print(f"{r['scenario_id']:14} {(r['family'] or '')[:6]:6} {r['profile']:9} "
              f"{str(r['logged_L']):4} {str(r['logged_S']):6} {str(r['audit_verdict']):8} "
              f"{str(r['audit_severity_S']):6} {str(r['engine_matches_log']):5} {r['conf_action']}")
    print(f"\nsuppressed={n_suppressed}/5 | engine==log {n_consistent}/5 | "
          f"audit fields ok={fields_ok} | GUARD={guard}")
    if suppressed_rec:
        print(f"\n--- ONE SUPPRESSED TURN ({suppressed_rec['scenario_id']}) audit record ---")
        print(f"  verdict={suppressed_rec['verdict']} severity_S={suppressed_rec['severity_S']} "
              f"family={suppressed_rec['family']} profile={suppressed_rec['profile']}")
        print(f"  source(leaked entities)={suppressed_rec['source']}")
        print(f"  confidence_threshold={suppressed_rec['confidence_threshold']}")
        print(f"  layers_fired={suppressed_rec['layers_fired']}")
    print(f"\nPASS={PASS}")
    print("Wrote results/phase3/audit/confidence_audit_results.json")


if __name__ == "__main__":
    main()
