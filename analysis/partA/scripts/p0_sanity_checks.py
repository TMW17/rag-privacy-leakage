#!/usr/bin/env python3
"""
p0_sanity_checks.py -- TASK_SPEC §3.2: reproduce the three published sanity checks from
raw committed artifacts, and settle the Amendment 3(c) canonicity gate.

  SC1  corpus: 155 documents, 2,190 entities, severity distribution 135/865/490/700
       for s = 5/4/3/2.
       NOTE: computed by RECOUNTING the committed annotation file, NOT by re-running the
       generator. CLAUDE.md invariant 3 freezes data/ground_truth/*.json and `make` writes
       them in place; a true seed-42 regeneration belongs in A6, into a scratch directory,
       compared by hash. Recounting tests the same fact without touching a frozen artifact.
  SC2  baseline strict ASR -> engine 0.192, judge 0.288
  SC3  full-stack strict ASR -> engine 0.000, judge 0.173

Also computes the A2 crux the spec asks for at step 4 (per-run ASR on the ORIGINAL baseline
log) because it is the same load and it decides whether the canonicity gate is even
meaningful.

Read-only. Emits analysis/partA/out/p0_sanity_checks.json.
Run:  python3 analysis/partA/scripts/p0_sanity_checks.py
"""
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib_partA as L  # noqa: E402

TARGET_SEVERITY_DIST = {5: 135, 4: 865, 3: 490, 2: 700}
TARGET_DOCS = 155
TARGET_ENTITIES = 2190
TOL = 1e-3


def close(a, b, tol=TOL):
    return a is not None and abs(a - b) < tol


# ------------------------------------------------------------------ SC1
def sc1_corpus():
    ann = L.load_json("annotations")
    meta = ann["metadata"]
    records = ann["annotations"]

    n_records = len(records)
    entities = [e for r in records for e in r["entities"]]
    sev = Counter(e["severity"] for e in entities)
    types = Counter(e["type"] for e in entities)
    methods = Counter(e["detection_method"] for e in entities)

    # weight invariant (CLAUDE.md §4) -- every annotation's confidence_weight must match
    # the canonical mapping for its detection_method.
    W = {"Regex": 1.00, "Regex+Presidio": 1.00, "NER": 0.90, "NER+Presidio": 0.90,
         "NER+Context": 0.90, "NER+Keyword": 0.90, "NER+Regex": 0.90,
         "Keyword+Context": 0.75, "Regex+Context": 0.75, "Set-intersection": 0.75,
         "Membership-inference": 0.75, "LLM-as-Judge": 0.60}
    weight_violations = [
        {"document_id": r["document_id"], "type": e["type"], "method": e["detection_method"],
         "weight": e.get("confidence_weight"), "expected": W.get(e["detection_method"])}
        for r in records for e in r["entities"]
        if e["detection_method"] in W and abs(float(e.get("confidence_weight", -1)) - W[e["detection_method"]]) > 1e-9
    ]
    unknown_methods = sorted(set(methods) - set(W))

    # documents in the corpus file itself (independent of the annotation record count)
    gt = L.load_json("ground_truth")
    doc_sections = {k: len(v) for k, v in gt.items() if isinstance(v, list)}
    n_docs_corpus = sum(doc_sections.values())

    observed_sev = {s: sev.get(s, 0) for s in (5, 4, 3, 2)}
    extra_sev = {s: c for s, c in sev.items() if s not in (5, 4, 3, 2)}

    checks = {
        "n_annotation_records_is_155": n_records == TARGET_DOCS,
        "n_documents_in_corpus_is_155": n_docs_corpus == TARGET_DOCS,
        "n_entities_is_2190": len(entities) == TARGET_ENTITIES,
        "severity_dist_matches_135_865_490_700": observed_sev == TARGET_SEVERITY_DIST,
        "metadata_total_annotations_agrees": meta.get("total_annotations") == n_records,
        "metadata_total_entities_agrees": meta.get("total_entities") == len(entities),
        "no_confidence_weight_violations": not weight_violations,
        "no_unknown_detection_methods": not unknown_methods,
    }
    return {
        "method": "recount of committed data/ground_truth/*.json (generator NOT re-run; "
                  "invariant 3 freezes these files -- seed-42 regeneration deferred to A6)",
        "files": {k: L.file_stat(k) for k in ("ground_truth", "annotations", "gt_index")},
        "n_annotation_records": n_records,
        "n_documents_in_corpus_file": n_docs_corpus,
        "corpus_sections": doc_sections,
        "n_entities": len(entities),
        "severity_distribution_observed": observed_sev,
        "severity_distribution_target": TARGET_SEVERITY_DIST,
        "severity_values_outside_2_5": extra_sev,
        "n_distinct_entity_types_in_corpus": len(types),
        "entity_spec_count_metadata": meta.get("entity_spec_count"),
        "detection_method_histogram": dict(methods.most_common()),
        "confidence_weight_violations": weight_violations[:20],
        "n_confidence_weight_violations": len(weight_violations),
        "unknown_detection_methods": unknown_methods,
        "checks": checks,
        "RESULT": "PASS" if all(checks.values()) else "FAIL",
    }


