"""
Phase 3 / Task 0.1 — Presidio detection recall vs the ground-truth answer key.

MEASUREMENT ONLY — builds NO redaction/anonymization.

Runs in the isolated .venv-presidio (Python 3.11) because spaCy/Presidio cannot
import on the project's Python 3.14 interpreter.

Subtask 3: custom PatternRecognizers for the Algerian entities (NNI, EMPLOYEE_ID,
           HEALTH_RECORD_ID, DZ IBAN) via PatternRecognizer + registry.add_recognizer
           + context words.
Subtask 4: per-type recall (flagged / answer-key) over the faithfully reconstructed
           corpus, plus a precision lower-bound. Flags every type with recall < 0.90.

Inputs (read-only):
  results/phase3/presidio_check/corpus_text.json      (Phase-2 _TEXT_BUILDERS serialization)
  data/ground_truth/ground_truth_annotations.json     (the answer key)
  results/phase3/presidio_check/answer_key_inventory.json (per-type severity)

Output:
  results/phase3/presidio_check/presidio_recall.json
  results/phase3/presidio_check/SUBTASK4_presidio_recall.md
"""
import json, os, re
from collections import defaultdict, Counter
from importlib.metadata import version, PackageNotFoundError

import spacy
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PC = os.path.join(ROOT, "results", "phase3", "presidio_check")
RECALL_FLAG = 0.90

# Recognizer set: "ids_only" = baseline (4 Algerian ID recognizers + Presidio defaults);
# "bin_a" = + legitimate structured detectors (secrets/path/xref/DZ-phone/salary).
SET_NAME = os.environ.get("PRESIDIO_SET", "bin_a")
OUT_STEM = {"ids_only": "presidio_recall_baseline",
            "bin_a": "presidio_recall"}.get(SET_NAME, "presidio_recall")


def ver(pkg):
    try:
        return version(pkg)
    except PackageNotFoundError:
        return None


# ---------------------------------------------------------------- load inputs
corpus = json.load(open(os.path.join(PC, "corpus_text.json")))
ann = json.load(open(os.path.join(ROOT, "data", "ground_truth",
                                   "ground_truth_annotations.json")))
inv = json.load(open(os.path.join(PC, "answer_key_inventory.json")))
sev_by_type = {}
for r in inv["types"]:
    s = r["severity"]
    sev_by_type[r["type"]] = s if isinstance(s, int) else max(s)


