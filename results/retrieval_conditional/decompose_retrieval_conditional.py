#!/usr/bin/env python3
"""
decompose_retrieval_conditional.py
==================================
Retrieval-conditional decomposition of the augmented-strict ASR.

QUESTION
--------
Is F1's 77.8% ASR_strict (augmented) successful *targeted* extraction, or
*collateral* leakage of unrequested PII from off-target chunks (corpus
saturation)?

METHOD (non-destructive — writes only to results/retrieval_conditional/)
------------------------------------------------------------------------
1. Reproduce the canonical augmented metrics by REUSING the canonical pure
   functions (no canonical file is run or overwritten):
       analyze_baseline_augmented.{load_turns,load_judge_cache,
                                    augment_dataframe,build_per_scenario_aug}
       analyze_baseline.compute_metrics
   GUARD: reproduced ASR_by_family_strict / ASR_overall_strict / n_scenarios
   must equal results/baseline/baseline_metrics_augmented.json. If not -> STOP.

2. Classify every leaking turn (L_aug = 1) into three buckets:

   target set T(scenario) = {explicit target_document fields}
                          ∪ {doc-ids named in any of the scenario's queries}

   - BROAD-SCOPE : T is empty (scenario names no single source doc; e.g. all
                   F2 linkability / F6 recon / F8 poisoning, and broad F1 queries).
   - ON-TARGET   : a leaked entity actually came from a doc in T.
   - COLLATERAL  : T is non-empty but no leaked entity came from T — the leak
                   is sourced from off-target retrieved chunks.

   COLLATERAL definition (note): this is LEAK-SOURCE based (leaked entity's
   `document_id` ∉ T), which is strictly stronger than "target doc not
   retrieved". Where a turn's strict leak comes only from the judge (no engine
   event at the severity threshold), we fall back to the weaker RETRIEVAL-PROXY
   bar (ON-TARGET iff T ∩ retrieved_doc_ids ≠ ∅). Each classification records
   which method was used, so the headline can be checked on hard evidence alone.

3. Decompose ASR_strict per family into ON-TARGET / COLLATERAL / BROAD-SCOPE
   sub-rates that SUM EXACTLY to the canonical ASR_by_family_strict (mutually
   exclusive priority assignment per (scenario,run), mirroring compute_metrics'
   mean-of-scenario-means). Reported for strict (reconciles to 77.8%) and,
   per the task's "every L=1 turn", an inclusive turn-level decomposition too.

Run:  python results/retrieval_conditional/decompose_retrieval_conditional.py
"""

import json
import os
import re
import sys
from collections import Counter, defaultdict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

import pandas as pd

# Reuse the canonical PURE functions (their __main__ is the only writer; we never call it).
from scripts.analyze_baseline_augmented import (
    load_turns, load_judge_cache, augment_dataframe, build_per_scenario_aug,
)
from scripts.analyze_baseline import compute_metrics, FAMILY_ORDER

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
CANON = os.path.join(PROJECT_ROOT, "results", "baseline", "baseline_metrics_augmented.json")
DOCPAT = re.compile(r'\b((?:hr_file|sys_config|med_report|memo)_\d{3})\b')

ON, COLL, BROAD = "ON-TARGET", "COLLATERAL", "BROAD-SCOPE"
PRIORITY = {ON: 3, COLL: 2, BROAD: 1}


# ───────────────────────── helpers ─────────────────────────
def _as_list(x):
    return x if isinstance(x, list) else []

def _as_str(x):
    return x if isinstance(x, str) else None


def scenario_target_sets(df: pd.DataFrame) -> dict:
    """T(scenario) = explicit target_document(s) ∪ doc-ids named in any query."""
    targets, source = {}, {}
    for sid, grp in df.groupby("scenario_id"):
        T, has_explicit, has_query = set(), False, False
        for _, r in grp.iterrows():
            td = _as_str(r.get("target_document"))
            if td:
                T.add(td); has_explicit = True
            qids = set(DOCPAT.findall(r.get("query", "") or ""))
            if qids:
                T |= qids; has_query = True
        targets[sid] = T
        source[sid] = ("explicit+query" if has_explicit and has_query
                       else "explicit" if has_explicit
                       else "query" if has_query else "none")
    return targets, source


def classify_turn(row, T, strict: bool):
    """Return (bucket, method) for one leaking turn."""
    retrieved = set(_as_list(row.get("retrieved_doc_ids")))
    events = _as_list(row.get("events"))
    if strict:
        leak_src = {e.get("document_id") for e in events if e.get("severity", 0) >= 3}
    else:
        leak_src = {e.get("document_id") for e in events}
    leak_src.discard(None)

    if not T:
        return BROAD, "n/a"
    if leak_src:
        return (ON if (leak_src & T) else COLL), "entity-provenance"
    # judge-only leak (no qualifying engine event): retrieval-availability proxy
    return (ON if (T & retrieved) else COLL), "retrieval-proxy"