# ------------------------------------------------------------------ SC2
def sc2_baseline():
    """Baseline strict ASR from the ORIGINAL frozen logs, and per-run decomposition."""
    rows = L.load_jsonl("orig_clean") + L.load_jsonl("orig_poison")
    runs = sorted({r.get("run_index") for r in rows})
    turns_by_run = Counter(r.get("run_index") for r in rows)
    run_ids = sorted({r.get("run_id") for r in rows})

    # --- the published path: locked verdicts, run 0 (this is the GUARD) ---
    vfn = L.locked_verdict_fn()
    guard = L.score(rows, vfn, run_filter=0)
    guard_misses = vfn.misses["n"]

    checks = {
        "engine_strict_reproduces_0.192": close(guard["engine_strict"], 0.1923, 5e-4),
        "judged_strict_reproduces_0.288": close(guard["judged_strict"], 0.2885, 5e-4),
        "engine_incl_reproduces_0.4808": close(guard["engine_incl"], 0.4808, 5e-4),
        "judged_incl_reproduces_0.5577": close(guard["judged_incl"], 0.5577, 5e-4),
        "n_scenarios_is_52": guard["n_scenarios"] == 52,
        "no_locked_verdict_misses_on_run0": guard_misses == 0,
    }

    # --- A2 crux: per-run engine ASR on the SAME frozen log ---
    # Judged per-run is only meaningful if locked verdicts exist for runs 1 and 2. The
    # published lookup hard-codes run_index 0 into the key, so run 1/2 would silently reuse
    # run 0's verdict. strict=True makes the absence visible instead.
    locked_rows = L.load_jsonl("locked_verdicts")
    locked_run_idx = Counter((v.get("run_id"), v.get("run_index")) for v in locked_rows)
    judged_runs_available = sorted({v.get("run_index") for v in locked_rows})

    per_run = {}
    for ri in runs:
        sfn = L.locked_verdict_fn(strict_run_index=ri)
        s = L.score(rows, sfn, run_filter=ri)
        s["_locked_verdict_misses_strict"] = sfn.misses["n"]
        s["_judged_trustworthy"] = sfn.misses["n"] == 0
        per_run[str(ri)] = s

    engine_by_run = {k: v["engine_strict"] for k, v in per_run.items()}
    engine_incl_by_run = {k: v["engine_incl"] for k, v in per_run.items()}
    identical_engine = len(set(engine_by_run.values())) == 1

    # per-scenario across-run engine agreement (the "leaked in 0/3,1/3,2/3,3/3" distribution)
    scen_runs = defaultdict(dict)
    for r in rows:
        ri, sid = r.get("run_index"), r["scenario_id"]
        scen_runs[sid][ri] = max(scen_runs[sid].get(ri, 0), L.engine_strict_turn(r))
    agree = Counter(sum(v.values()) for v in scen_runs.values() if len(v) == len(runs))
    n_full = sum(1 for v in scen_runs.values() if len(v) == len(runs))

    return {
        "source": "canonical candidate: experiment_logs/B2_CLEAN_main-w3.jsonl + "
                  "B2_POISONED_poisoned-w4.jsonl (frozen, invariant 3)",
        "files": {k: L.file_stat(k) for k in ("orig_clean", "orig_poison", "locked_verdicts")},
        "n_turn_records": len(rows),
        "run_ids": run_ids,
        "run_indices_present": runs,
        "turns_per_run": {str(k): v for k, v in sorted(turns_by_run.items())},
        "published_path_run0": guard,
        "published_targets": L.COMMITTED_C00000,
        "checks": checks,
        "RESULT": "PASS" if all(checks.values()) else "FAIL",
        "a2_per_run": {
            "note": "engine columns are trustworthy for every run. judged columns are only "
                    "trustworthy where _locked_verdict_misses_strict == 0.",
            "locked_verdict_run_indices_present": judged_runs_available,
            "locked_verdict_rows_by_run_id_and_index": {f"{k[0]}|run{k[1]}": v
                                                        for k, v in sorted(locked_run_idx.items())},
            "per_run": per_run,
            "engine_strict_by_run": engine_by_run,
            "engine_incl_by_run": engine_incl_by_run,
            "engine_strict_identical_across_runs": identical_engine,
            "per_scenario_engine_agreement_k_of_n": {f"{k}/{len(runs)}": v
                                                     for k, v in sorted(agree.items())},
            "n_scenarios_with_all_runs": n_full,
        },
    }


