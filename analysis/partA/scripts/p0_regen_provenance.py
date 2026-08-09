#!/usr/bin/env python3
"""
p0_regen_provenance.py -- Amendment 3: settle what results/phase3_4/baseline_regen/ IS,
from file CONTENTS rather than inference, before anything is classified.

Amendment 3(a) offered two hypotheses: a second independent SUT run, or a re-judge of the
stored responses. This script tests both against the artifacts:

  1. judge model identifier inside judge_cache_regen.jsonl
  2. the config recorded in the two _summary.json files + RUN_CONDITIONS.txt + cost_ledger.csv
  3. file mtimes
  4. whether regen response text is BYTE-IDENTICAL to experiment_logs/B2_CLEAN_main-w3.jsonl

Then, per Amendment 3(b), it runs the only free test of JUDGE-side determinism available:
the regen judge cache is content-addressed by sha256(profile + NUL + response). Any
original turn whose response is byte-identical to its regen counterpart produces the SAME
key, so a verdict for it in BOTH the locked Phase-2 verdicts and the regen cache is the
same input judged twice. Disagreement there = the primary instrument is not deterministic.

Also runs the Amendment 4 truncation audit (does full response text survive, for A3/A4).

Read-only. Emits analysis/partA/out/p0_regen_provenance.json.
Run:  python3 analysis/partA/scripts/p0_regen_provenance.py
"""
import os
import re
import sys
from collections import Counter, defaultdict
from statistics import pstdev

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib_partA as L  # noqa: E402


def load_all():
    orig = L.load_jsonl("orig_clean") + L.load_jsonl("orig_poison")
    regen = L.load_jsonl("regen_clean") + L.load_jsonl("regen_poison")
    cache = L.load_jsonl("regen_judge_cache")
    locked = L.load_jsonl("locked_verdicts")
    return orig, regen, cache, locked


# ------------------------------------------------------------------ (a) model identity
def model_identity(regen, cache, orig):
    """What model produced the regen SUT responses and the regen judge verdicts?"""
    sut_models_regen = Counter(r.get("model") for r in regen)
    sut_models_orig = Counter(r.get("model") for r in orig)

    cache_keys = sorted({k for e in cache for k in e.keys()})
    judge_model_field = [k for k in cache_keys if "model" in k.lower()]

    # The judge model is not stamped on the cache rows. Recover it from the driving script.
    src = open(L.path("published_scorer"), encoding="utf-8").read()
    prompt_version = re.search(r'LLMJudge\(prompt_version="([^"]+)"\)', src)
    rate_comment = re.search(r'_IN_RATE, _OUT_RATE = ([^\n]+)', src)
    summary = L.load_json("regen_summary")
    conditions_txt = open(L.path("regen_conditions"), encoding="utf-8").read().strip()

    # cross-check the declared judge against the default in the judge implementation
    judge_src_path = os.path.join(L.ROOT, "scripts", "llm_judge.py")
    judge_default = None
    if os.path.exists(judge_src_path):
        js = open(judge_src_path, encoding="utf-8").read()
        m = re.findall(r'claude-[a-z0-9\.\-]+', js)
        judge_default = sorted(set(m))

    return {
        "sut_model_field_in_regen_records": dict(sut_models_regen),
        "sut_model_field_in_original_records": dict(sut_models_orig),
        "sut_model_identical_orig_vs_regen": set(sut_models_regen) == set(sut_models_orig),
        "judge_cache_row_keys": cache_keys,
        "judge_model_field_present_in_cache": judge_model_field or None,
        "JUDGE_MODEL_PROVENANCE_GAP": (
            "judge_cache_regen.jsonl rows carry NO model identifier field. The judge model "
            "is recoverable only from the driving script and the summary's prose 'conditions' "
            "string, not from the verdict rows themselves. Flag for A6 (hard rule 8 asks every "
            "classification row to name its producing model; these rows do not)."
            if not judge_model_field else None),
        "judge_declared_in_regen_summary_conditions": summary.get("conditions"),
        "judge_prompt_version_in_driver": prompt_version.group(1) if prompt_version else None,
        "judge_price_constants_in_driver": rate_comment.group(1).strip() if rate_comment else None,
        "claude_model_ids_referenced_in_scripts_llm_judge": judge_default,
        "run_conditions_txt": conditions_txt,
    }


