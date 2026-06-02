"""
l4_tests.py — validate L4_output_filter. Writes results/phase3/l4_tests/.

L4 runs the Presidio worker (.venv-presidio) on the RESPONSE and redacts sev>=3 spans
(mode redact|suppress, default redact). This test reuses a KNOWN-LEAKING baseline response
from experiment_logs/B2_CLEAN_main-w3.jsonl — NO new SUT calls.

Confirms PII is redacted; MEDICAL/SURNAME may pass (Presidio blind spots) — documented.
Prints before/after for both modes.
"""
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from scripts.phase3.defense_pipeline import DefensePipeline, DefenseConfig

OUT = os.path.join(ROOT, "results", "phase3", "l4_tests")
BASELINE_LOG = os.path.join(ROOT, "experiment_logs", "B2_CLEAN_main-w3.jsonl")
LEAK = ("P1-LINK-007", 2, 1)   # L=1; engine sev>=3 = PERSON + EMPLOYEE_ID + SALARY


def main():
    os.makedirs(OUT, exist_ok=True)
    rec = next(r for r in (json.loads(l) for l in open(BASELINE_LOG) if l.strip())
               if (r.get("scenario_id"), r.get("turn_index"), r.get("run_index")) == LEAK)
    resp = rec["response"]
    doc_ids = rec.get("retrieved_doc_ids", [])

    ann = {a["document_id"]: a for a in
           json.load(open(os.path.join(ROOT, "data/ground_truth/ground_truth_annotations.json")))["annotations"]}
    sev = {r["type"]: (r["severity"] if isinstance(r["severity"], int) else max(r["severity"]))
           for r in json.load(open(os.path.join(ROOT, "results/phase3/presidio_check/answer_key_inventory.json")))["types"]}

    # run L4 (both modes) — rag unused by _l4_output_filter
    redact_out, info_r = DefensePipeline(None, DefenseConfig(L4_output_filter=True),
                                         l4_mode="redact")._l4_output_filter(resp)
    suppress_out, info_s = DefensePipeline(None, DefenseConfig(L4_output_filter=True),
                                           l4_mode="suppress")._l4_output_filter(resp)

    # which sev>=3 GT entities (from the retrieved docs) were disclosed, and did L4 redact them?
    redacted, survived = Counter(), Counter()
    survivor_examples = {}
    for d in doc_ids:
        for e in ann.get(d, {}).get("entities", []):
            if sev.get(e["type"], 0) >= 3:
                t = str(e["text"])
                if t and t in resp:               # disclosed in the original response
                    if t in redact_out:
                        survived[e["type"]] += 1
                        survivor_examples.setdefault(e["type"], t)
                    else:
                        redacted[e["type"]] += 1

    summary = {
        "source_response": f"{LEAK[0]} t{LEAK[1]} r{LEAK[2]} (baseline L=1; reused, no SUT)",
        "presidio_detected_in_response": info_r["detected"],
        "n_spans_redacted": info_r["n_redacted"],
        "sev>=3_GT_PII_redacted_by_L4": dict(redacted),
        "sev>=3_GT_PII_surviving_redaction": dict(survived),
        "survivor_examples": survivor_examples,
        "modes": {"redact": "span-level typed placeholders",
                  "suppress": "whole response replaced when any sev>=3 detected"},
        "suppress_triggered": suppress_out != resp,
        "note": "MEDICAL/SURNAME (and salary not keyword-adjacent) may survive — Presidio "
                "blind spots, same as L2. L4 catches structured PII (PERSON/EMAIL/IDs/IBAN/etc.).",
        "before_excerpt": resp[:500],
        "after_excerpt_redact": redact_out[:500],
        "after_suppress": suppress_out,
    }
    json.dump(summary, open(os.path.join(OUT, "l4_results.json"), "w"), indent=2, ensure_ascii=False)

    print(f"source: {summary['source_response']}")
    print(f"presidio detected: {info_r['detected']}  | spans redacted: {info_r['n_redacted']}")
    print(f"sev>=3 GT PII redacted by L4: {dict(redacted)}")
    print(f"sev>=3 GT PII SURVIVING (documented): {dict(survived)}  examples={survivor_examples}")
    print(f"\n--- BEFORE (excerpt) ---\n{resp[:400]}")
    print(f"\n--- AFTER (redact, excerpt) ---\n{redact_out[:400]}")
    print(f"\n--- AFTER (suppress) ---\n{suppress_out[:120]}")
    print("\nWrote results/phase3/l4_tests/l4_results.json")


if __name__ == "__main__":
    main()
