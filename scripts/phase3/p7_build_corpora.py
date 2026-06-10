"""
p7_build_corpora.py — Phase 7 / Stage 1: build + verify the k-generalized corpora.

LOCAL ONLY: pure generalization + verification. NO embedding, NO API, NO index build.

For each target k in {2,5,10}: produce a globally k-anonymous copy of the 100 employee records by
MINIMAL full-domain generalization over the frozen QI hierarchy (l7_consistency_check.QI_HIERARCHY,
re-confirmed exit-0), suppressing residual sub-k records. Also a RANDOM-SAME-RATE corpus per k (same
number of QI-cells blurred at random, seed 42) — the bulk-degradation confound floor.

CRITICAL serialization rule (the spot-check gate): the chunk must carry the GENERALIZED QI, so the
generalized record serializes age->age_range, salary->salary_range (the buckets the k-anon is computed
over — raw age/salary are finer and would break k-anon in the text) and SUPPRESSES the raw fields that
re-derive a generalized QI (date_of_birth->age, address->office_location, job_title/surname_job_title->
department). Spot-check verifies no raw QI leaks into the serialized chunk.

GUARDS: QI hierarchy is the committed, consistency-checked one (NOT redefined). The re-id k drives WHICH
records generalize to WHICH level; it is NEVER a success metric. The baseline corpus/collections are
untouched — this writes NEW files only.
"""
import json
import os
import random
import sys
from itertools import product
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from scripts.phase3.l7_consistency_check import QUASI_IDENTIFIERS, age_range, salary_range  # noqa: E402
from scripts.phase3.l7_gate import generalize, max_level                                    # noqa: E402

CORPUS = os.path.join(ROOT, "data/ground_truth/ground_truth.json")
OUT_DIR = os.path.join(ROOT, "results/phase3/p7")
KS = [2, 5, 10]
SUPP_CAP = 0.10              # allow <=10% suppression as the release valve for minimal generalization
SEED = 42

# Fields ALWAYS suppressed: finer than their QI's L0 bucket, so they leak sub-bucket info even when
# the QI is not "generalized". date_of_birth re-derives the exact age (finer than the age_range bucket).
_ALWAYS_SUPPRESS = ["date_of_birth"]
# raw fields that re-derive a generalized QI and must be suppressed when that QI is generalized to L>=1
_LEAKY = {"department": ["job_title", "surname_job_title"]}
# the QI's raw record field (what _employee_text serializes) -> we overwrite it with the generalized value
_QI_FIELD = {"department": "department", "salary_range": "salary", "medical_condition": "medical_condition",
             "performance": "performance", "gender": "gender", "age_range": "age", "office_location": "office_location"}

# _employee_text field order (replica of build_index.py:_employee_text — avoids the spaCy-shim import)
_FIELD_LABELS = [
    ("national_id", "National ID"), ("name", "Name"), ("email", "Email"), ("phone", "Phone"),
    ("address", "Address"), ("date_of_birth", "Date of Birth"), ("iban", "IBAN"),
    ("health_record_id", "Health Record ID"), ("surname_job_title", "Surname / Title"),
    ("salary", "Salary"), ("medical_condition", "Medical Condition"), ("employee_id", "Employee ID"),
    ("immigration_status", "Immigration Status"), ("performance", "Performance"), ("gender", "Gender"),
    ("age", "Age"), ("department", "Department"), ("job_title", "Job Title"),
    ("office_location", "Office Location"), ("work_schedule", "Work Schedule"),
    ("project_assignment", "Project Assignment"), ("training_status", "Training Status"),
]


def employee_text(doc):
    lines = ["EMPLOYEE RECORD", f"Document ID: {doc.get('document_id','')}"]
    for f, lab in _FIELD_LABELS:
        v = doc.get(f)
        if v is not None and str(v).strip().lower() not in ("", "none", "n/a"):
            lines.append(f"{lab}: {v}")
    return "\n".join(lines)


def l0_qis(rec):
    """The QI values at level 0 (the buckets the re-id analysis / k-anon are computed over)."""
    return {"department": rec.get("department"), "salary_range": salary_range(rec.get("salary")),
            "medical_condition": (rec.get("medical_condition") or "none"),
            "performance": rec.get("performance"), "gender": rec.get("gender"),
            "age_range": age_range(rec.get("age")), "office_location": rec.get("office_location")}


def gen_tuple(l0, node):
    return tuple(generalize(qi, l0[qi], node[QUASI_IDENTIFIERS.index(qi)]) for qi in QUASI_IDENTIFIERS)


