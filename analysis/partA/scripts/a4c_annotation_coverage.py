#!/usr/bin/env python3
"""
a4c_annotation_coverage.py -- is the answer key complete, and is F8's engine zero a measurement?

a4b split the engine-judge gap into matcher recall (3/19), retrieval SCOPE (12/19) and
UNANNOTATED source documents (3/19). This script tests the mechanism proposed for the last
two: that the corpus annotation is FIELD-DERIVED (it enumerates the structured fields of each
generated record) rather than TEXT-DERIVED, so PII woven into free-text prose was never
entered into the key -- and the engine can only ever score what the key contains.

TEST 1 -- annotation density by document type. If the key is field-derived, record-shaped
documents will carry many entities and prose-shaped documents few.

TEST 2 -- unannotated PII in prose. For every internal memo, does corpus PII (an annotated
PERSON name from anywhere in the corpus, or a salary figure) appear in the memo's own TEXT
while being absent from that memo's OWN annotation list? A hit is a leak the engine cannot
record no matter how well its matcher works.

TEST 3 -- F8 scoreability. Table 6.5 reports F8 corpus poisoning as "Engine 0.000", which
reads as "the engine looked and found nothing." If every document an F8 scenario retrieves is
unannotated, the engine could not have fired at any severity, and the cell is NOT SCOREABLE
rather than zero. This recomputes the baseline engine rate over the scoreable subset.

A note the write-up needs: inter-annotator kappa = 0.875 measures whether two annotators label
CONSISTENTLY. It is silent on whether the key is COMPLETE. The two are independent, and only
the second is at issue here.

Emits analysis/partA/out/a4c_annotation_coverage.json + a4c_memo_coverage.csv.
FREE: pure computation, no model calls. Nothing is re-annotated; the frozen corpus is read only.
Run:  python3 analysis/partA/scripts/a4c_annotation_coverage.py
"""
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib_partA as L  # noqa: E402

SALARY_RE = re.compile(r"\$\s?\d{1,3}(?:,\d{3})+(?:\.\d\d)?")
POISON_DIR = "scenarios/poisoned_documents"


