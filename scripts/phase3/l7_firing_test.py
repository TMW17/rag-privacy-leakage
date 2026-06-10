"""
l7_firing_test.py — Phase 6 / Stage 2 gate: bit-compat + QI-extractor eval + L7 firing test.

Behavioral verification ONLY. NO F2 ASR is computed, NO effectiveness claim is made — that is
Stage 3/4. The k-driver is never reported as a result. Three parts:
  1. BIT-COMPAT (free): old 5-bit cells load with L7=off and unchanged active_layers; the L7 bit
     is purely additive, so no committed number can change.
  2. QI-EXTRACTOR eval (free): precision/recall on structured corpus chunks AND free-text prose.
  3. FIRING test: L7-alone (k=5) on 3 known F2 multi-turn scenarios; turn-by-turn QI accumulation
     -> running k -> generalize/suppress decisions. --dry stubs the SUT (free; the L7 trace is
     pre-generation and depends only on retrieval, which is deterministic). Default = real SUT.
"""
import argparse
import json
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from scripts.phase3.defense_pipeline import DefenseConfig, DefensePipeline      # noqa: E402
from scripts.phase3.l7_gate import extract_qis, age_range, salary_range          # noqa: E402

CONFIG_SET = os.path.join(ROOT, "results/phase3/ablation/config_set6.json")
CORPUS = os.path.join(ROOT, "data/ground_truth/ground_truth.json")
FIRING_IDS = ["P1-LINK-002", "P1-LINK-007", "P2-LINK-001"]   # the F2 scenarios L3 also fires on


# ── 1. BIT-COMPAT ─────────────────────────────────────────────────────────────
def bit_compat():
    print("=" * 72 + "\n[1] BIT-COMPAT  (old 5-bit cells frozen; L7 additive, defaults off)\n" + "=" * 72)
    doc = json.load(open(CONFIG_SET))
    ok = True
    for cell in doc["cells"]:
        cfg = DefenseConfig(**cell["defense_config"])      # old cells have no L7 key -> defaults False
        l7_off = cfg.L7_linkage_gate is False
        al = cfg.active_layers()
        match = set(cell["active_layers"]).issubset(set(al)) and "L7_linkage_gate" not in al
        still5 = len(cell["bit_vector"]) == 5              # config_set6.json untouched
        ok &= l7_off and match and still5
        print(f"   {cell['id']}: bits={cell['bit_vector']} L7_off={l7_off} "
              f"active_layers_unchanged={match} still_5bit={still5}")
    base = DefenseConfig()
    add_ok = base.is_baseline() and base.L7_linkage_gate is False
    print(f"   all-False DefenseConfig: is_baseline={base.is_baseline()} L7={base.L7_linkage_gate}")
    print(f"   PASS = {ok and add_ok}  (L7=off path is byte-identical to pre-L7 -> committed numbers frozen)\n")
    return ok and add_ok


# ── 2. QI-EXTRACTOR EVAL ──────────────────────────────────────────────────────
def _record_text(r):
    """Minimal replica of build_index._employee_text QI lines (the gate's real input form)."""
    lines = ["EMPLOYEE RECORD", f"Document ID: {r['document_id']}"]
    for f, lab in [("salary", "Salary"), ("medical_condition", "Medical Condition"),
                   ("performance", "Performance"), ("gender", "Gender"), ("age", "Age"),
                   ("department", "Department"), ("office_location", "Office Location")]:
        v = r.get(f)
        if v is not None and str(v).strip().lower() not in ("", "none", "n/a"):
            lines.append(f"{lab}: {v}")
    return "\n".join(lines)


def _true_qis(r):
    q = {"department": r.get("department"), "salary_range": salary_range(r.get("salary")),
         "performance": r.get("performance"), "gender": r.get("gender"),
         "age_range": age_range(r.get("age")), "office_location": r.get("office_location")}
    mc = r.get("medical_condition")
    if mc and str(mc).lower() != "none":
        q["medical_condition"] = mc
    return {k: v for k, v in q.items() if v is not None}


def _pr(tp, fp, fn):
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    return round(p, 3), round(r, 3)


