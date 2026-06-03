"""
risk_matrix.py — Task 3.4: privacy risk matrix (results/phase3/risk_matrix/).

PURE SYNTHESIS of measured data ($0). Residual config = C01100 (the RQ5 knee/recommended; Task 3.5
produced NO L6 reduction, diagnosis only). Two tables with TWO DISTINCT likelihood bases — never
conflated:

  TABLE A  Family risk (F1-F8): likelihood = JUDGED ASR_strict (primary).
           baseline = C00000, residual = C01100. risk = impact_tier x residual.
           -> JUDGED residual is a LOWER BOUND on true risk: like the engine, the judge cannot see
              all cross-document re-identification (finding F1).

  TABLE B  Entity-type risk (31 types): likelihood = detector-miss EXPOSURE under L2, i.e. whether a
           retrieved entity survives C01100's L2 Presidio-redaction. NOT judged ASR (no per-type
           judged metric exists); this is the per-type residual the task asks to tie to Task 0.1.
             - sev>=3 : residual = 1 - Presidio recall_any (Task 0.1; recall_any is redaction-relevant)
             - sev==2 : residual = 1.0  (L2 redacts sev>=3 ONLY; sev2 quasi-identifiers retained BY DESIGN)
           risk = severity x residual_exposure.

THE ONE STORY (tables are coupled): the DETECTOR-GAP sensitive attributes (MEDICAL, AGE_GENDER,
SURNAME_TITLE, IMMIGRATION) that L2 misses, PLUS the BELOW-THRESHOLD sev2 quasi-identifiers L2
retains by design, are the SUBSTRATE that makes the F2 LINKABILITY family (Table A) survive the
stack (judged ~0.6-0.7, unreduced). AGE_GENDER is the bridge (sev3 detector-gap AND
LINDDUN=Linkability). See results/phase3/linkability_diagnosis/FINDING.md + Task 2.3 headline.
"""
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "results/phase3/risk_matrix")
FINAL = os.path.join(ROOT, "results/phase3/ablation/metrics/final_metrics.json")
RECALL = os.path.join(ROOT, "results/phase3/presidio_check/presidio_recall.json")
ANN = os.path.join(ROOT, "data/ground_truth/ground_truth_annotations.json")

L2_REDACTION_THRESHOLD = 3      # L2 redacts Presidio-detected sev>=3 PII only
RESIDUAL_CONFIG = "C01100"
BASELINE_CONFIG = "C00000"

FAMILIES = ["F1_DIRECT_PII", "F2_LINKABILITY", "F3_DIRECT_INJECTION", "F4_OBFUSCATION",
            "F5_JAILBREAK", "F6_RECON", "F7_SOCIAL_ENG", "F8_CORPUS_POISONING"]
# assigned IMPACT TIER = max severity class the family can exfiltrate if it succeeds (documented;
# the PRIMARY ranking is by measured residual, so the tier only scales the risk product).
IMPACT_TIER = {"F1_DIRECT_PII": 5, "F2_LINKABILITY": 4, "F3_DIRECT_INJECTION": 5, "F4_OBFUSCATION": 4,
               "F5_JAILBREAK": 5, "F6_RECON": 3, "F7_SOCIAL_ENG": 4, "F8_CORPUS_POISONING": 5}
# dominant LINDDUN privacy-threat realised by the family (the harm to the data subject, not the vector)
FAMILY_LINDDUN = {"F1_DIRECT_PII": "Identifiability", "F2_LINKABILITY": "Linkability",
                  "F3_DIRECT_INJECTION": "Disclosure", "F4_OBFUSCATION": "Disclosure",
                  "F5_JAILBREAK": "Disclosure", "F6_RECON": "Detectability",
                  "F7_SOCIAL_ENG": "Disclosure", "F8_CORPUS_POISONING": "Disclosure"}
NOTE_FAMILY = {
    "F2_LINKABILITY": "DOMINANT ELEVATED residual: unreduced (judged ~0.6-0.7 across ALL configs; "
                      "0.60/0.70/0.60 at C00000/C01100/C11111) -> the redaction stack does not reduce "
                      "linkability (Task 2.3 headline; linkability_diagnosis). residual>=baseline here "
                      "is the FINDING, not config-worse.",
    "F6_RECON": "small-n (n=3): residual 0.333 = 1/3 turns, judge variance within the 0.08 floor; not robust.",
    "F1_DIRECT_PII": "L2 cuts it 0.78->0.22; the 0.22 residual = the SURNAME/prose-salary detector gaps (Table B).",
}


def load_linddun():
    ann = json.load(open(ANN))
    recs = ann if isinstance(ann, list) else next(v for v in ann.values() if isinstance(v, list))
    m = {}
    for doc in recs:
        for e in doc.get("entities", []):
            m.setdefault(e.get("type"), e.get("linddun_category"))
    return m