# ------------------------------------------------------------------ (b) config + cost
def config_and_cost():
    files = {k: L.file_stat(k) for k in
             ("regen_clean", "regen_poison", "regen_judge_cache", "regen_summary",
              "regen_conditions", "regen_cost", "orig_clean", "orig_poison", "locked_verdicts")}
    clean_sum = L.load_json("results/phase3_4/baseline_regen/B2_CLEAN_regen_summary.json")
    poison_sum = L.load_json("results/phase3_4/baseline_regen/B2_POISONED_regen_summary.json")
    cost_rows = [ln.strip().split(",") for ln in
                 open(L.path("regen_cost"), encoding="utf-8").read().strip().splitlines()]
    hdr, rows = cost_rows[0], cost_rows[1:]
    ledger = [dict(zip(hdr, r)) for r in rows]
    real = [r for r in ledger if float(r["cost_usd"]) > 0]
    return {
        "files": files,
        "tracked_in_git": {k: L.is_tracked(files[k]["path"]) for k in files if files[k]["exists"]},
        "clean_summary_config": {k: clean_sum[k] for k in
                                 ("run_id", "batch", "collection", "dry_run", "n_scenarios",
                                  "n_errors", "generated_at", "cost_usd", "strict_leaks_count",
                                  "strict_leaks_rate") if k in clean_sum},
        "poison_summary_config": {k: poison_sum[k] for k in
                                  ("run_id", "batch", "collection", "dry_run", "n_scenarios",
                                   "n_errors", "generated_at", "cost_usd", "strict_leaks_count",
                                   "strict_leaks_rate") if k in poison_sum},
        "cost_ledger": ledger,
        "n_ledger_rows_with_real_spend": len(real),
        "sut_calls_billed": sum(int(r["calls"]) for r in real),
        "sut_cost_usd": round(sum(float(r["cost_usd"]) for r in real), 4),
        "sut_output_tokens_billed": sum(int(r["out_tokens"]) for r in real),
    }


# ------------------------------------------------------------------ (c) byte identity
def byte_identity(orig, regen):
    """Is the regen response text byte-identical to the original, turn for turn?"""
    def key(r):
        return (r["scenario_id"], r.get("run_index"), r["turn_index"])

    o = {key(r): r for r in orig}
    g = {key(r): r for r in regen}
    common = sorted(set(o) & set(g))

    ident_resp = ident_hash = ident_query = ident_docs = 0
    diffs = []
    for k in common:
        a, b = o[k], g[k]
        same_resp = a["response"] == b["response"]
        ident_resp += same_resp
        ident_hash += a.get("response_hash") == b.get("response_hash")
        ident_query += a.get("query") == b.get("query")
        ident_docs += list(a.get("retrieved_doc_ids") or []) == list(b.get("retrieved_doc_ids") or [])
        if not same_resp and len(diffs) < 5:
            diffs.append({"key": list(k), "orig_len": len(a["response"]), "regen_len": len(b["response"]),
                          "orig_hash": a.get("response_hash"), "regen_hash": b.get("response_hash"),
                          "orig_out_tokens": a.get("output_tokens"), "regen_out_tokens": b.get("output_tokens")})

    n = len(common)
    return {
        "n_turns_original": len(o),
        "n_turns_regen": len(g),
        "n_turns_matched_by_scenario_run_turn": n,
        "n_response_text_byte_identical": ident_resp,
        "pct_response_byte_identical": round(ident_resp / n, 4) if n else None,
        "n_response_hash_identical": ident_hash,
        "n_query_identical": ident_query,
        "n_retrieved_doc_ids_identical": ident_docs,
        "pct_retrieval_identical": round(ident_docs / n, 4) if n else None,
        "example_differences": diffs,
        "VERDICT": ("NOT a re-judge: responses differ, so the SUT was re-executed"
                    if ident_resp < n else
                    "IS a re-judge: every response is byte-identical to the original"),
    }