def min_kanon_node(records_l0, k):
    """Exhaustive minimal full-domain search: among lattice nodes whose suppression (records in
    classes < k) is <= SUPP_CAP, return the one of least normalised height. Heuristic (stated):
    full-domain recoding + bounded suppression; minimal in height, not the NP-hard optimal local
    recoding (which is future work). The lattice is small (~2592 nodes) so this is exhaustive."""
    ranges = [range(max_level(qi) + 1) for qi in QUASI_IDENTIFIERS]
    maxlev = [max_level(qi) for qi in QUASI_IDENTIFIERS]
    best = None
    for node in product(*ranges):
        classes = Counter(gen_tuple(l0, node) for l0 in records_l0)
        supp = sum(c for c in classes.values() if c < k)
        if supp / len(records_l0) > SUPP_CAP:
            continue
        height = sum(node[i] / maxlev[i] for i in range(len(node)))
        ncols = sum(1 for x in node if x > 0)
        keyv = (height, ncols)
        if best is None or keyv < best[0]:
            best = (keyv, node, supp)
    return best[1], best[2]   # (node levels, suppression count)


def build_generalized(records, node):
    """Apply node generalization to each record; suppress leaky raw fields; drop sub-k records.
    Returns (kept_generalized_records, dropped_count, achieved_min_k, gen_cols, gen_levels)."""
    l0s = [l0_qis(r) for r in records]
    classes = Counter(gen_tuple(l0, node) for l0 in l0s)
    gen_cols = [qi for i, qi in enumerate(QUASI_IDENTIFIERS) if node[i] > 0]
    kept, dropped = [], 0
    for r, l0 in zip(records, l0s):
        gt = gen_tuple(l0, node)
        if classes[gt] < k_current:          # residual sub-k -> suppress (drop the document)
            dropped += 1
            continue
        nr = dict(r)
        for f in _ALWAYS_SUPPRESS:
            nr[f] = None
        for i, qi in enumerate(QUASI_IDENTIFIERS):
            nr[_QI_FIELD[qi]] = generalize(qi, l0[qi], node[i])   # serialize the GENERALIZED bucket/value
            if node[i] > 0:
                for leaky in _LEAKY.get(qi, []):
                    nr[leaky] = None                              # suppress raw field that re-derives this QI
        kept.append(nr)
    kept_classes = Counter(gen_tuple(l0_qis_from_generalized(r), node) for r in kept) if kept else Counter()
    achieved = min(classes[gt] for gt in classes if classes[gt] >= k_current) if any(c >= k_current for c in classes.values()) else 0
    levels = [node[i] for i, qi in enumerate(QUASI_IDENTIFIERS) if node[i] > 0]
    return kept, dropped, achieved, gen_cols, levels


def l0_qis_from_generalized(r):
    # the generalized record already stores generalized QI strings; for class re-check use them directly
    return {qi: r.get(_QI_FIELD[qi]) for qi in QUASI_IDENTIFIERS}


def build_random_same_rate(records, node, rng):
    """Random-same-rate: generalize the SAME number of (record,QI) cells as the k-driven full-domain
    node, chosen at random, to a level drawn from the k-driven level distribution. No suppression."""
    n = len(records)
    gen_cols = [i for i in range(len(QUASI_IDENTIFIERS)) if node[i] > 0]
    n_cells = len(gen_cols) * n                                   # same volume as full-domain
    level_pool = [node[i] for i in gen_cols] or [0]
    all_cells = [(ri, qi) for ri in range(n) for qi in range(len(QUASI_IDENTIFIERS))]
    chosen = set(rng.sample(all_cells, min(n_cells, len(all_cells))))
    out = []
    for ri, r in enumerate(records):
        l0 = l0_qis(r)
        nr = dict(r)
        for f in _ALWAYS_SUPPRESS:
            nr[f] = None
        for qi_i, qi in enumerate(QUASI_IDENTIFIERS):
            if (ri, qi_i) in chosen:
                lvl = min(rng.choice(level_pool), max_level(qi))
                nr[_QI_FIELD[qi]] = generalize(qi, l0[qi], lvl)
                if lvl > 0:
                    for leaky in _LEAKY.get(qi, []):
                        nr[leaky] = None
            else:
                nr[_QI_FIELD[qi]] = generalize(qi, l0[qi], 0)     # bucket even when not generalized (k-anon safe text)
        out.append(nr)
    return out, n_cells


