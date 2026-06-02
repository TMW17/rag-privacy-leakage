"""
presidio_worker.py — L2 retrieval-redaction worker. Runs under .venv-presidio (Py 3.11).

Reads JSON  {"texts": [str,...], "sev_threshold": int (default 3)}  from stdin.
Redacts every detected entity whose taxonomy severity >= threshold with a TYPED
placeholder (Presidio AnalyzerEngine + the Task-0.1 bin_a recognizers + AnonymizerEngine).
Writes JSON  {"redacted": [str,...], "stats": [...], ...}  to stdout.

Invoked as a subprocess by scripts/phase3/presidio_bridge.py (Python 3.14 side). This is
the ONLY place spaCy/Presidio are imported. One process per redact() call (the bridge
batches all chunks of a query into a single call to amortize AnalyzerEngine startup).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from scripts.phase3.recognizers import build_custom_recognizers

DEFAULT_THRESHOLD = 3

# Severity keyed on the labels the bin_a analyzer ACTUALLY emits (custom + firing defaults).
# Source: Task-0.1 taxonomy severities — NOT the stale inventory.presidio_label column
# (which shows None for the sev-5 secrets, pre-bin_a). Anything not listed is fail-closed.
LABEL_SEVERITY = {
    # bin_a custom recognizers
    "NNI_DZ": 5, "EMPLOYEE_ID": 3, "HEALTH_RECORD_ID": 4, "IBAN_DZ": 4,
    "API_KEY": 5, "JWT_TOKEN": 5, "PASSWORD_HASH": 5, "PRIVATE_KEY": 5,
    "DB_CONN_STRING": 5, "FILE_PATH": 3, "CROSS_REFERENCE": 3, "PHONE_DZ": 4,
    "SALARY": 3,
    # Presidio default labels that fire on this corpus
    "PERSON": 4, "EMAIL_ADDRESS": 4, "PHONE_NUMBER": 4, "IBAN_CODE": 4,
    "IP_ADDRESS": 4, "LOCATION": 4, "DATE_TIME": 4, "MEDICAL_LICENSE": 3,
}
FAILCLOSED_SEV = 99   # unknown label -> treat as high severity, redact (never leak silently)


def build_analyzer():
    eng = AnalyzerEngine()
    for rec in build_custom_recognizers("bin_a"):
        eng.registry.add_recognizer(rec)
    return eng


def main():
    payload = json.load(sys.stdin)
    texts = payload.get("texts", [])
    threshold = int(payload.get("sev_threshold", DEFAULT_THRESHOLD))

    analyzer = build_analyzer()
    anonymizer = AnonymizerEngine()

    redacted, stats = [], []
    unknown = set()
    for text in texts:
        results = analyzer.analyze(text=text, language="en")
        keep, detected, red_types = [], {}, {}
        for r in results:
            detected[r.entity_type] = detected.get(r.entity_type, 0) + 1
            sev = LABEL_SEVERITY.get(r.entity_type)
            if sev is None:
                unknown.add(r.entity_type)
                sev = FAILCLOSED_SEV
            if sev >= threshold:
                keep.append(r)
                red_types[r.entity_type] = red_types.get(r.entity_type, 0) + 1
        # AnonymizerEngine default operator replaces each kept span with "<ENTITY_TYPE>"
        out = anonymizer.anonymize(text=text, analyzer_results=keep).text if keep else text
        redacted.append(out)
        stats.append({"n_detected": len(results), "n_redacted": len(keep),
                      "detected": detected, "redacted": red_types})

    json.dump({"redacted": redacted, "stats": stats, "threshold": threshold,
               "unknown_labels_failclosed": sorted(unknown),
               "label_severity": LABEL_SEVERITY}, sys.stdout)


if __name__ == "__main__":
    main()