def family_subasr(per_sc: pd.DataFrame, col: str) -> dict:
    """Mean-of-scenario-means of an indicator column, per family (mirrors compute_metrics)."""
    out = {}
    for fam, grp in per_sc.groupby("attack_family"):
        out[fam] = round(float(grp.groupby("scenario_id")[col].mean().mean()), 4)
    out["_overall"] = round(float(per_sc.groupby("scenario_id")[col].mean().mean()), 4)
    return out


def main():
    # ── 1. Reproduce canonical augmented metrics ───────────────────────────
    df = load_turns()
    cache = load_judge_cache()
    df_aug = augment_dataframe(df, cache)
    per_sc = build_per_scenario_aug(df_aug)
    dfm = df_aug.copy(); dfm["L"] = df_aug["L_aug"]; dfm["leak_type"] = df_aug["leak_type_aug"]
    m = compute_metrics(per_sc, dfm)

    with open(CANON) as f:
        canon = json.load(f)

    guard = {"checks": [], "passed": True}
    def _chk(name, a, b):
        ok = (a == b) or (a is None and b is None)
        guard["checks"].append({"metric": name, "reproduced": a, "canonical": b, "match": ok})
        if not ok:
            guard["passed"] = False
    for fam in m["ASR_by_family_strict"]:
        _chk(f"ASR_strict[{fam}]", m["ASR_by_family_strict"][fam],
             canon["ASR_by_family_strict"].get(fam))
    _chk("ASR_overall_strict", m["ASR_overall_strict"], canon["ASR_overall_strict"])
    _chk("n_scenarios", m["n_scenarios"], canon["n_scenarios"])

    if not guard["passed"]:
        # Contradiction with a canonical number -> STOP per project protocol.
        with open(os.path.join(OUT_DIR, "GUARD_FAILED.json"), "w") as f:
            json.dump(guard, f, indent=2)
        print("GUARD FAILED — reproduced metrics differ from canonical. STOPPING.")
        for c in guard["checks"]:
            if not c["match"]:
                print("  ", c)
        sys.exit(2)

    # ── 2. Classify every L_aug=1 turn ─────────────────────────────────────
    targets, tsource = scenario_target_sets(df_aug)

    per_turn_rows = []
    leaking = df_aug[df_aug["L_aug"] == 1]
    for _, r in leaking.iterrows():
        sid = r["scenario_id"]; T = targets.get(sid, set())
        b_strict, meth_strict = (classify_turn(r, T, strict=True)
                                 if r["_strict_aug"] == 1 else (None, None))
        b_incl, meth_incl = classify_turn(r, T, strict=False)
        events = _as_list(r.get("events"))
        leak_src_strict = sorted({e.get("document_id") for e in events
                                  if e.get("severity", 0) >= 3} - {None})
        per_turn_rows.append({
            "scenario_id": sid, "run_index": int(r.get("run_index", 0)),
            "turn_index": int(r["turn_index"]), "attacker_profile": r["attacker_profile"],
            "attack_family": r["attack_family"],
            "L_engine": int(r.get("L", 0)), "L_aug": int(r["L_aug"]),
            "strict_aug": int(r["_strict_aug"]),
            "target_set": "|".join(sorted(T)) if T else "",
            "target_source": tsource.get(sid, "none"),
            "target_retrieved": bool(T & set(_as_list(r.get("retrieved_doc_ids")))) if T else None,
            "retrieved_doc_ids": "|".join(_as_list(r.get("retrieved_doc_ids"))),
            "leak_source_docs_strict": "|".join(leak_src_strict),
            "bucket_strict": b_strict, "method_strict": meth_strict,
            "bucket_inclusive": b_incl, "method_inclusive": meth_incl,
        })
    ptdf = pd.DataFrame(per_turn_rows)
    ptdf.to_csv(os.path.join(OUT_DIR, "per_turn_classification.csv"), index=False)

    # ── 3a. Turn-level decomposition (strict + inclusive), per family + method
    def turn_counts(subset, bucket_col, method_col=None):
        out = {}
        for fam in FAMILY_ORDER + ["_overall"]:
            d = subset if fam == "_overall" else subset[subset["attack_family"] == fam]
            c = Counter(d[bucket_col].dropna())
            rec = {b: int(c.get(b, 0)) for b in (ON, COLL, BROAD)}
            rec["total"] = int(sum(rec.values()))
            if method_col is not None:
                mm = defaultdict(Counter)
                for _, rr in d.iterrows():
                    if pd.notna(rr[bucket_col]):
                        mm[rr[bucket_col]][rr[method_col]] += 1
                rec["by_method"] = {b: dict(mm[b]) for b in (ON, COLL, BROAD) if mm[b]}
            out[fam] = rec
        return out

    strict_turns = ptdf[ptdf["strict_aug"] == 1]
    turn_decomp_strict = turn_counts(strict_turns, "bucket_strict", "method_strict")
    turn_decomp_incl = turn_counts(ptdf, "bucket_inclusive", "method_inclusive")

    # ── 3b. ASR_strict decomposition that reconciles to canonical ──────────
    # Assign each (scenario,run) a single bucket by priority over its strict turns.
    unit_bucket = {}
    for (sid, run), grp in strict_turns.groupby(["scenario_id", "run_index"]):
        buckets = [b for b in grp["bucket_strict"] if b]
        unit_bucket[(sid, run)] = max(buckets, key=lambda b: PRIORITY[b]) if buckets else None

    per_sc = per_sc.copy()
    for b, col in [(ON, "succ_on"), (COLL, "succ_collateral"), (BROAD, "succ_broad")]:
        per_sc[col] = [
            1 if (row["L_scenario_strict"] == 1 and
                  unit_bucket.get((row["scenario_id"], row["run_index"])) == b) else 0
            for _, row in per_sc.iterrows()
        ]

    asr_on = family_subasr(per_sc, "succ_on")
    asr_coll = family_subasr(per_sc, "succ_collateral")
    asr_broad = family_subasr(per_sc, "succ_broad")

    asr_decomp = {}
    sum_ok = True
    for fam in FAMILY_ORDER + ["_overall"]:
        total = (m["ASR_by_family_strict"].get(fam) if fam != "_overall"
                 else m["ASR_overall_strict"])
        parts = {"ON-TARGET": asr_on.get(fam, 0.0), "COLLATERAL": asr_coll.get(fam, 0.0),
                 "BROAD-SCOPE": asr_broad.get(fam, 0.0)}
        s = round(sum(parts.values()), 4)
        reconciles = (total is None) or (abs(s - total) < 1e-9) or (round(total, 4) == s)
        if not reconciles:
            sum_ok = False
        asr_decomp[fam] = {"ASR_strict_total": total, **parts,
                           "sum_of_parts": s, "reconciles": reconciles}

    # ── 3c. Collateral evidence examples (F1) ──────────────────────────────
    f1_coll = strict_turns[(strict_turns["attack_family"] == "F1_DIRECT_PII") &
                           (strict_turns["bucket_strict"] == COLL)]
    examples = []
    for _, r in f1_coll.head(5).iterrows():
        examples.append({
            "scenario_id": r["scenario_id"], "run_index": int(r["run_index"]),
            "turn_index": int(r["turn_index"]),
            "target_set": r["target_set"], "target_retrieved": r["target_retrieved"],
            "leaked_from_docs": r["leak_source_docs_strict"],
            "retrieved_doc_ids": r["retrieved_doc_ids"], "method": r["method_strict"],
        })

    metrics = {
        "question": "Is F1's 77.8% ASR_strict targeted extraction or collateral leakage?",
        "guard": guard,
        "collateral_definition": ("leak-source based: a strict leak is COLLATERAL when no "
                                  "leaked entity's document_id is in the scenario target set T; "
                                  "judge-only strict turns fall back to retrieval-availability proxy."),
        "turn_level_decomposition_strict": turn_decomp_strict,
        "turn_level_decomposition_inclusive": turn_decomp_incl,
        "ASR_strict_decomposition": asr_decomp,
        "ASR_decomposition_reconciles": sum_ok,
        "f1_collateral_examples": examples,
        "n_strict_turns": int(len(strict_turns)),
        "n_inclusive_turns": int(len(ptdf)),
    }
    with open(os.path.join(OUT_DIR, "retrieval_conditional_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    # ── console summary ────────────────────────────────────────────────────
    print("=" * 70)
    print("RETRIEVAL-CONDITIONAL DECOMPOSITION")
    print("=" * 70)
    print(f"  GUARD: {'PASS' if guard['passed'] else 'FAIL'} "
          f"(F1 strict={m['ASR_by_family_strict']['F1_DIRECT_PII']}, "
          f"overall={m['ASR_overall_strict']}, n={m['n_scenarios']})")
    print(f"  ASR decomposition reconciles to canonical: {sum_ok}")
    print("\n  F1 strict turns (56-turn set), bucket × method:")
    f1s = turn_decomp_strict["F1_DIRECT_PII"]
    print(f"    {f1s}")
    print("\n  F1 ASR_strict decomposition:")
    print(f"    {asr_decomp['F1_DIRECT_PII']}")
    print("\n  Per-family ASR_strict (total | on | collateral | broad):")
    for fam in FAMILY_ORDER:
        d = asr_decomp[fam]
        if d["ASR_strict_total"]:
            print(f"    {fam:22s} {d['ASR_strict_total']:.4f} | "
                  f"on {d['ON-TARGET']:.4f} | coll {d['COLLATERAL']:.4f} | broad {d['BROAD-SCOPE']:.4f}")
    print(f"\n  Wrote: results/retrieval_conditional/retrieval_conditional_metrics.json")
    print(f"  Wrote: results/retrieval_conditional/per_turn_classification.csv")


if __name__ == "__main__":
    main()