def entity_class(sev, recall_any):
    if sev >= L2_REDACTION_THRESHOLD and recall_any >= 0.999:
        return "REDACTED"          # detected -> removed by L2
    if sev >= L2_REDACTION_THRESHOLD:
        return "DETECTOR-GAP"      # should be redacted but Presidio misses it -> survives
    return "BELOW-THRESHOLD"       # sev2 < sev>=3 threshold -> L2 retains BY DESIGN (linkability substrate)


def entity_residual(sev, recall_any, klass):
    if klass == "BELOW-THRESHOLD":
        return 1.0                 # L2 does not target sev2 regardless of detection
    return round(1.0 - recall_any, 4)   # sev>=3: survivors = undetected fraction


ENTITY_NOTE = {
    "SYSTEM_PROMPT": "Presidio/L2 is NOT the control for prompt leakage; covered at SCENARIO level by F3 "
                     "(judged residual 0.0) -> entity residual high but scenario risk low.",
    "SALARY": "structured-format recall 1.0 (redacted); PROSE-form salary ('compensation of $106,307') "
              "SURVIVES (linkability_diagnosis; Sprint-1 L4 format-drift) — a residual NOT captured by "
              "this per-type structured recall.",
    "AGE_GENDER": "BRIDGE: sev3 detector-gap AND LINDDUN=Linkability -> direct fuel for the F2 residual.",
    "MEDICAL": "ELEVATED (Task 0.1 recall_any=0.0, open-vocabulary): never redacted; feeds F2.",
    "SURNAME_TITLE": "ELEVATED (Task 0.1 recall_any=0.51): half survive; feeds F1/F2 residual.",
}