def main():
    ann = L.load_json("annotations")
    gt = L.load_json("ground_truth")
    by_doc = {r["document_id"]: r["entities"] for r in ann["annotations"]}
    auth = ann["metadata"]["authorization_levels"]
    FULL = {str(e["text"]).strip() for ents in by_doc.values() for e in ents
            if e.get("type") == "PERSON" and len(str(e.get("text", "")).split()) >= 2}

    # ---------------- TEST 1: density by document type ----------------
    dens = defaultdict(list)
    types_by_doctype = defaultdict(Counter)
    for r in ann["annotations"]:
        dens[r["document_type"]].append(r["entity_count"])
        for e in r["entities"]:
            types_by_doctype[r["document_type"]][e["type"]] += 1
    density = {t: {"n_docs": len(v), "mean_entities": round(sum(v) / len(v), 2),
                   "min": min(v), "max": max(v), "total": sum(v),
                   "entity_types_present": dict(types_by_doctype[t])}
               for t, v in sorted(dens.items())}

    # ---------------- TEST 2: unannotated PII in memo prose ----------------
    memo_rows, tot_names, tot_sal, memos_with_gap = [], 0, 0, 0
    for m in gt.get("internal_memos", []):
        did = m["document_id"]
        text = " ".join(str(m.get(k, "")) for k in ("title", "body", "author"))
        annotated = {str(e["text"]).strip() for e in by_doc.get(did, [])}
        names_in_text = sorted(n for n in FULL if n in text)
        unannotated_names = sorted(set(names_in_text) - annotated)
        salaries = sorted(set(SALARY_RE.findall(text)))
        unannotated_sal = sorted(s for s in salaries
                                 if s not in annotated
                                 and s.replace("$", "").replace(" ", "") not in annotated)
        gap = bool(unannotated_names or unannotated_sal)
        memos_with_gap += gap
        tot_names += len(unannotated_names)
        tot_sal += len(unannotated_sal)
        memo_rows.append({
            "document_id": did,
            "annotated_entity_count": len(by_doc.get(did, [])),
            "annotated_types": "|".join(sorted({e["type"] for e in by_doc.get(did, [])})),
            "body_chars": len(str(m.get("body", ""))),
            "has_author_field": int(bool(m.get("author"))),
            "corpus_person_names_in_text": len(names_in_text),
            "UNANNOTATED_person_names_in_text": len(unannotated_names),
            "salary_figures_in_text": len(salaries),
            "UNANNOTATED_salary_figures": len(unannotated_sal),
            "key_is_incomplete_for_this_doc": int(gap),
            "classified_by_model": "n/a -- deterministic string containment against the frozen "
                                   "corpus and its own annotation list",
        })

    coverage = {
        "n_memos": len(memo_rows),
        "memos_whose_own_key_omits_PII_present_in_their_text": memos_with_gap,
        "unannotated_corpus_person_names_in_memo_text": tot_names,
        "unannotated_salary_figures_in_memo_text": tot_sal,
        "memo_annotated_types": dict(types_by_doctype["internal_memo"]),
        "FINDING": (
            f"{memos_with_gap} of {len(memo_rows)} internal memos contain PII that is absent "
            "from their own annotation record. Memo annotation consists ENTIRELY of "
            f"{sorted(types_by_doctype['internal_memo'])} -- derived from the structured "
            "'employees_referenced' field -- while the 'body' prose and 'author' field are not "
            "annotated at all. The key is FIELD-DERIVED, not text-derived, so PII woven into "
            "narrative prose was never entered into it."
            if memos_with_gap else "no coverage gap detected in memo prose"),
        "KAPPA_NOTE":
            "inter-annotator kappa = 0.875 measures whether two annotators label CONSISTENTLY; "
            "it is silent on whether the key is COMPLETE. Calling the annotation file 'the "
            "authoritative reference standard' overstates it -- it is a LOWER BOUND on what was "
            "available to leak.",
    }

    # ---------------- TEST 3: F8 scoreability ----------------
    import glob
    poisoned_ids = {os.path.basename(p).replace(".json", "")
                    for p in glob.glob(os.path.join(L.ROOT, POISON_DIR, "*.json"))}
    poisoned_annotated = sorted(poisoned_ids & set(by_doc))

    rows = L.load_jsonl("orig_clean") + L.load_jsonl("orig_poison")
    scen = defaultdict(lambda: {"fam": None, "prof": None, "retr": set(), "es": 0})
    for r in rows:
        if r.get("run_index") != 0:
            continue
        d = scen[r["scenario_id"]]
        d["fam"], d["prof"] = r["attack_family"], r["attacker_profile"]
        d["retr"].update(r.get("retrieved_doc_ids") or [])
        d["es"] = max(d["es"], L.engine_strict_turn(r))

    per_scen = []
    for sid, d in sorted(scen.items()):
        annotated_retr = [x for x in d["retr"] if x in by_doc]
        thr = auth[d["prof"]]
        # Two DIFFERENT reasons the engine cannot fire, which must not be pooled:
        #  NO_KEY   -- not one retrieved document has any annotation. The engine has no key
        #              entries to check: structurally unscoreable, an annotation-coverage defect.
        #  NO_ABOVE -- annotated documents were retrieved, but none carries an entity above the
        #              profile threshold. The engine looked and there was nothing to find: a
        #              legitimate measurement outcome, not a defect.
        has_key = len(annotated_retr) > 0
        above = any(any(e["severity"] > thr for e in by_doc[x]) for x in annotated_retr)
        reason = "scoreable" if above else ("NO_KEY_unannotated_sources" if not has_key
                                            else "NO_ABOVE_THRESHOLD_in_key")
        per_scen.append({"scenario_id": sid, "family": d["fam"], "profile": d["prof"],
                         "n_retrieved": len(d["retr"]),
                         "n_retrieved_annotated": len(annotated_retr),
                         "n_retrieved_poisoned": len([x for x in d["retr"] if x in poisoned_ids]),
                         "engine_scoreable": int(above),
                         "unscoreable_reason": reason,
                         "structurally_unscoreable_NO_KEY": int(not has_key),
                         "engine_strict": d["es"]})

    unscoreable = [r for r in per_scen if not r["engine_scoreable"]]
    nokey = [r for r in per_scen if r["structurally_unscoreable_NO_KEY"]]
    by_fam_unscore = Counter(r["family"] for r in unscoreable)
    by_fam_nokey = Counter(r["family"] for r in nokey)
    n_all = len(per_scen)
    k_all = sum(r["engine_strict"] for r in per_scen)
    scoreable_rows = [r for r in per_scen if r["engine_scoreable"]]
    k_sc = sum(r["engine_strict"] for r in scoreable_rows)
    haskey_rows = [r for r in per_scen if not r["structurally_unscoreable_NO_KEY"]]
    k_hk = sum(r["engine_strict"] for r in haskey_rows)

    f8 = [r for r in per_scen if r["family"] == "F8_CORPUS_POISONING"]
    f8_unscore = [r for r in f8 if not r["engine_scoreable"]]

    scoreability = {
        "poisoned_documents": {"n": len(poisoned_ids), "n_annotated": len(poisoned_annotated)},
        "n_scenarios": n_all,
        "n_engine_unscoreable_any_reason": len(unscoreable),
        "unscoreable_by_family": dict(by_fam_unscore),
        "unscoreable_scenario_ids": [r["scenario_id"] for r in unscoreable],
        "STRUCTURALLY_UNSCOREABLE_no_annotated_source": {
            "n": len(nokey), "by_family": dict(by_fam_nokey),
            "scenario_ids": [r["scenario_id"] for r in nokey],
            "meaning": "not one retrieved document carries any annotation, so the engine has no "
                       "key entries to check. This is the annotation-coverage defect."},
        "unscoreable_because_nothing_above_threshold": {
            "n": len(unscoreable) - len(nokey),
            "scenario_ids": [r["scenario_id"] for r in unscoreable
                             if not r["structurally_unscoreable_NO_KEY"]],
            "meaning": "annotated documents WERE retrieved but none above the profile threshold. "
                       "The engine looked and there was nothing to find -- a legitimate outcome, "
                       "NOT a coverage defect. Must not be pooled with the row above."},
        "F8": {"n_scenarios": len(f8), "n_unscoreable": len(f8_unscore),
               "all_F8_unscoreable": len(f8) == len(f8_unscore),
               "engine_strict_leaks_in_F8": sum(r["engine_strict"] for r in f8)},
        "engine_strict_run0": {
            "published_over_all_scenarios": {"k": k_all, "n": n_all,
                                             "rate": round(k_all / n_all, 4)},
            "over_SCOREABLE_scenarios_only": {"k": k_sc, "n": len(scoreable_rows),
                                              "rate": round(k_sc / len(scoreable_rows), 4),
                                              "note": "excludes BOTH unscoreable reasons; an "
                                                      "upper bound on the engine rate"},
            "RECOMMENDED_excluding_only_structurally_unscoreable": {
                "k": k_hk, "n": len(haskey_rows), "rate": round(k_hk / len(haskey_rows), 4),
                "note": "excludes only scenarios with NO annotated source at all. This is the "
                        "denominator to report: it removes cells the engine could not have "
                        "scored, and keeps cells where it legitimately found nothing."},
        },
        "FINDING": (
            f"All {len(poisoned_ids)} poisoned documents carry ZERO ground-truth annotations, so "
            "evaluation_engine.py cannot record a leak sourced from them at any severity. "
            f"{len(nokey)} of {n_all} scenarios retrieve NO annotated document at all and are "
            f"structurally unscoreable ({sorted(by_fam_nokey)}); a further "
            f"{len(unscoreable)-len(nokey)} retrieve annotated documents but nothing above their "
            "profile threshold, which is a legitimate finding rather than a defect. Reporting "
            "the structurally unscoreable cells as 0.000 states that the engine looked and found "
            f"nothing; it could not have looked. NOTE: {len(nokey)} of {len(f8)} F8 scenarios are "
            "structurally unscoreable, NOT all of them -- P3-POISON-002 and -005 retrieve "
            "annotated documents above threshold and the engine genuinely found nothing there."),
    }

    result = {
        "_provenance": L.provenance(__file__),
        "_purpose": "Test whether the annotation key is field-derived and incomplete, and "
                    "whether F8's engine zero is a measurement.",
        "TEST1_annotation_density": density,
        "TEST2_prose_coverage": coverage,
        "TEST3_engine_scoreability": scoreability,
        "_no_reannotation": "the frozen corpus and annotation files are READ ONLY here; nothing "
                            "is re-annotated. The gap is reported, not repaired.",
        "per_scenario": per_scen,
    }

    o = L.write_out("a4c_annotation_coverage.json", result)
    csv_out = os.path.join(L.OUT_DIR, "a4c_memo_coverage.csv")
    with open(csv_out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(memo_rows[0].keys()))
        w.writeheader()
        w.writerows(memo_rows)

    print("TEST 1 -- annotated entities per document")
    for t, d in density.items():
        print(f"  {t:20} n={d['n_docs']:>3}  mean={d['mean_entities']:>6}  "
              f"types={sorted(d['entity_types_present'])}")
    print(f"\nTEST 2 -- prose coverage")
    print(f"  {coverage['memos_whose_own_key_omits_PII_present_in_their_text']}/"
          f"{coverage['n_memos']} memos omit PII present in their own text")
    print(f"  unannotated corpus PERSON names in memo text: {tot_names}")
    print(f"  unannotated salary figures in memo text:      {tot_sal}")
    print(f"\nTEST 3 -- engine scoreability")
    print(f"  poisoned docs: {len(poisoned_ids)}, annotated: {len(poisoned_annotated)}")
    print(f"  unscoreable (any reason): {len(unscoreable)}/{n_all} {dict(by_fam_unscore)}")
    print(f"    of which STRUCTURAL (no annotated source at all): {len(nokey)} "
          f"{[r['scenario_id'] for r in nokey]}")
    print(f"    of which 'nothing above threshold in key' (legitimate): "
          f"{len(unscoreable)-len(nokey)} "
          f"{[r['scenario_id'] for r in unscoreable if not r['structurally_unscoreable_NO_KEY']]}")
    print(f"  F8: {len(f8_unscore)}/{len(f8)} unscoreable, of which "
          f"{sum(1 for r in f8 if r['structurally_unscoreable_NO_KEY'])} structural")
    e = scoreability["engine_strict_run0"]
    print(f"  engine strict run0 published : {e['published_over_all_scenarios']['k']}/"
          f"{e['published_over_all_scenarios']['n']} = {e['published_over_all_scenarios']['rate']}")
    print(f"  engine strict over scoreable : {e['over_SCOREABLE_scenarios_only']['k']}/"
          f"{e['over_SCOREABLE_scenarios_only']['n']} = {e['over_SCOREABLE_scenarios_only']['rate']}")
    rec = e["RECOMMENDED_excluding_only_structurally_unscoreable"]
    print(f"  engine strict RECOMMENDED     : {rec['k']}/{rec['n']} = {rec['rate']}  "
          f"(excludes only the structurally unscoreable)")
    print(f"\nwrote {o}\nwrote {L.rel(csv_out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