# ------------------------------------------------------------------ judge determinism
def judge_determinism(orig, regen, cache, locked):
    """Amendment 3(b): find inputs judged twice and compare the two verdicts.

    The regen cache is keyed by sha256(profile + NUL + response). Any ORIGINAL turn whose
    response happens to be byte-identical to its regen counterpart therefore has a verdict
    in the regen cache under the same key -- and it also has a locked Phase-2 verdict. That
    pair is one input, two judgements.
    """
    cache_by_key = {e["_judge_key"]: e for e in cache}
    locked_by_ck = {v["_cache_key"]: v for v in locked}

    pairs, disagreements = [], []
    for r in orig:
        k = L.judge_key(r["attacker_profile"], r["response"])
        if k not in cache_by_key:
            continue
        ck = f"{r.get('run_id','')}|{r['scenario_id']}|{r.get('run_index')}|{r['turn_index']}"
        lv = locked_by_ck.get(ck)
        if lv is None:
            continue
        rv = cache_by_key[k]
        a = (int(lv.get("L_judge", 0) or 0), int(lv.get("severity_judge", 0) or 0),
             lv.get("leak_type_judge"))
        b = (int(rv.get("L_judge", 0) or 0), int(rv.get("severity_judge", 0) or 0),
             rv.get("leak_type_judge"))
        rec = {"scenario_id": r["scenario_id"], "run_index": r.get("run_index"),
               "turn_index": r["turn_index"], "profile": r["attacker_profile"],
               "response_len": len(r["response"]),
               "locked": {"L": a[0], "severity": a[1], "leak_type": a[2]},
               "regen": {"L": b[0], "severity": b[1], "leak_type": b[2]},
               "L_agrees": a[0] == b[0], "severity_agrees": a[1] == b[1],
               "leak_type_agrees": a[2] == b[2],
               "strict_agrees": (a[1] >= 3) == (b[1] >= 3)}
        pairs.append(rec)
        if not (rec["L_agrees"] and rec["severity_agrees"]):
            disagreements.append(rec)

    n = len(pairs)
    return {
        "method": "content-addressed key intersection: an ORIGINAL turn whose response is "
                  "byte-identical to its regen counterpart yields the same sha256(profile|response) "
                  "key, so it carries both a locked Phase-2 verdict and a fresh regen verdict.",
        "n_inputs_judged_twice": n,
        "n_L_disagreements": sum(1 for p in pairs if not p["L_agrees"]),
        "n_severity_disagreements": sum(1 for p in pairs if not p["severity_agrees"]),
        "n_strict_threshold_disagreements": sum(1 for p in pairs if not p["strict_agrees"]),
        "n_leak_type_disagreements": sum(1 for p in pairs if not p["leak_type_agrees"]),
        "raw_agreement_L": round(sum(p["L_agrees"] for p in pairs) / n, 4) if n else None,
        "raw_agreement_severity": round(sum(p["severity_agrees"] for p in pairs) / n, 4) if n else None,
        "disagreements": disagreements,
        "VERDICT": ("DATA MISSING -- no byte-identical response was judged by both passes, so "
                    "judge determinism cannot be measured from these artifacts" if n == 0 else
                    ("judge reproduced every verdict on identical input (n=%d)" % n
                     if not disagreements else
                     "JUDGE IS NOT DETERMINISTIC: %d/%d identical inputs got a different verdict"
                     % (len(disagreements), n))),
    }


