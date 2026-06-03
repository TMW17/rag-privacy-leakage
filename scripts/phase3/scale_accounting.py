"""
scale_accounting.py — HONEST query-execution accounting for the project (Task: results/phase3/scale/).

A "query-execution" = ONE SUT (RAG) generation = one turn. Judge/eval LLM calls are NOT
query-executions (reported separately as evaluation overhead). Counting is DEDUP-AWARE:
  * REUSED  = served from Phase-2 logs or the content-addressed SUT cache -> $0, NOT new work.
  * NEW     = a real fresh SUT API call in Phase 3.
Rule: do NOT pad, do NOT present reused turns as new. Big numbers are read from source files;
small unit-test counts are encoded with per-file provenance (filter/retrieval-only tests make 0
SUT calls; only generation tests count).

Outputs: results/phase3/scale/{scale_report.json, SCALE.md} + console print.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "results/phase3/scale")


def wc(path):
    return sum(1 for _ in open(os.path.join(ROOT, path)))


def main():
    os.makedirs(OUT, exist_ok=True)

    # ── file-derived (authoritative) ──
    b_clean = wc("experiment_logs/B2_CLEAN_main-w3.jsonl")          # 246
    b_pois = wc("experiment_logs/B2_POISONED_poisoned-w4.jsonl")    # 21
    baseline_reused = b_clean + b_pois                              # 267 (= 3 runs x 89)

    eng = json.load(open(os.path.join(ROOT, "results/phase3/ablation/engine/ablation_engine_summary.json")))
    ablation_real = eng["real_calls"]                              # 213 fresh SUT (incl. 13-turn drift anchor), dedup-aware
    ablation_dedup = eng["dedup_hit_rate"]
    ablation_cost = eng["sut_cost_usd"]
    defended_scored = 5 * 89                                        # nominal scored turns over the 5 defended configs
    c00000_scored = 89                                             # C00000 scored turns (a REUSED subset of the 267)

    guard = wc("results/phase3/ablation/guard_baseline_f1.jsonl")  # 39 (all-False==baseline reproduction check, separate run)

    util = json.load(open(os.path.join(ROOT, "results/phase3/utility/utility_results.json")))
    util_sut = util["summary"]["_meta"]["sut_calls"]              # 60 (30 benign x C00000,C11111)
    util_judge = util["summary"]["_meta"]["judge_calls"]          # 180 (eval, NOT query-exec)

    judged = json.load(open(os.path.join(ROOT, "results/phase3/ablation/judged/augmented_summary.json")))
    judge_calls_ablation = judged["n_real_judge_calls"]          # 227 (eval, NOT query-exec)

    # ── unit-test fresh SUT (per-file provenance; filter/retrieval-only => 0 SUT) ──
    unit = {
        "L1 input-filter (l1_results)": (0, "input-filter only: regex+NeMo on 2 attacks+3 benign INPUTS, pre-SUT gate; no generation"),
        "L2 collateral": (0, "chunk-level: retrieved_doc_ids[5] + per_chunk_redaction[5] + engine_L on context; no generation"),
        "L2 utility_survivors": (0, "context-level: which sev>=3 survive redaction in the 5 retrieved chunks; no generation"),
        "L2 oracle_killer": (30, "forced-on-target GENERATIONS: 15 L2-ON (per_run[15], all blocked=0.0) + 15 L2-OFF baseline (0.9333=14/15 leaked); constructed oracle attack, both runs fresh"),
        "L3 test1 p1link": (3, "3-turn P1-LINK conversation: per_turn[3] generations"),
        "L3 test2 fp_guard": (3, "3 false-positive-guard queries: per_query[3] generations"),
        "L3 test3 handoff": (1, "1 live forced run (defense_in_depth__live_forced_run); gate test uses a CONSTRUCTED input (0 SUT); +-1"),
        "L4 output-filter (l4_results)": (0, "output-filter applied to a SINGLE source_response (before/after redaction); source reused -> 0 fresh (<=1)"),
        "L5 provenance/acl + f8": (3, "provenance(155 docs) + ACL = index-level 0 SUT; f8_exploit L5_ON_runs[3] = 3 fresh; L5_OFF baseline REUSED from B2_POISONED (not re-run)"),
        "sanitized_tests F1 probe": (1, "sut_probe.sut_calls=1 (direct-PII F1 probe vs sanitized index)"),
        "Task 1.7 confidence/audit": (0, "5 ALREADY-LOGGED Phase-2 turns reused -> 0 new SUT (by design)"),
    }
    unit_sut = sum(n for n, _ in unit.values())                   # 26

    # ── out-of-scope Phase-2 development executions (NOT measurement, NOT reused; shown for full transparency) ──
    dev = {
        "B1 pilot": wc("experiment_logs/B1_PILOT_pilot-B1-w3.jsonl"),     # 17
        "dry-run smoketest": wc("experiment_logs/DRY_RUN_smoketest.jsonl"),       # 17
        "dry-run w3": wc("experiment_logs/DRY_RUN_w3-dryrun-test.jsonl"),  # 17
        "smoke (final-test-v1/v3, rag_*, sanity)": 4,                       # 1+1+1+1
    }
    dev_total = sum(dev.values())

    # ── totals (dedup-aware) ──
    new_phase3 = ablation_real + guard + unit_sut + util_sut       # L6=0, demo=0
    total_real = baseline_reused + new_phase3
    total_incl_dev = total_real + dev_total

    # ── the padding trap (what an inflated count would (wrongly) report) ──
    nominal_scored = baseline_reused + defended_scored + c00000_scored + guard + unit_sut + util_sut  # counts reused C00000 twice-ish
    padded_with_judge = nominal_scored + judge_calls_ablation + util_judge

    # ── usability FPR ──
    fm = json.load(open(os.path.join(ROOT, "results/phase3/ablation/metrics/final_metrics.json")))
    det = fm["detection_metrics"]
    defended = ["C10000", "C01000", "C00100", "C01100", "C11111"]
    fpr_rows = {}
    for c in ["C00000"] + defended:
        d = det[c]
        ob, nb = d["over_block_on_benign"], d["n_benign"]
        fpr_rows[c] = {"attack_suite_benign_blocked": ob, "attack_suite_n_benign": nb,
                       "attack_suite_benign_blocked_rate": round(ob / nb, 4) if nb else None,
                       "has_L1": c in ("C10000", "C11111")}
    true_fpr = {
        "C00000": {"benign_n": util["summary"]["C00000"]["n_total"], "refused": util["summary"]["C00000"]["n_refused"],
                   "over_refusal_rate": round(util["summary"]["C00000"]["n_refused"] / util["summary"]["C00000"]["n_total"], 4)},
        "C11111": {"benign_n": util["summary"]["C11111"]["n_total"], "refused": util["summary"]["C11111"]["n_refused"],
                   "over_refusal_rate": round(util["summary"]["C11111"]["n_refused"] / util["summary"]["C11111"]["n_total"], 4)},
        "C10000/C01000/C00100/C01100": "NOT measured on the benign set (Task 3.1 ran only the two extremes); "
                   "by monotonicity each is <= C11111's 0/30, i.e. ~0.",
    }

    report = {
        "definition": "query-execution = 1 SUT (RAG) generation = 1 turn. Judge/eval calls excluded "
                      "(reported separately). DEDUP-AWARE: reused (Phase-2 logs or content-addressed cache, $0) "
                      "vs genuinely-new fresh SUT calls.",
        "components": {
            "phase2_baseline_REUSED": {"turns": baseline_reused, "breakdown": f"{b_clean} clean + {b_pois} poisoned (=3 runs x 89)",
                "status": "REUSED as C00000 (re-ran 0)", "new_sut": 0,
                "source": "experiment_logs/B2_CLEAN_main-w3.jsonl + B2_POISONED_poisoned-w4.jsonl"},
            "ablation_6cell_NEW": {"nominal_scored_turns": defended_scored + c00000_scored,
                "note": f"6 cells x 89 = {defended_scored + c00000_scored} SCORED, of which C00000 (89) is a REUSED subset "
                        f"of the 267 and {defended_scored} are defended-config scored turns",
                "fresh_sut_dedup_aware": ablation_real, "includes": "13-turn drift anchor (ran through same cache)",
                "dedup_hit_rate": ablation_dedup, "dedup_saved_turns": defended_scored - (ablation_real - 13),
                "sut_cost_usd": ablation_cost, "source": "ablation_engine_summary.json real_calls"},
            "ablation_GUARD_reproduction_NEW": {"turns": guard, "fresh_sut": guard,
                "note": "all-False pipeline == Phase-2 baseline invariant check (F1 x3 runs); separate run, "
                        "verification not new measurement", "source": "guard_baseline_f1.jsonl"},
            "unit_tests_NEW": {"fresh_sut": unit_sut, "per_test": {k: {"sut": n, "why": w} for k, (n, w) in unit.items()},
                "note": "filter/retrieval-only layer tests (L1, L2-collateral/survivors, L4, L5-provenance/acl) make 0 SUT "
                        "calls; only generation tests count. OFF-baselines verified: oracle_killer ran its L2-OFF set fresh "
                        "(+15, counted); L5 f8 L5-OFF was REUSED from B2_POISONED (not counted). Residual uncertainty +-2 "
                        "(L3-handoff live run, L4 source) — does not affect the <1000 verdict."},
            "utility_3_1_NEW": {"fresh_sut": util_sut, "note": "30 benign queries x {C00000, C11111}",
                "source": "utility_results.json _meta.sut_calls"},
            "L6_3_5": {"fresh_sut": 0, "note": "Task 3.5 --execute NEVER ran (diagnosis only); no l6_results.json"},
            "attacker_demo": {"fresh_sut": 0, "note": "no separate demo artifact; the direct-PII demonstration is the "
                        "sanitized F1 probe (1, in unit tests) + the L2 oracle-killer forced attacks (15, in unit tests)"},
        },
        "totals_DEDUP_AWARE": {
            "reused_phase2_turns": baseline_reused,
            "genuinely_new_phase3_sut": new_phase3,
            "new_breakdown": f"{ablation_real} ablation + {guard} guard + {unit_sut} unit + {util_sut} utility + 0 L6 + 0 demo",
            "total_real_query_executions": total_real,
            "reused_pct": round(100 * baseline_reused / total_real, 1),
            "new_pct": round(100 * new_phase3 / total_real, 1),
            "EXCEEDS_1000": total_real > 1000,
        },
        "out_of_scope_phase2_dev_executions": {"per_log": dev, "total": dev_total,
            "note": "pilot + dry-runs + smoke tests: real Phase-2 dev executions, but NOT measurement and NOT reused; "
                    "excluded from the headline (listed for full transparency)",
            "grand_total_incl_dev": total_incl_dev, "still_under_1000": total_incl_dev <= 1000},
        "padding_trap_AVOIDED": {
            "nominal_scored_SUT_only_counting_reused_as_new": nominal_scored,
            "key_point": f"even PADDED SUT-only (all {defended_scored + c00000_scored} ablation turns counted as new, "
                   f"ignoring 51% dedup + the reused C00000) = {nominal_scored}, STILL < 1000. Crossing 1000 REQUIRES "
                   f"additionally mislabeling judge/eval calls as query-executions.",
            "what_a_padded_count_would_claim": padded_with_judge,
            "how": f"{nominal_scored} padded SUT + {judge_calls_ablation}+{util_judge} JUDGE calls (eval) = "
                   f"~{padded_with_judge} (>1000)",
            "why_it_is_wrong": "that double-counts reused turns as new work and conflates evaluation calls with "
                   "query-executions — exactly what was forbidden",
            "evaluation_overhead_separate": {"ablation_judge_calls": judge_calls_ablation, "utility_judge_calls": util_judge,
                   "note": "Opus-4.7 judge calls = evaluation, not query-executions"},
        },
        "usability_FPR": {
            "attack_suite_benign_blocked_per_config": fpr_rows,
            "CAVEAT": "on the ADVERSARIAL attack suite, 'benign' = turns with no GT-leakable PII, which are almost all "
                      "ATTACK turns carrying no PII payload (injections/jailbreaks). So a high 'benign-blocked' rate for "
                      "L1-bearing configs (C10000 ~0.79, C11111 ~0.93) is MOSTLY CORRECT ATTACK-BLOCKING, not a usability "
                      "failure. n_benign also shifts (3->14) because L1 reclassifies blocked attacks. This is NOT a "
                      "usability FPR.",
            "TRUE_usability_FPR_task_3_1": true_fpr,
            "true_fpr_headline": "On 30 GENUINE benign queries (Task 3.1), over-refusal = 0/30 = 0.0% for BOTH C00000 and "
                      "C11111 -> the full defense stack does not over-refuse legitimate queries (middle cells unmeasured, "
                      "bounded ~0 by monotonicity).",
        },
        "draft_claim_check": {
            "searched": "*.md and *.tex under Code/ for an execution/query-count claim (esp. >1000)",
            "found_over_1000_claim": False,
            "note": "no in-repo draft cites a >1000 query total; the thesis .tex live outside Code/. If any draft/report "
                    "cites a query or execution total, the honest figure is %d real query-executions (%d reused Phase-2 + "
                    "%d new Phase-3). Prompted by the prior count-contamination in the report "
                    "(memory: phase2-report-files-and-s54-bug)." % (total_real, baseline_reused, new_phase3),
        },
    }
    json.dump(report, open(os.path.join(OUT, "scale_report.json"), "w"), indent=2, ensure_ascii=False)
    _md(report)
    _print(report)
    return 0


def _md(r):
    t = r["totals_DEDUP_AWARE"]
    c = r["components"]
    fpr = r["usability_FPR"]
    L = []
    L.append("# Phase-3 scale — honest query-execution accounting\n")
    L.append(f"**A query-execution = one SUT (RAG) generation (one turn).** Judge/eval calls are excluded "
             f"(separate overhead). Counts are **dedup-aware**: *reused* = served from Phase-2 logs or the "
             f"content-addressed SUT cache ($0); *new* = a real fresh Phase-3 SUT call.\n")
    L.append("## Components (each separately)\n")
    L.append("| Component | Turns | New SUT (dedup-aware) | Status |")
    L.append("|---|---|---|---|")
    L.append(f"| Phase-2 baseline | {c['phase2_baseline_REUSED']['turns']} | 0 | **REUSED** ($0; {c['phase2_baseline_REUSED']['breakdown']}) |")
    L.append(f"| 6-cell ablation | {c['ablation_6cell_NEW']['nominal_scored_turns']} scored | **{c['ablation_6cell_NEW']['fresh_sut_dedup_aware']}** | NEW; 51% deduped, incl. 13 drift-anchor; ${c['ablation_6cell_NEW']['sut_cost_usd']} |")
    L.append(f"| Ablation GUARD reproduction | {c['ablation_GUARD_reproduction_NEW']['turns']} | {c['ablation_GUARD_reproduction_NEW']['fresh_sut']} | NEW (verification: all-False == baseline) |")
    L.append(f"| Unit tests (L1–L5 + sanitized) | — | {c['unit_tests_NEW']['fresh_sut']} | NEW (filter/retrieval tests = 0 SUT) |")
    L.append(f"| Utility (Task 3.1) | 60 | {c['utility_3_1_NEW']['fresh_sut']} | NEW (30 benign × 2 cells) |")
    L.append(f"| L6 (Task 3.5) | 0 | 0 | NOT run (diagnosis only) |")
    L.append(f"| Attacker demo | 0 | 0 | none separate (folded into unit tests) |")
    L.append("")
    L.append("### Unit-test SUT breakdown")
    for k, v in c["unit_tests_NEW"]["per_test"].items():
        L.append(f"- **{k}** → {v['sut']} SUT — {v['why']}")
    L.append("")
    L.append("## Total\n")
    L.append(f"- **Reused Phase-2 turns:** {t['reused_phase2_turns']}  ({t['reused_pct']}%)")
    L.append(f"- **Genuinely new Phase-3 SUT:** {t['genuinely_new_phase3_sut']}  ({t['new_pct']}%)  = {c['ablation_6cell_NEW']['fresh_sut_dedup_aware']} ablation + {c['ablation_GUARD_reproduction_NEW']['fresh_sut']} guard + {c['unit_tests_NEW']['fresh_sut']} unit + {c['utility_3_1_NEW']['fresh_sut']} utility")
    L.append(f"- **TOTAL real query-executions = {t['total_real_query_executions']}**")
    L.append(f"- **Exceeds 1000? → {'YES' if t['EXCEEDS_1000'] else 'NO'}.** The honest dedup-aware total is "
             f"{t['total_real_query_executions']} ({t['reused_pct']}% reused Phase-2, {t['new_pct']}% genuinely new Phase-3).\n")
    od = r["out_of_scope_phase2_dev_executions"]
    L.append(f"*Transparency:* {od['total']} additional Phase-2 dev executions exist (pilot {od['per_log']['B1 pilot']} + "
             f"dry-runs + smoke), not measurement and not reused; even including them the grand total is "
             f"{od['grand_total_incl_dev']} (still < 1000).\n")
    pt = r["padding_trap_AVOIDED"]
    L.append(f"*Padding trap (avoided):* even counting **all** ablation SCORED turns as new (ignoring the 51% dedup + the "
             f"reused C00000) gives only **{pt['nominal_scored_SUT_only_counting_reused_as_new']} SUT — still < 1000**. "
             f"Crossing 1000 (~{pt['what_a_padded_count_would_claim']}) requires additionally counting the "
             f"{pt['evaluation_overhead_separate']['ablation_judge_calls']}+"
             f"{pt['evaluation_overhead_separate']['utility_judge_calls']} judge/eval calls as 'query-executions' — "
             f"which presents reused turns as new work and conflates evaluation with query-execution.\n")
    L.append("## Usability FPR (benign-blocked) per defended config\n")
    L.append("| Config | Attack-suite benign-blocked | rate | note |")
    L.append("|---|---|---|---|")
    for cfg, v in fpr["attack_suite_benign_blocked_per_config"].items():
        tag = "no-defense reference" if cfg == "C00000" else ("L1 present → high rate = blocked attacks" if v["has_L1"] else "")
        L.append(f"| {cfg} | {v['attack_suite_benign_blocked']}/{v['attack_suite_n_benign']} | "
                 f"{v['attack_suite_benign_blocked_rate']} | {tag} |")
    L.append("")
    L.append(f"⚠️ **{fpr['CAVEAT']}**\n")
    L.append(f"✅ **True usability FPR (Task 3.1, 30 genuine benign queries):** C00000 = "
             f"{fpr['TRUE_usability_FPR_task_3_1']['C00000']['refused']}/30, C11111 = "
             f"{fpr['TRUE_usability_FPR_task_3_1']['C11111']['refused']}/30 → **0.0% over-refusal for both.** "
             f"{fpr['TRUE_usability_FPR_task_3_1']['C10000/C01000/C00100/C01100']}")
    open(os.path.join(OUT, "SCALE.md"), "w").write("\n".join(L) + "\n")


def _print(r):
    t = r["totals_DEDUP_AWARE"]
    print("=" * 78)
    print("PHASE-3 SCALE — honest query-execution accounting (1 exec = 1 SUT turn; judge calls excluded)")
    print("=" * 78)
    c = r["components"]
    print(f"  Phase-2 baseline      : {c['phase2_baseline_REUSED']['turns']:>4}  REUSED ($0)")
    print(f"  6-cell ablation       : {c['ablation_6cell_NEW']['fresh_sut_dedup_aware']:>4}  NEW  (of {c['ablation_6cell_NEW']['nominal_scored_turns']} scored; 51% deduped)")
    print(f"  ablation GUARD repro  : {c['ablation_GUARD_reproduction_NEW']['fresh_sut']:>4}  NEW  (verification)")
    print(f"  unit tests (L1-L5+san): {c['unit_tests_NEW']['fresh_sut']:>4}  NEW")
    print(f"  utility (3.1)         : {c['utility_3_1_NEW']['fresh_sut']:>4}  NEW")
    print(f"  L6 (3.5)              : {0:>4}  not run")
    print(f"  attacker demo         : {0:>4}  none separate")
    print("-" * 78)
    print(f"  REUSED Phase-2  : {t['reused_phase2_turns']:>4}  ({t['reused_pct']}%)")
    print(f"  NEW Phase-3 SUT : {t['genuinely_new_phase3_sut']:>4}  ({t['new_pct']}%)")
    print(f"  TOTAL real exec : {t['total_real_query_executions']:>4}   -> EXCEEDS 1000? {'YES' if t['EXCEEDS_1000'] else 'NO'}")
    print(f"  (incl. out-of-scope dev: {r['out_of_scope_phase2_dev_executions']['grand_total_incl_dev']}, still <1000)")
    print(f"  padding trap would claim ~{r['padding_trap_AVOIDED']['what_a_padded_count_would_claim']} (counts reused as new + judge calls)")
    print("-" * 78)
    print("  USABILITY FPR (benign-blocked):")
    for cfg, v in r["usability_FPR"]["attack_suite_benign_blocked_per_config"].items():
        print(f"    {cfg}: attack-suite {v['attack_suite_benign_blocked']}/{v['attack_suite_n_benign']} "
              f"= {v['attack_suite_benign_blocked_rate']} {'(L1; mostly blocked ATTACKS)' if v['has_L1'] else ''}")
    print(f"    TRUE usability FPR (Task 3.1 benign): C00000 0/30, C11111 0/30 = 0.0% over-refusal")
    print("Files: results/phase3/scale/{scale_report.json, SCALE.md}")


if __name__ == "__main__":
    sys.exit(main())