# -------------------------------------------------- subtask 3: recognizers
def build_custom_recognizers(set_name="bin_a"):
    # 4 Algerian-ID recognizers (always on) — verified 1.0 recall
    recs = [
        PatternRecognizer(
            supported_entity="NNI_DZ",
            patterns=[Pattern("nni_9digit", r"\b\d{9}\b", 0.4)],
            context=["national", "national id", "nni", "nin", "id national"],
        ),
        PatternRecognizer(
            supported_entity="EMPLOYEE_ID",
            patterns=[Pattern("emp_id", r"\bEMP-\d{5}\b", 0.85)],
            context=["employee", "employee id", "staff", "emp"],
        ),
        PatternRecognizer(
            supported_entity="HEALTH_RECORD_ID",
            patterns=[Pattern("mrn", r"\bMRN-\d{5}\b", 0.85)],
            context=["health", "medical", "patient", "record", "mrn"],
        ),
        PatternRecognizer(
            supported_entity="IBAN_DZ",
            patterns=[Pattern("iban_dz", r"\bDZ\d{2}-\d{5}-\d{10}-\d{2}\b", 0.9)],
            context=["iban", "bank", "account"],
        ),
    ]
    if set_name != "bin_a":
        return recs
    # bin-(a): legitimate, generalizable structured detectors (NOT corpus-value gazetteers)
    recs += [
        PatternRecognizer(
            supported_entity="API_KEY",
            patterns=[Pattern("api_key_sk", r"\bsk-(?:ant-)?[A-Za-z0-9]{20,}\b", 0.9)],
            context=["api", "key", "secret", "openai", "anthropic"],
        ),
        PatternRecognizer(
            supported_entity="JWT_TOKEN",
            patterns=[Pattern("jwt", r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", 0.9)],
            context=["jwt", "token", "bearer"],
        ),
        PatternRecognizer(
            supported_entity="PASSWORD_HASH",
            patterns=[Pattern("bcrypt", r"\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}", 0.9)],
            context=["password", "hash", "bcrypt"],
        ),
        PatternRecognizer(
            supported_entity="PRIVATE_KEY",
            patterns=[Pattern("pem", r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----", 0.95)],
            context=["private", "key", "rsa", "pem"],
        ),
        PatternRecognizer(
            supported_entity="DB_CONN_STRING",
            patterns=[Pattern("db_uri", r"\b[a-zA-Z][\w+]*://[^\s:@/]+:[^\s:@/]+@[\w.-]+", 0.85)],
            context=["db", "database", "connection", "postgres", "dsn"],
        ),
        PatternRecognizer(
            supported_entity="FILE_PATH",
            patterns=[Pattern("unix_path", r"(?:/[\w.-]+){2,}", 0.6)],
            context=["path", "file", "directory", "paths"],
        ),
        PatternRecognizer(
            supported_entity="CROSS_REFERENCE",
            patterns=[Pattern("hr_ref", r"\bhr_file_\d{3}\b", 0.85)],
            context=["employee", "reference", "ref", "referenced"],
        ),
        PatternRecognizer(
            supported_entity="PHONE_DZ",
            patterns=[Pattern("dz_phone", r"\+213-\d{3}-\d{6}", 0.8)],
            context=["phone", "tel", "mobile"],
        ),
        PatternRecognizer(
            supported_entity="SALARY",
            patterns=[Pattern("salary_ctx",
                              r"(?:[Ss]alary|[Cc]ompensation)\s*[:\-]?\s*\$?\d{3,7}", 0.7)],
            context=["salary", "compensation", "pay"],
        ),
    ]
    return recs


engine = AnalyzerEngine()
for rec in build_custom_recognizers(SET_NAME):
    engine.registry.add_recognizer(rec)

# Does the DEFAULT IBAN_CODE recognizer catch the synthetic hyphenated DZ IBAN?
sample_iban = "DZ23-86758-8963334018-54"
base_engine = AnalyzerEngine()
iban_code_hits = base_engine.analyze(text=f"Bank IBAN: {sample_iban}",
                                     language="en", entities=["IBAN_CODE"])
iban_code_catches_dz = len(iban_code_hits) > 0

# GT type -> acceptable Presidio labels for the stricter "correct-label" recall
LABELS = {
    "NATIONAL_ID": {"NNI_DZ"},
    "EMPLOYEE_ID": {"EMPLOYEE_ID"},
    "HEALTH_RECORD_ID": {"HEALTH_RECORD_ID"},
    "IBAN": {"IBAN_CODE", "IBAN_DZ"},
    "PERSON": {"PERSON"},
    "SURNAME_TITLE": {"PERSON"},
    "EMAIL": {"EMAIL_ADDRESS"},
    "PHONE": {"PHONE_NUMBER", "PHONE_DZ"},
    "ADDRESS": {"LOCATION"},
    "OFFICE_LOCATION": {"LOCATION"},
    "DOB": {"DATE_TIME"},
    "INTERNAL_IP": {"IP_ADDRESS"},
    "MEDICAL": {"MEDICAL_LICENSE"},
    # bin-(a) structured detectors
    "API_KEY": {"API_KEY"},
    "JWT_TOKEN": {"JWT_TOKEN"},
    "PASSWORD_HASH": {"PASSWORD_HASH"},
    "PRIVATE_KEY": {"PRIVATE_KEY"},
    "DB_CONN_STRING": {"DB_CONN_STRING"},
    "FILE_PATH": {"FILE_PATH"},
    "CROSS_REFERENCE": {"CROSS_REFERENCE"},
    "SALARY": {"SALARY"},
}


def occurrences(text, doc):
    """Return ([(start,end),...], mode) for entity text in doc.
    Falls back to a 5+ digit numeric core when the formatted answer-key text
    (e.g. '$43,905') is not present verbatim (doc stores 'Salary: 43905')."""
    text = str(text)
    spans = []
    if text and text in doc:
        i = doc.find(text)
        while i != -1:
            spans.append((i, i + len(text)))
            i = doc.find(text, i + 1)
        return spans, "verbatim"
    digits = re.sub(r"[^0-9]", "", text)
    if len(digits) >= 5 and digits in doc:
        i = doc.find(digits)
        while i != -1:
            spans.append((i, i + len(digits)))
            i = doc.find(digits, i + 1)
        return spans, "numeric"
    return [], "not_found"


def overlaps(spans, r):
    return any(not (e <= r.start or s >= r.end) for (s, e) in spans)


# -------------------------------------------------- analyze each doc once
results_by_doc = {did: engine.analyze(text=txt, language="en")
                  for did, txt in corpus.items()}

# -------------------------------------------------- subtask 4: recall
per_type = defaultdict(lambda: {"answer_key": 0, "det_any": 0,
                                "det_correct": 0, "not_found": 0})
for rec in ann["annotations"]:
    did = rec["document_id"]
    txt = corpus.get(did, "")
    res = results_by_doc.get(did, [])
    for e in rec["entities"]:
        t = e["type"]
        per_type[t]["answer_key"] += 1
        spans, mode = occurrences(e["text"], txt)
        if not spans:
            per_type[t]["not_found"] += 1
            continue
        if any(overlaps(spans, r) for r in res):
            per_type[t]["det_any"] += 1
        acc = LABELS.get(t, set())
        if acc and any(overlaps(spans, r) for r in res if r.entity_type in acc):
            per_type[t]["det_correct"] += 1

# -------------------------------------------------- precision (lower bound)
gt_spans_by_doc = defaultdict(list)
for rec in ann["annotations"]:
    did = rec["document_id"]
    txt = corpus.get(did, "")
    for e in rec["entities"]:
        spans, _ = occurrences(e["text"], txt)
        gt_spans_by_doc[did].extend(spans)

total_det = 0
tp_det = 0
det_label_hist = Counter()
for did, res in results_by_doc.items():
    gts = gt_spans_by_doc[did]
    for r in res:
        total_det += 1
        det_label_hist[r.entity_type] += 1
        if any(not (e <= r.start or s >= r.end) for (s, e) in gts):
            tp_det += 1
precision_lb = round(tp_det / total_det, 4) if total_det else None

# -------------------------------------------------- assemble per-type rows
rows = []
for t in sorted(per_type, key=lambda k: -per_type[k]["answer_key"]):
    d = per_type[t]
    ak = d["answer_key"]
    rows.append({
        "type": t,
        "severity": sev_by_type.get(t),
        "answer_key": ak,
        "detected_any_label": d["det_any"],
        "detected_correct_label": d["det_correct"],
        "answer_key_text_not_locatable": d["not_found"],
        "recall_any": round(d["det_any"] / ak, 4) if ak else None,
        "recall_correct_label": round(d["det_correct"] / ak, 4) if ak else None,
        "expected_presidio_labels": sorted(LABELS.get(t, [])) or None,
    })

# -------------------------------------------------- sev>=3 overall recall
sev3 = [r for r in rows if (r["severity"] or 0) >= 3]
ak3 = sum(r["answer_key"] for r in sev3)
nf3 = sum(r["answer_key_text_not_locatable"] for r in sev3)
ak3_loc = ak3 - nf3                       # exclude entities not present verbatim in corpus
any3 = sum(r["detected_any_label"] for r in sev3)
cor3 = sum(r["detected_correct_label"] for r in sev3)
recall_any_sev3 = round(any3 / ak3, 4) if ak3 else None
recall_correct_sev3 = round(cor3 / ak3, 4) if ak3 else None
recall_any_sev3_loc = round(any3 / ak3_loc, 4) if ak3_loc else None
recall_correct_sev3_loc = round(cor3 / ak3_loc, 4) if ak3_loc else None

flagged = [r["type"] for r in rows if (r["recall_any"] is not None
                                       and r["recall_any"] < RECALL_FLAG)]

out = {
    "task": "Phase 3 / Task 0.1 — Presidio detection recall (MEASUREMENT ONLY, no redaction)",
    "recognizer_set": SET_NAME,
    "n_custom_recognizers": len(build_custom_recognizers(SET_NAME)),
    "environment": {
        "python": "3.11 (.venv-presidio)",
        "presidio_analyzer": ver("presidio-analyzer"),
        "presidio_anonymizer": ver("presidio-anonymizer"),
        "spacy": ver("spacy") or spacy.__version__,
        "spacy_model": "en_core_web_lg",
        "spacy_model_version": ver("en_core_web_lg"),
    },
    "real_presidio_call": True,
    "method": {
        "corpus_text": "results/phase3/presidio_check/corpus_text.json "
                       "(reconstructed via frozen Phase-2 build_index._TEXT_BUILDERS)",
        "matching": "entity flagged if a Presidio span overlaps an occurrence of the "
                    "answer-key text in the document; verbatim match, with 5+ digit "
                    "numeric fallback for formatted values (e.g. '$43,905' -> '43905')",
        "recall_any": "detected by ANY Presidio label (redaction-relevant: anything "
                      "flagged would be redacted)",
        "recall_correct_label": "detected by the SEMANTICALLY correct label only",
        "precision_note": "LOWER BOUND only — the answer key does not annotate every "
                          "PII type, so legitimate detections of un-annotated types "
                          "(DATE_TIME, LOCATION, URL, NRP, ...) count as false positives",
        "score_threshold": "Presidio default (all results with score > 0)",
    },
    "custom_recognizers": [
        {"entity": "NNI_DZ", "pattern": r"\b\d{9}\b", "base_score": 0.4,
         "context": ["national", "national id", "nni", "nin", "id national"]},
        {"entity": "EMPLOYEE_ID", "pattern": r"\bEMP-\d{5}\b", "base_score": 0.85,
         "context": ["employee", "employee id", "staff", "emp"]},
        {"entity": "HEALTH_RECORD_ID", "pattern": r"\bMRN-\d{5}\b", "base_score": 0.85,
         "context": ["health", "medical", "patient", "record", "mrn"]},
        {"entity": "IBAN_DZ", "pattern": r"\bDZ\d{2}-\d{5}-\d{10}-\d{2}\b",
         "base_score": 0.9, "context": ["iban", "bank", "account"]},
    ],
    "iban_code_default_catches_dz": iban_code_catches_dz,
    "iban_code_test_sample": sample_iban,
    "overall": {
        "total_entities": sum(r["answer_key"] for r in rows),
        "gate_recall_threshold": RECALL_FLAG,
        "sev>=3_answer_key": ak3,
        "sev>=3_not_locatable_in_corpus": nf3,
        "sev>=3_answer_key_locatable": ak3_loc,
        # honest floor = correct-label; any-label = upper bound (partial overlaps inflate it)
        "sev>=3_recall_correct_label_all": recall_correct_sev3,
        "sev>=3_recall_correct_label_locatable": recall_correct_sev3_loc,
        "sev>=3_recall_any_label_all": recall_any_sev3,
        "sev>=3_recall_any_label_locatable": recall_any_sev3_loc,
        "gate_pass": False,  # fails on every variant below 0.90
        "gate_pass_detail": {
            "correct_label_all": recall_correct_sev3 >= RECALL_FLAG,
            "correct_label_locatable": recall_correct_sev3_loc >= RECALL_FLAG,
            "any_label_all": recall_any_sev3 >= RECALL_FLAG,
            "any_label_locatable": recall_any_sev3_loc >= RECALL_FLAG,
        },
    },
    "precision_estimate_lower_bound": precision_lb,
    "total_presidio_detections": total_det,
    "detections_overlapping_a_gt_entity": tp_det,
    "detection_label_histogram": dict(det_label_hist.most_common()),
    "types_flagged_recall_below_0.90": flagged,
    "per_type": rows,
}

os.makedirs(PC, exist_ok=True)
json.dump(out, open(os.path.join(PC, f"{OUT_STEM}.json"), "w"),
          indent=2, ensure_ascii=False)

# -------------------------------------------------- markdown summary
L = [f"# Subtask 4 — Presidio recall vs answer key (recognizer set: {SET_NAME})\n",
     f"- Real Presidio call: **{out['real_presidio_call']}** "
     f"(presidio-analyzer {out['environment']['presidio_analyzer']}, "
     f"spaCy {out['environment']['spacy']} / en_core_web_lg "
     f"{out['environment']['spacy_model_version']})",
     f"- Default IBAN_CODE catches the synthetic DZ IBAN `{sample_iban}`: "
     f"**{iban_code_catches_dz}**",
     f"- Precision (lower bound): **{precision_lb}** "
     f"({tp_det}/{total_det} detections overlap a GT entity)",
     "",
     f"## Overall recall on severity>=3 types (gate >= {RECALL_FLAG}) — FAILS on every variant",
     f"- sev>=3 answer-key entities: **{ak3}** "
     f"({nf3} not locatable verbatim in corpus -> locatable **{ak3_loc}**)",
     f"- recall CORRECT-label (honest floor): all=**{recall_correct_sev3}**, "
     f"locatable=**{recall_correct_sev3_loc}**",
     f"- recall ANY-label (upper bound; partial overlaps inflate it): "
     f"all=**{recall_any_sev3}**, locatable=**{recall_any_sev3_loc}**",
     "",
     f"## Types flagged (recall_any < {RECALL_FLAG}): {len(flagged)}",
     "",
     "| type | sev | n | det_any | recall_any | recall_correct | not_locatable | labels |",
     "|---|--:|--:|--:|--:|--:|--:|---|"]
for r in rows:
    L.append(f"| {r['type']} | {r['severity']} | {r['answer_key']} | "
             f"{r['detected_any_label']} | {r['recall_any']} | "
             f"{r['recall_correct_label']} | {r['answer_key_text_not_locatable']} | "
             f"{','.join(r['expected_presidio_labels'] or []) or '—'} |")
open(os.path.join(PC, f"SUBTASK4_{OUT_STEM}.md"), "w").write("\n".join(L) + "\n")

# -------------------------------------------------- console
print(f"[set={SET_NAME}] WROTE {OUT_STEM}.json + SUBTASK4_{OUT_STEM}.md")
print(f"IBAN_CODE default catches DZ IBAN: {iban_code_catches_dz}")
print(f"precision lower-bound: {precision_lb}  ({tp_det}/{total_det})")
print(f"sev>=3 (n={ak3}; locatable={ak3_loc}): "
      f"correct-label all={recall_correct_sev3} loc={recall_correct_sev3_loc} | "
      f"any-label all={recall_any_sev3} loc={recall_any_sev3_loc}  -> GATE(>=0.90)=FAIL")
print(f"types flagged (recall_any<0.90): {len(flagged)}")
print("\nper-type (sev, n, recall_any, recall_correct, not_locatable):")
for r in rows:
    print(f"  {r['type']:18s} sev={r['severity']} n={r['answer_key']:4d} "
          f"any={r['recall_any']} corr={r['recall_correct_label']} "
          f"nf={r['answer_key_text_not_locatable']}")