def main():
    os.makedirs(OUT, exist_ok=True)
    fm = json.load(open(FINAL))
    rec = json.load(open(RECALL))
    lind = load_linddun()

    # ── TABLE A: families (judged) ──
    fam_rows = []
    for f in FAMILIES:
        base = fm["per_cell"][BASELINE_CONFIG]["judged_strict"]["per_family"][f]
        resid = fm["per_cell"][RESIDUAL_CONFIG]["judged_strict"]["per_family"][f]
        n = fm["per_cell"][BASELINE_CONFIG]["family_n"][f]
        tier = IMPACT_TIER[f]
        fam_rows.append({
            "family": f, "n_scenarios": n, "impact_tier_assigned": tier,
            "baseline_judged_ASR": round(base, 4), "residual_judged_ASR_C01100": round(resid, 4),
            "linddun": FAMILY_LINDDUN[f], "risk_tier_x_residual": round(tier * resid, 4),
            "delta_vs_baseline": round(resid - base, 4), "note": NOTE_FAMILY.get(f, ""),
        })
    fam_rows.sort(key=lambda r: -r["residual_judged_ASR_C01100"])

    # ── TABLE B: entity types (detector-miss exposure under L2) ──
    ent_rows = []
    for e in rec["per_type"]:
        t, sev, ra = e["type"], e["severity"], e["recall_any"]
        klass = entity_class(sev, ra)
        resid = entity_residual(sev, ra, klass)
        # which scenario family covers this entity, and is that family defended at C01100?
        ent_rows.append({
            "entity_type": t, "severity": sev, "linddun": lind.get(t, "?"),
            "presidio_recall_any_task01": ra, "residual_exposure_under_L2": resid,
            "risk_sev_x_residual": round(sev * resid, 4), "residual_class": klass,
            "note": ENTITY_NOTE.get(t, ""),
        })
    CLASS_PRI = {"DETECTOR-GAP": 0, "BELOW-THRESHOLD": 1, "REDACTED": 2}
    ent_rows.sort(key=lambda r: (CLASS_PRI[r["residual_class"]], -r["risk_sev_x_residual"], -r["severity"]))

    # ── write CSVs ──
    with open(os.path.join(OUT, "risk_matrix_families.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fam_rows[0].keys())); w.writeheader(); w.writerows(fam_rows)
    with open(os.path.join(OUT, "risk_matrix_entities.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(ent_rows[0].keys())); w.writeheader(); w.writerows(ent_rows)

    # ── key numbers for the DPIA (Task 3.7) to cite ──
    detector_gap = [r for r in ent_rows if r["residual_class"] == "DETECTOR-GAP"]
    below = [r for r in ent_rows if r["residual_class"] == "BELOW-THRESHOLD"]
    keys = {
        "residual_config": RESIDUAL_CONFIG, "l2_redaction_threshold_sev": L2_REDACTION_THRESHOLD,
        "judged_is_lower_bound_per_F1": True,
        "dominant_elevated_family": {"family": "F2_LINKABILITY", "residual_judged": fam_rows[0]["residual_judged_ASR_C01100"]
                                     if fam_rows[0]["family"] == "F2_LINKABILITY" else
                                     next(r["residual_judged_ASR_C01100"] for r in fam_rows if r["family"] == "F2_LINKABILITY"),
                                     "across_configs": "0.60/0.70/0.60 (C00000/C01100/C11111) — unreduced"},
        "elevated_detector_gap_sev>=3": [{"type": r["entity_type"], "sev": r["severity"],
                                          "recall_any": r["presidio_recall_any_task01"],
                                          "residual": r["residual_exposure_under_L2"], "linddun": r["linddun"]}
                                         for r in detector_gap],
        "MEDICAL_recall": next(r["presidio_recall_any_task01"] for r in ent_rows if r["entity_type"] == "MEDICAL"),
        "SURNAME_recall": next(r["presidio_recall_any_task01"] for r in ent_rows if r["entity_type"] == "SURNAME_TITLE"),
        "below_threshold_quasi_identifiers": [r["entity_type"] for r in below],
        "connection": "DETECTOR-GAP sev>=3 attributes (MEDICAL/AGE_GENDER/SURNAME/IMMIGRATION) + BELOW-THRESHOLD "
                      "sev2 quasi-identifiers = the substrate F2 linkability survives on.",
    }
    json.dump({"families": fam_rows, "entities": ent_rows, "key_findings": keys},
              open(os.path.join(OUT, "risk_matrix.json"), "w"), indent=2, ensure_ascii=False)

    _md(fam_rows, ent_rows, keys)
    _print(fam_rows, ent_rows, keys)
    return 0


def _md(fam, ent, keys):
    L = ["# Task 3.4 — Privacy risk matrix\n",
         f"Residual config = **{RESIDUAL_CONFIG}** (RQ5 knee/recommended; Task 3.5 produced no L6 reduction). "
         f"Two tables, **two likelihood bases** (never conflated): families use the **judged ASR** (primary); "
         f"entity types use **detector-miss exposure under L2** (= 1−Presidio recall_any for sev≥3; =1.0 for sev2, "
         f"which L2 retains by design). **Judged residual is a LOWER BOUND** on true risk — the judge, like the "
         f"engine, cannot see all cross-document re-identification (finding F1).\n",
         "## Table A — Family risk (judged ASR; sorted by residual)\n",
         "| Family | n | Impact tier | Baseline judged ASR (C00000) | **Residual judged ASR (C01100)** | LINDDUN | Risk (tier×resid) | Note |",
         "|---|---|---|---|---|---|---|---|"]
    for r in fam:
        L.append(f"| {r['family']} | {r['n_scenarios']} | {r['impact_tier_assigned']} | {r['baseline_judged_ASR']} | "
                 f"**{r['residual_judged_ASR_C01100']}** | {r['linddun']} | {r['risk_tier_x_residual']} | {r['note']} |")
    L.append(f"\n**Impact tier is an *assigned* worst-case impact class (documented), not measured — the ranking is "
             f"driven by the *measured* residual.** F2 LINKABILITY is the dominant elevated residual "
             f"({keys['dominant_elevated_family']['residual_judged']}); across configs it is "
             f"{keys['dominant_elevated_family']['across_configs']}.\n")
    L.append("## Table B — Entity-type risk (detector-miss exposure under L2; grouped by class, then risk)\n")
    L.append("| Entity type | Sev | LINDDUN | Presidio recall_any (Task 0.1) | Residual exposure | Risk (sev×resid) | Class | Note |")
    L.append("|---|---|---|---|---|---|---|---|")
    for r in ent:
        L.append(f"| {r['entity_type']} | {r['severity']} | {r['linddun']} | {r['presidio_recall_any_task01']} | "
                 f"{r['residual_exposure_under_L2']} | {r['risk_sev_x_residual']} | {r['residual_class']} | {r['note']} |")
    L.append("")
    f2 = keys["dominant_elevated_family"]["residual_judged"]
    L.append("## Elevated residuals — the headline\n")
    L.append(f"**1. LINKABILITY (F2) is the dominant residual** — judged ASR **{f2}** under C01100, **unreduced** by "
             f"the stack (~0.6–0.7 across every config). It is the leak the recommended config does not close "
             f"(Task 2.3 headline; `linkability_diagnosis/FINDING.md`).")
    L.append(f"**2. Its feeders are the Task-0.1 detector gaps** — sev≥3 attributes L2 *should* redact but Presidio "
             f"misses: **MEDICAL** (recall_any **{keys['MEDICAL_recall']}**), **SURNAME_TITLE** "
             f"(**{keys['SURNAME_recall']}**), **AGE_GENDER** (0.0 — the Linkability bridge), **IMMIGRATION** (0.0). "
             f"They survive redaction and re-identify *in combination* with the retained sev2 quasi-identifiers. "
             f"This is the MEDICAL/SURNAME elevation the task asks for, tied directly to Task 0.1.")
    L.append(f"**3. SYSTEM_PROMPT sorts to the top of the entity table** (sev5 × residual 1.0 = 5.0) **but is NOT a "
             f"top operational risk** — Presidio/L2 is not its control, and the F3 injection family that targets it "
             f"is fully defended (judged residual 0.0). Listed for completeness; it does not set the headline.\n")
    L.append("Full detector-gap class (sev≥3, survive L2 redaction — Task 0.1):")
    for r in keys["elevated_detector_gap_sev>=3"]:
        cov = " — scenario-covered by F3 (judged 0.0)" if r["type"] == "SYSTEM_PROMPT" else ""
        L.append(f"- **{r['type']}** (sev {r['sev']}, recall_any **{r['recall_any']}** → residual "
                 f"{r['residual']}, LINDDUN={r['linddun']}){cov}")
    L.append("")
    L.append("## The connection (one story, not two tables)\n")
    L.append(f"The Table-B residuals **are why Table-A's F2 survives.** The detector-gap sev≥3 attributes "
             f"(MEDICAL, AGE_GENDER, SURNAME_TITLE, IMMIGRATION) that L2 misses, **plus** the below-threshold "
             f"sev2 quasi-identifiers L2 retains by design ({', '.join(keys['below_threshold_quasi_identifiers'])}), "
             f"are the substrate the **F2 LINKABILITY** family re-identifies on. **AGE_GENDER is the bridge** — "
             f"sev3 (above the redaction threshold), LINDDUN=Linkability, recall_any 0.0. So the entity-level "
             f"detector gap (Table B) and the family-level survival of linkability (Table A, judged ~0.6–0.7, "
             f"unreduced) are the *same* phenomenon. See `linkability_diagnosis/FINDING.md` + Task 2.3.\n")
    L.append("## Caveats\n")
    L.append("- **Judged residual = lower bound** (finding F1): true re-identification risk ≥ the judged figure.")
    L.append("- **F2 residual ≥ baseline** (0.70 vs 0.60) is one noisy plateau within the 0.08 judged floor — read "
             "it as *linkability unreduced*, NOT 'C01100 worse than the full stack'.")
    L.append("- **SYSTEM_PROMPT** (sev5, recall 0.0) tops the detector-gap class but L2/Presidio is not its control; "
             "the F3 injection family that targets it is fully defended (judged residual 0.0).")
    L.append("- **SALARY** structured recall is 1.0 (redacted) but **prose-form salary survives** — a residual not "
             "visible in the per-type structured recall (linkability_diagnosis).")
    L.append("- Entity residual is the **L2-redaction** model; family residual is the full **C01100** judged outcome "
             "(L2+L3+model). Two different mechanisms, two different likelihood bases — not interchangeable.")
    open(os.path.join(OUT, "RISK_MATRIX.md"), "w").write("\n".join(L) + "\n")


def _print(fam, ent, keys):
    print("=" * 80)
    print("TASK 3.4 RISK MATRIX (residual config C01100; $0 synthesis)")
    print("=" * 80)
    print("TABLE A — families (judged ASR; sorted by residual):")
    print(f"  {'family':20}{'base':>7}{'resid':>8}{'risk':>7}  {'linddun':14}")
    for r in fam:
        flag = "  <- DOMINANT" if r["family"] == "F2_LINKABILITY" else ("  (small-n)" if r["family"] == "F6_RECON" else "")
        print(f"  {r['family']:20}{r['baseline_judged_ASR']:>7}{r['residual_judged_ASR_C01100']:>8}"
              f"{r['risk_tier_x_residual']:>7}  {r['linddun']:14}{flag}")
    print("\nTABLE B — entity types (top of each class):")
    seen = set()
    for r in ent:
        if r["residual_class"] not in seen:
            seen.add(r["residual_class"]); print(f"  --- {r['residual_class']} ---")
        if r["residual_class"] != "REDACTED" or r["entity_type"] in ("SALARY",):
            print(f"    {r['entity_type']:18} sev{r['severity']} recall_any={r['presidio_recall_any_task01']!s:5} "
                  f"resid={r['residual_exposure_under_L2']!s:5} risk={r['risk_sev_x_residual']!s:5} {r['linddun']}")
    print(f"\n  MEDICAL recall_any={keys['MEDICAL_recall']} | SURNAME recall_any={keys['SURNAME_recall']} "
          f"(Task-0.1 blind spots, ELEVATED)")
    print(f"  CONNECTION: detector-gap attrs + sev2 quasi-identifiers = substrate F2 linkability survives on")
    print("Files: results/phase3/risk_matrix/{risk_matrix_families.csv, risk_matrix_entities.csv, RISK_MATRIX.md, risk_matrix.json}")


if __name__ == "__main__":
    sys.exit(main())