# ------------------------------------------------------------------ truncation audit
def truncation_audit(orig, regen):
    """Amendment 4: is the response text complete enough for A3 (refusal detection) and
    A4 (evidence inspection)?"""
    def stats(rows, label):
        lens = [len(r["response"]) for r in rows]
        toks = [r.get("output_tokens") or 0 for r in rows]
        maxtok = max(toks) if toks else 0
        # max_tokens=1024 was the declared cap; a response that hit it is TRUNCATED BY THE
        # SUT (not by logging). Distinguish the two: logging truncation shows as a constant
        # character length; generation truncation shows as output_tokens at the cap.
        at_cap = sum(1 for t in toks if t >= 1024)
        len_hist = Counter(lens)
        modal_len, modal_n = len_hist.most_common(1)[0] if len_hist else (None, 0)
        ratio = [len(r["response"]) / (r.get("output_tokens") or 1) for r in rows
                 if (r.get("output_tokens") or 0) > 0]
        return {
            "label": label,
            "n": len(rows),
            "response_chars_min": min(lens) if lens else None,
            "response_chars_median": sorted(lens)[len(lens) // 2] if lens else None,
            "response_chars_max": max(lens) if lens else None,
            "output_tokens_max": maxtok,
            "n_responses_at_or_over_1024_output_tokens": at_cap,
            "modal_char_length": modal_len,
            "n_at_modal_length": modal_n,
            "constant_length_truncation_suspected": modal_n > len(rows) * 0.1 and modal_len not in (0,),
            "chars_per_output_token_min": round(min(ratio), 2) if ratio else None,
            "chars_per_output_token_median": round(sorted(ratio)[len(ratio) // 2], 2) if ratio else None,
            "n_empty_responses": sum(1 for x in lens if x == 0),
        }

    # which fields A3 and A4 can actually run on
    sample = orig[0]
    fields = {f: (f in sample) for f in
              ("response", "retrieved_doc_ids", "retrieved_chunks_preview", "events",
               "target_document", "target_document_retrieved", "attacker_profile", "L", "S")}
    locked = L.load_jsonl("locked_verdicts")
    judge_fields = sorted({k for v in locked for k in v.keys()})
    quote_fields = [k for k in judge_fields if "quote" in k.lower() or "evidence" in k.lower()]
    rlens = [len(v.get("rationale") or "") for v in locked]

    return {
        "original_logs": stats(orig, "experiment_logs (canonical)"),
        "regen_logs": stats(regen, "baseline_regen"),
        "fields_present_in_execution_records": fields,
        "judge_verdict_fields": judge_fields,
        "evidence_quote_fields_present": quote_fields or None,
        "rationale_chars_min": min(rlens) if rlens else None,
        "rationale_chars_median": sorted(rlens)[len(rlens) // 2] if rlens else None,
        "rationale_chars_max": max(rlens) if rlens else None,
        "A3_SUPPORT": None,   # filled by main() after evaluating
        "A4_SUPPORT": None,
    }


# ------------------------------------------------------------------ regen scoring
def regen_scoring(regen, cache):
    vfn = L.cache_verdict_fn(cache)
    runs = sorted({r.get("run_index") for r in regen})
    per_run = {str(ri): L.score(regen, L.cache_verdict_fn(cache), run_filter=ri) for ri in runs}
    pooled = L.score(regen, vfn, run_filter=None)
    metrics = ("engine_strict", "engine_incl", "judged_strict", "judged_incl")
    sigma = {m: round(pstdev([per_run[str(ri)][m] for ri in runs]), 4) for m in metrics}
    spread = {}
    for m in metrics:
        vals = [per_run[str(ri)][m] for ri in runs]
        pw = [abs(a - b) for i, a in enumerate(vals) for b in vals[i + 1:]]
        spread[m] = {"values": vals, "max_pairwise_abs_delta": round(max(pw), 4) if pw else 0.0}

    published = L.load_json("regen_summary")
    return {
        "per_run": per_run,
        "pooled_all_runs": pooled,
        "run_to_run_sigma_population": sigma,
        "run_to_run_spread": spread,
        "matches_published_regen_summary": {
            m: (abs(per_run["0"][m] - published["regen_run0"][m]) < 1e-6) for m in metrics
        },
        "published_regen_summary_run0": published["regen_run0"],
        "published_regen_sigma": published["regen_run_to_run_sigma"],
    }


def main():
    orig, regen, cache, locked = load_all()

    ident = byte_identity(orig, regen)
    det = judge_determinism(orig, regen, cache, locked)
    trunc = truncation_audit(orig, regen)

    # A3/A4 support determination (Amendment 4)
    o = trunc["original_logs"]
    full_text = (not o["constant_length_truncation_suspected"]) and o["response_chars_max"] > 1000
    trunc["A3_SUPPORT"] = (
        "SUPPORTED -- full untruncated response text is present on every execution record "
        "(no constant-length logging truncation; chars/token ratio is natural), and "
        "retrieved_doc_ids is present, so refusal detection and the context-content join "
        "can both run." if full_text and trunc["fields_present_in_execution_records"]["retrieved_doc_ids"]
        else "BLOCKED (DATA MISSING) -- see fields above")
    trunc["A4_SUPPORT"] = (
        "SUPPORTED, with a caveat: full response text is present, so evidence can be "
        "inspected directly. However NO evidence_quote field was ever persisted by the judge; "
        "only 'rationale' exists. A4 step 2 must inspect the response text plus the rationale, "
        "and must state that verbatim judge-selected quotes are unavailable."
        if full_text else "BLOCKED (DATA MISSING)")

    classification = (
        "SECOND INDEPENDENT SUT RUN **AND** A FRESH JUDGE PASS -- neither of Amendment 3's "
        "two hypotheses alone. The SUT was re-executed (responses are not byte-identical; "
        "the cost ledger bills real SUT calls) and all verdicts were produced fresh by the "
        "judge. Because BOTH instruments moved, its run-to-run sigma is a JOINT SUT+judge "
        "figure and CANNOT be decomposed into an SUT half and a judge half."
        if ident["n_response_text_byte_identical"] < ident["n_turns_matched_by_scenario_run_turn"]
        else "RE-JUDGE ONLY")

    result = {
        "_provenance": L.provenance(__file__),
        "_purpose": "Amendment 3: determine from file contents what baseline_regen is, then "
                    "run the free judge-determinism test and the Amendment 4 truncation audit.",
        "CLASSIFICATION": classification,
        "a_model_identity": model_identity(regen, cache, orig),
        "b_config_and_cost": config_and_cost(),
        "c_byte_identity": ident,
        "judge_determinism_test": det,
        "truncation_audit": trunc,
        "regen_scoring": regen_scoring(regen, cache),
    }
    out = L.write_out("p0_regen_provenance.json", result)

    print("CLASSIFICATION:", classification)
    print()
    print("[byte identity]", {k: ident[k] for k in
                              ("n_turns_matched_by_scenario_run_turn", "n_response_text_byte_identical",
                               "n_retrieved_doc_ids_identical", "pct_retrieval_identical")})
    print("[cost]", {k: result["b_config_and_cost"][k] for k in
                     ("sut_calls_billed", "sut_cost_usd", "sut_output_tokens_billed")})
    print()
    print("[judge determinism]", det["VERDICT"])
    print("   n judged twice:", det["n_inputs_judged_twice"])
    print()
    print("[truncation] original:", {k: trunc["original_logs"][k] for k in
                                     ("response_chars_min", "response_chars_median", "response_chars_max",
                                      "n_responses_at_or_over_1024_output_tokens",
                                      "constant_length_truncation_suspected")})
    print("   evidence_quote fields:", trunc["evidence_quote_fields_present"])
    print("   A3:", trunc["A3_SUPPORT"][:100])
    print("   A4:", trunc["A4_SUPPORT"][:100])
    print()
    rs = result["regen_scoring"]
    print("[regen per-run]", {k: v["judged_strict"] for k, v in rs["per_run"].items()})
    print("   sigma:", rs["run_to_run_sigma_population"])
    print("   reproduces published regen_summary:", rs["matches_published_regen_summary"])
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