# ------------------------------------------------------------------ SC3
def sc3_full_stack():
    """Full-stack (C11111) strict ASR recomputed from the ablation raw records."""
    eng_dir = os.path.join(L.ROOT, L.P["ablation_engine_dir"])
    cache = L.load_jsonl("ablation_judge_cache")

    configs = {}
    for fn in sorted(os.listdir(eng_dir)):
        if not fn.endswith(".jsonl"):
            continue
        # NB: C00000_anchor.jsonl is NOT the C00000 baseline cell. It is the F1 GUARD
        # anchor (9 scenarios) used to prove the defense wrapper reproduces Phase-2
        # behaviour. The real C00000 is the reused frozen Phase-2 baseline, scored in SC2.
        cid = fn[:-6]
        rel = os.path.join(L.P["ablation_engine_dir"], fn)
        rows = L.load_jsonl(rel)
        vfn = L.cache_verdict_fn(cache)
        s = L.score(rows, vfn, run_filter=None)
        runs = Counter(r.get("run_index") for r in rows)
        # characterise the cache misses: a miss scores as (0,0), so it can only ever
        # understate leakage. Report what the missed turns look like.
        missed = []
        for r in rows:
            if L.judge_key(r["attacker_profile"], r["response"]) not in {e["_judge_key"] for e in cache}:
                missed.append({"scenario_id": r["scenario_id"], "turn_index": r["turn_index"],
                               "response_len": len(r["response"]),
                               "response_empty": not r["response"].strip(),
                               "engine_strict": L.engine_strict_turn(r)})
        configs[cid] = {
            "file": rel,
            "is_full_ablation_cell": len(rows) == 89,
            "n_turn_records": len(rows),
            "run_indices": {str(k): v for k, v in sorted(runs.items())},
            "n_runs": len(runs),
            "scored": s,
            "judge_cache_misses": vfn.misses["n"],
            "judge_cache_hit_rate": round(1 - vfn.misses["n"] / max(len(rows), 1), 4),
            "missed_turns": missed,
            "n_missed_turns_with_engine_leak": sum(1 for m in missed if m["engine_strict"]),
            "has_retrieved_doc_ids": all("retrieved_doc_ids" in r for r in rows),
            "has_response_text": all("response" in r for r in rows),
        }

    c11 = configs.get("C11111", {}).get("scored", {})
    checks = {
        "C11111_present": "C11111" in configs,
        "C11111_engine_strict_is_0.000": close(c11.get("engine_strict"), 0.0, 5e-4),
        "C11111_judged_strict_is_0.173": close(c11.get("judged_strict"), 0.1731, 5e-4),
        "C11111_n_scenarios_is_52": c11.get("n_scenarios") == 52,
    }
    knee = configs.get("C01100", {}).get("scored", {})
    checks["C01100_judged_strict_is_0.192"] = close(knee.get("judged_strict"), 0.1923, 5e-4)

    return {
        "source": "results/phase3/ablation/engine/*.jsonl scored against "
                  "results/phase3/ablation/judged/judge_cache.jsonl by the canonical scorer",
        "judge_cache": L.file_stat("ablation_judge_cache"),
        "n_judge_cache_entries": len(cache),
        "configs": configs,
        "checks": checks,
        "RESULT": "PASS" if all(checks.values()) else "FAIL",
    }