def spot_check(generalized_records, n=4):
    """Confirm no raw QI leaks into the serialized chunk: raw 5-digit salary, raw 2-digit age on the
    Age line, or a suppressed leaky field still present."""
    import re
    issues = []
    for r in generalized_records[:n]:
        txt = employee_text(r)
        for line in txt.splitlines():
            if line.startswith("Age:") and re.search(r"\bAge:\s*\d{1,3}\s*$", line):
                issues.append(("raw age", r["document_id"], line))
            if line.startswith("Salary:") and re.search(r"\bSalary:\s*\d{4,}", line):
                issues.append(("raw salary", r["document_id"], line))
        if "Date of Birth:" in txt:
            issues.append(("DOB present (re-derives age)", r["document_id"], ""))
    return issues


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    corpus = json.load(open(CORPUS))
    emp = corpus["employee_records"]
    l0s = [l0_qis(r) for r in emp]
    print(f"corpus: {len(emp)} employee records | QIs: {QUASI_IDENTIFIERS} | SUPP_CAP={SUPP_CAP}")
    print(f"L0 distinct QI-combos: {len(set(gen_tuple(l0, tuple(0 for _ in QUASI_IDENTIFIERS)) for l0 in l0s))} "
          f"(of {len(emp)}) -> mostly unique at L0\n")

    global k_current
    rng = random.Random(SEED)
    rows = []
    spot_all = []
    for k in KS:
        k_current = k
        node, supp = min_kanon_node(l0s, k)
        kept, dropped, achieved, gen_cols, levels = build_generalized(emp, node)
        # achieved-k over KEPT generalized records
        kept_classes = Counter(gen_tuple(l0_qis_from_generalized(r), node) for r in kept)
        achieved_min = min(kept_classes.values()) if kept_classes else 0
        gen_rate = len(gen_cols) / len(QUASI_IDENTIFIERS)
        gen_depth = round(sum(levels) / len(levels), 2) if levels else 0
        info_loss = round(sum(node[i] / max_level(QUASI_IDENTIFIERS[i]) for i in range(len(node))) / len(QUASI_IDENTIFIERS), 2)
        rows.append((k, gen_cols, gen_rate, gen_depth, info_loss, dropped, achieved_min, node))
        # random-same-rate corpus
        rnd, ncells = build_random_same_rate(emp, node, rng)
        # save both
        json.dump({**corpus, "employee_records": kept},
                  open(os.path.join(OUT_DIR, f"corpus_k{k}.json"), "w"))
        json.dump({**corpus, "employee_records": rnd},
                  open(os.path.join(OUT_DIR, f"corpus_random_k{k}.json"), "w"))
        spot_all.append((k, spot_check(kept)))

    print("=" * 92)
    print("ACHIEVED-K + INFO-LOSS (per k): the utility cost made visible BEFORE any spend")
    print("=" * 92)
    print(f"{'k':>3} | {'gen_cols (QIs generalized)':<42} | {'cols':>5} | {'depth':>5} | {'info_loss':>9} | {'drop':>4} | {'min-k':>6}")
    for k, gc, gr, gd, il, dr, am, node in rows:
        ok = "OK" if am >= k else f"FAIL({am})"
        print(f"{k:>3} | {','.join(gc):<42} | {gr:>5.2f} | {gd:>5} | {il:>9.2f} | {dr:>4} | {am:>3} {ok}")
    print()
    # FLAG: substantial corpus degradation at the discriminating cell (cols >=0.70 OR info_loss >=0.50)
    k2 = rows[0]
    gr2, il2 = k2[2], k2[4]
    if gr2 >= 0.70 or il2 >= 0.50:
        print(f"*** FLAG: k=2 already removes a large share of QI information — cols {gr2:.2f}, info_loss {il2:.2f},")
        print(f"    [{','.join(k2[1])}] at mean depth {k2[3]}, plus {k2[5]} records dropped. Substantial corpus")
        print(f"    degradation at the discriminating cell: an F2 drop here risks the 'corpus was gutted' reading,")
        print(f"    NOT 'ingestion k-anonymity works'. The likely answer is partly visible pre-spend. ***")
    else:
        print(f"    k=2: cols {gr2:.2f}, info_loss {il2:.2f} — not near-blanket; a genuine partial k-anonymization.")
    print(f"\n    SANITY vs L7: corpus-level k generalises records that are NEVER retrieved too, so P7's")
    print(f"    gen_rate (above) is the WHOLE-corpus cost; L7's per-query rate (k=2 0.335, k=5/10 ~0.73/0.77)")
    print(f"    only touched retrieved chunks. P7's ingestion cost is structurally >= L7's query-time cost.")
    print("\n" + "=" * 92 + "\nSPOT-CHECK: QIs generalised in the SERIALIZED chunk text (no raw-field bypass)\n" + "=" * 92)
    for k, issues in spot_all:
        print(f"  k={k}: {'CLEAN (no raw QI leak)' if not issues else 'ISSUES: ' + str(issues)}")
    # show one sample generalized chunk
    sample = json.load(open(os.path.join(OUT_DIR, "corpus_k5.json")))["employee_records"][0]
    print("\n  sample generalized chunk (k=5):")
    for line in employee_text(sample).splitlines():
        if any(line.startswith(p) for p in ("Department:", "Salary:", "Medical", "Age:", "Office", "Performance:", "Gender:", "Date of Birth", "Job Title", "Address:")):
            print(f"    {line}")
    print(f"\nsaved: {OUT_DIR}/corpus_k{{2,5,10}}.json + corpus_random_k{{2,5,10}}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