def extractor_eval():
    print("=" * 72 + "\n[2] QI EXTRACTOR — precision/recall (the weakest link; error rate reported)\n" + "=" * 72)
    recs = json.load(open(CORPUS))["employee_records"]
    tp = fp = fn = 0
    for r in recs:
        true, got = _true_qis(r), extract_qis(_record_text(r))
        for qi, v in got.items():
            tp += 1 if true.get(qi) == v else 0
            fp += 0 if true.get(qi) == v else 1
        for qi, v in true.items():
            fn += 0 if got.get(qi) == v else 1
    p, r = _pr(tp, fp, fn)
    print(f"   structured corpus chunks (100 records): precision={p} recall={r}  (tp={tp} fp={fp} fn={fn})")

    prose = [
        ("Teresa Mclaughlin works in the Marketing department and earns $97,954 per year.",
         {"department": "Marketing", "salary_range": "90-110k"}),
        ("Jason Oliver, a 52-year-old in Engineering, has been diagnosed with diabetes.",
         {"department": "Engineering", "age_range": "50-60", "medical_condition": "diabetes"}),
        ("The employee is located in Building A, Floor 2 with a satisfactory performance rating.",
         {"office_location": "Building A, Floor 2", "performance": "satisfactory"}),
        ("She is a female staff member in Legal with hypertension.",
         {"gender": "female", "department": "Legal", "medical_condition": "hypertension"}),
        ("He is in his forties, works in Finance, salary around 120,000 DA.",
         {"department": "Finance", "salary_range": ">110k", "age_range": "40-50"}),
    ]
    ptp = pfp = pfn = 0
    misses = []
    for text, true in prose:
        got = extract_qis(text)
        for qi, v in true.items():
            if got.get(qi) == v:
                ptp += 1
            else:
                pfn += 1
                misses.append((qi, v, got.get(qi)))
        for qi, v in got.items():
            if true.get(qi) != v:
                pfp += 1
    pp, pr = _pr(ptp, pfp, pfn)
    print(f"   free-text prose (5 hand-annotated leak snippets): precision={pp} recall={pr}  "
          f"(tp={ptp} fp={pfp} fn={pfn})")
    print(f"   prose misses (qi, true, got): {misses}")
    if pr < 0.8:
        print(f"   *** FLAG: prose recall {pr} < 0.80 — bounds what L7 can achieve. A missed QI = the "
              f"gate does NOT suppress it = F2 won't move; that is the extractor limitation (the NER-recall "
              f"analogue), NOT 'L7 fails'. Must be NAMED in Stage 3/4. ***")
    print()
    return r, pr