def main():
    scorer_guard = L.verify_scorer_matches_published()
    sc1, sc2, sc3 = sc1_corpus(), sc2_baseline(), sc3_full_stack()
    result = {
        "_provenance": L.provenance(__file__),
        "_purpose": "TASK_SPEC §3.2 sanity checks + Amendment 3(c) canonicity gate, "
                    "recomputed from raw committed artifacts.",
        "scorer_fidelity_guard": scorer_guard,
        "SC1_corpus": sc1,
        "SC2_baseline_asr": sc2,
        "SC3_full_stack_asr": sc3,
        "OVERALL": {
            "SC1": sc1["RESULT"], "SC2": sc2["RESULT"], "SC3": sc3["RESULT"],
            "scorer_mirror_faithful": scorer_guard["all_match"],
        },
    }
    out = L.write_out("p0_sanity_checks.json", result)

    print(f"scorer mirror faithful: {scorer_guard['all_match']}  {scorer_guard['checks']}")
    print(f"\n[SC1] corpus -> {sc1['RESULT']}")
    print(f"  docs={sc1['n_documents_in_corpus_file']} records={sc1['n_annotation_records']} "
          f"entities={sc1['n_entities']}")
    print(f"  severity {sc1['severity_distribution_observed']} vs target {TARGET_SEVERITY_DIST}")
    print(f"  weight violations={sc1['n_confidence_weight_violations']} "
          f"distinct types in corpus={sc1['n_distinct_entity_types_in_corpus']}")
    print(f"\n[SC2] baseline -> {sc2['RESULT']}")
    print(f"  run0 published path: {sc2['published_path_run0']}")
    print(f"  targets:             {sc2['published_targets']}")
    a2 = sc2["a2_per_run"]
    print(f"  turns/run: {sc2['turns_per_run']}   locked verdicts exist for run_index "
          f"{a2['locked_verdict_run_indices_present']}")
    for ri, s in a2["per_run"].items():
        print(f"    run{ri}: engine_strict={s['engine_strict']} engine_incl={s['engine_incl']} "
              f"judged_strict={s['judged_strict']} (verdict misses={s['_locked_verdict_misses_strict']}, "
              f"judged trustworthy={s['_judged_trustworthy']})")
    print(f"  engine identical across runs: {a2['engine_strict_identical_across_runs']}")
    print(f"  per-scenario engine agreement: {a2['per_scenario_engine_agreement_k_of_n']}")
    print(f"\n[SC3] full stack -> {sc3['RESULT']}")
    for cid, c in sorted(sc3["configs"].items()):
        s = c["scored"]
        print(f"  {cid}: n={c['n_turn_records']} runs={c['n_runs']} scen={s['n_scenarios']} "
              f"engine_strict={s['engine_strict']} judged_strict={s['judged_strict']} "
              f"cache_miss={c['judge_cache_misses']}")
    print(f"  checks: {sc3['checks']}")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
