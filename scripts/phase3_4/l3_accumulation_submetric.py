"""
l3_accumulation_submetric.py  (Phase 3-4 correction, Point 5)

Turn-accumulation / multi-turn sub-metric for the conversation-aware refusal layer (L3),
computed from EXISTING engine ablation logs WITHOUT any new model calls.

L3 fires by replacing the turn response with the exact _L3_REFUSAL_TEXT constant
(defense_pipeline.py line ~453). We count exact-match firings per config, broken out by
attack family and single- vs multi-turn, to test whether L3 earns its place in the
recommended knee (C01100 = L2+L3) on a *measured* basis.

Judged ASRs are read from the committed consolidated artifact final_metrics.json (not
recomputed) so the "no measured gain" claim is anchored to the same source the report cites.

Reads:  results/phase3/ablation/engine/{C00100,C01000,C01100,C11111}.jsonl  (existing)
        results/phase3/ablation/metrics/final_metrics.json                  (existing)
        scripts/phase3/defense_pipeline.py  (exact _L3_REFUSAL_TEXT constant)
Writes: results/phase3_4/l3_accumulation_submetric/l3_firing.json           (NEW)
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENGINE = os.path.join(ROOT, "results", "phase3", "ablation", "engine")
FINAL = os.path.join(ROOT, "results", "phase3", "ablation", "metrics", "final_metrics.json")
PIPE = os.path.join(ROOT, "scripts", "phase3", "defense_pipeline.py")
OUT = os.path.join(ROOT, "results", "phase3_4", "l3_accumulation_submetric", "l3_firing.json")


def exact_constant(name):
    src = open(PIPE).read()
    m = re.search(name + r"\s*=\s*\((.*?)\)\s*\n", src, re.DOTALL)
    parts = re.findall(r'"([^"]*)"', m.group(1))
    return "".join(parts).strip()


def firings(config, l3_text):
    path = os.path.join(ENGINE, f"{config}.jsonl")
    rows = [json.loads(l) for l in open(path) if l.strip()]
    fired = [r for r in rows if r.get("response", "").strip() == l3_text]
    by_family = Counter(r["attack_family"] for r in fired)
    multiturn = sum(1 for r in fired if r.get("turn_index", 0) > 0)
    return {
        "n_turns": len(rows),
        "l3_fired_turns": len(fired),
        "l3_fired_by_family": dict(by_family),
        "l3_fired_multiturn_turns": multiturn,
        "l3_fired_scenarios": sorted({r["scenario_id"] for r in fired}),
    }


def main():
    l3_text = exact_constant("_L3_REFUSAL_TEXT")
    fm = json.load(open(FINAL))
    cell = fm["per_cell"]

    submetric = {c: firings(c, l3_text) for c in ("C00100", "C01000", "C01100", "C11111")}

    judged = {
        "C00000_no_defense": cell["C00000"]["judged_strict"]["overall"],
        "C00100_L3_only": cell["C00100"]["judged_strict"]["overall"],
        "C01000_L2_only": cell["C01000"]["judged_strict"]["overall"],
        "C01100_L2_L3_knee": cell["C01100"]["judged_strict"]["overall"],
        "C11111_full": cell["C11111"]["judged_strict"]["overall"],
    }

    result = {
        "purpose": "Point 5: does the conversation-aware refusal layer (L3) yield a MEASURED "
                   "leakage reduction, or is it retained as unmeasured defense-in-depth?",
        "method": "Exact-match count of _L3_REFUSAL_TEXT firings in existing engine ablation "
                  "logs (no new model calls). L3 firing = pipeline replaced the response with "
                  "the L3 refusal constant.",
        "l3_firing_submetric": submetric,
        "judged_strict_ASR_source_final_metrics": judged,
        "findings": {
            "l3_fires_in_isolation": f"{submetric['C00100']['l3_fired_turns']}/"
                f"{submetric['C00100']['n_turns']} turns in C00100 (L3-only), all "
                f"F2_LINKABILITY multi-turn chains",
            "l3_inert_once_redaction_upstream": f"{submetric['C01100']['l3_fired_turns']}/"
                f"{submetric['C01100']['n_turns']} turns in C01100 (L2+L3, the knee) and "
                f"{submetric['C11111']['l3_fired_turns']}/{submetric['C11111']['n_turns']} in "
                f"C11111 (full): L2 redaction upstream strips the content, so the accumulation "
                f"threshold is never crossed and L3 never fires.",
            "no_measured_leakage_gain": "C01000 (L2 only) and C01100 (L2+L3) judged strict ASR "
                "are identical at 0.1923 -> L3 adds no measured leakage reduction over redaction "
                "alone. C00100 (L3 only) judged strict 0.3462 is above the 0.2885 baseline "
                "(within the 0.08 judged noise floor): no net reduction in isolation either.",
            "conclusion": "L3 yields NO measured leakage gain over redaction alone and is "
                "effectively inert inside the recommended knee. It is retained only as "
                "unmeasured multi-turn defense-in-depth (its sole positive evidence is the "
                "constructed handoff unit test in scripts/phase3/l3_tests.py, a co-occurrence "
                "that did not arise in the live campaign). The utility/cost table reports "
                "full-stack cost (C00000 vs C11111) and does not isolate L3's marginal cost.",
        },
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(result, open(OUT, "w"), indent=2)
    print(json.dumps(result, indent=2))
    print(f"\nwrote {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