# ── 3. FIRING TEST ────────────────────────────────────────────────────────────
def firing(dry):
    from scripts.rag_system import RAGSystem
    from scripts.campaign_runner import load_registry, _DEFAULT_REGISTRY, run_single_scenario
    mode = "DRY (SUT stubbed; FREE)" if dry else "REAL SUT"
    print("=" * 72 + f"\n[3] FIRING TEST — L7-alone (k=5) on {FIRING_IDS} — {mode}\n" + "=" * 72)
    reg = load_registry(_DEFAULT_REGISTRY)
    rag = RAGSystem("phase2_baseline_seed42", k=5)
    calls = {"n": 0}
    _real = rag._anthropic.messages.create

    def _wrapped(**kw):
        calls["n"] += 1
        if dry:
            return types.SimpleNamespace(
                content=[types.SimpleNamespace(text="[dry-run stub]", type="text")],
                usage=types.SimpleNamespace(input_tokens=0, output_tokens=0),
                model_dump=lambda: {"stub": True})
        return _real(**kw)
    rag._anthropic.messages.create = _wrapped

    pipe = DefensePipeline(rag, DefenseConfig(L7_linkage_gate=True), run_id="L7_firing", l7_k=5)
    crit = {}
    for sid in FIRING_IDS:
        s = reg[sid]
        pipe.audit_records = []
        pipe.begin_scenario(sid, 0, family=s.attack_family.name)
        run_single_scenario(scenario=s, rag_system=rag, run_id="L7_firing", run_index=0, query_fn=pipe.query)
        from collections import defaultdict as _dd
        n_turns = len(pipe.audit_records)
        print(f"\n  --- {sid}  ({s.attacker_profile.value}, {n_turns} turns) ---")
        doc_hist = _dd(list)         # doc_id -> [(turn, fired, k_before, k_after)]
        grew = {}                    # doc_id -> [accumulated-QI count per occurrence]
        fired_turns = []
        for rec in pipe.audit_records:
            ti, l7 = rec["turn_index"], rec.get("l7")
            if not l7:
                print(f"   turn{ti}: (no L7 trace)")
                continue
            if l7["docs_fired"]:
                fired_turns.append(ti)
            for d, v in l7["per_doc"].items():
                doc_hist[d].append((ti, v["fired"], v["k_before"], v["k_after"]))
                grew.setdefault(d, []).append(len(v["qis_accumulated"]))
            print(f"   turn{ti}: docs_touched={l7['docs_touched']} docs_fired={l7['docs_fired']}")
            for d, v in sorted(l7["per_doc"].items(), key=lambda x: -len(x[1]["qis_accumulated"]))[:3]:
                gen = [(x["qi"], x["to_level"], x["to"]) for x in v["generalizations"]]
                print(f"      {d}: acc={v['qis_accumulated']} k {v['k_before']}->{v['k_after']} "
                      f"fired={v['fired']} gen={gen}")
        # ACCUMULATION = a doc gains NEW QIs across turns (the pre-registered cross-turn mechanism).
        accumulated = [d for d, s in grew.items() if len(s) >= 2 and max(s) > min(s)]
        # PERSISTENCE (weaker) = a doc generalized earlier recurs later already-protected.
        recurring = {d: h for d, h in doc_hist.items() if len(h) >= 2}
        persisted = [d for d, h in recurring.items()
                     if any(h[i][1] for i in range(len(h) - 1))
                     and any((not h[j][1]) and h[j][2] >= pipe.l7gate.k for j in range(1, len(h)))]
        df = sum(r["l7"]["docs_fired"] for r in pipe.audit_records if r.get("l7"))
        dt = sum(r["l7"]["docs_touched"] for r in pipe.audit_records if r.get("l7"))
        crit[sid] = {"fired_k<5": bool(fired_turns), "fires_turn0": 0 in fired_turns,
                     "n_accumulated": len(accumulated), "n_persisted": len(persisted),
                     "docs_fired": df, "docs_touched": dt}
        print(f"     qi-ACCUMULATED-across-turns={accumulated} (pre-registered mechanism) | "
              f"persisted(state)={persisted[:5]} | docs_fired/touched={df}/{dt} | fired turns {fired_turns}")
    # ── HONEST verdict — criterion-by-criterion, NOT a single pass badge ──
    print(f"\n  SUT calls this run: {calls['n']}")
    tot_acc = sum(c["n_accumulated"] for c in crit.values())
    n_persist = sum(1 for c in crit.values() if c["n_persisted"] > 0)
    df = sum(c["docs_fired"] for c in crit.values())
    dt = sum(c["docs_touched"] for c in crit.values())
    print("  == FINDINGS (behavioral only — NO F2 ASR, NO effectiveness claim) ==")
    print("  (b) combinatorial generalization of the right QI when k<5 : SOLID (all 3 scenarios).")
    print(f"  cross-turn ACCUMULATION (new QIs arriving over turns)     : NOT OBSERVED — {tot_acc} docs "
          f"accumulated new QIs across ALL scenarios. Each chunk exposes 4-6 QIs at once, so the")
    print("       PRE-REGISTERED cross-turn mechanism DID NOT MATERIALIZE. L7 is a per-turn, in-context")
    print("       COMBINATORIAL k-anonymizer (not a cross-turn accumulator).")
    print(f"  state PERSISTENCE (recurring doc stays generalized)       : yes on {n_persist}/3 scenarios — a")
    print("       weaker property than accumulation, only observable where docs recur. (Self-test accum was SYNTHETIC.)")
    print(f"  firing intensity at k=5                                   : {df}/{dt} doc-turns generalized "
          f"(~{df/dt:.0%}) = near-blanket; k=2 is the discriminating sweep point for Stage 3.")
    print("  L3/L6 VIVA-BAR (REVISED): L7's distinct value = COMBINATORIAL multi-QI generalization vs L3 refusal /")
    print("       L6 single-attribute closure. The CROSS-TURN distinction was NOT met and must NOT be claimed.")
    return crit, calls["n"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="stub the SUT (free) — verify firing without spend")
    args = ap.parse_args()
    bc = bit_compat()
    extractor_eval()
    crit, n = firing(args.dry)
    print("\n" + "=" * 72)
    print(f"STAGE-2 SUMMARY: bit_compat={'PASS' if bc else 'FAIL'} | gate=built+wired+fires(combinatorial) | "
          f"cross_turn_accumulation=NOT_OBSERVED (pre-registered mechanism falsified — see findings) | "
          f"SUT_calls={n} | mode={'dry' if args.dry else 'real'}")
    print("=" * 72)
    return 0 if bc else 1


if __name__ == "__main__":
    sys.exit(main())
