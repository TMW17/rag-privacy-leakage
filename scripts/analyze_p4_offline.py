#!/usr/bin/env python3
"""
analyze_p4_offline.py
=====================
Third-Party Aggregator (P4 profile) offline privacy risk analysis.

Computes four risk dimensions from Phase 1 annotations + Phase 2 logs
with NO API calls (cost: $0).

OUTPUTS
-------
  results/baseline/p4_offline_metrics.json
  results/baseline/p4_offline_summary.md
"""

import json
import sys
import time
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).parent.parent

# ── Input paths ───────────────────────────────────────────────────────────────
ANNOTATIONS_FILE = ROOT / "data" / "ground_truth" / "ground_truth_annotations.json"
B2_CLEAN_FILE    = ROOT / "experiment_logs" / "B2_CLEAN_main-w3.jsonl"
B2_POISONED_FILE = ROOT / "experiment_logs" / "B2_POISONED_poisoned-w4.jsonl"

# ── Output paths ──────────────────────────────────────────────────────────────
OUT_DIR  = ROOT / "results" / "baseline"
OUT_JSON = OUT_DIR / "p4_offline_metrics.json"
OUT_MD   = OUT_DIR / "p4_offline_summary.md"

# ── Query keyword → entity_type heuristic (used in Metric 2) ─────────────────
# Keys are lowercase substrings; values are entity_type labels from events[].
# Only unambiguous, topic-specific keywords are included to avoid false intent
# attribution. Broad words like "employee" / "record" are deliberately excluded.
_KW_MAP: dict[str, str] = {
    # Compensation
    "salary":         "SALARY",
    "pay ":           "SALARY",
    "payroll":        "SALARY",
    "compensation":   "SALARY",
    "earnings":       "SALARY",
    "wage":           "SALARY",
    "remuneration":   "SALARY",
    # Medical
    "medical":        "MEDICAL",
    "health":         "MEDICAL",
    "diagnosis":      "MEDICAL",
    "prescription":   "MEDICAL",
    "treatment":      "MEDICAL",
    "condition":      "MEDICAL",
    # Contact / identity
    "address":        "ADDRESS",
    "national id":    "NATIONAL_ID",
    "national_id":    "NATIONAL_ID",
    "phone":          "PHONE",
    "telephone":      "PHONE",
    "mobile":         "PHONE",
    "email":          "EMAIL",
    # Org / role
    "department":     "DEPARTMENT",
    "division":       "DEPARTMENT",
    " team ":         "DEPARTMENT",
    "job title":      "JOB_TITLE",
    "jobtitle":       "JOB_TITLE",
    "job role":       "JOB_TITLE",
    # Location
    "office":         "OFFICE_LOCATION",
    "building":       "OFFICE_LOCATION",
    "floor ":         "OFFICE_LOCATION",
    # Performance
    "performance":    "PERFORMANCE",
    "evaluation":     "PERFORMANCE",
    "appraisal":      "PERFORMANCE",
    "review":         "PERFORMANCE",
    # Training
    "training":       "TRAINING",
    "certification":  "TRAINING",
    "course":         "TRAINING",
    # Document cross-reference (explicit file references)
    "hr_file":        "CROSS_REFERENCE",
    "hr file":        "CROSS_REFERENCE",
    "sys_config":     "CROSS_REFERENCE",
    "med_report":     "CROSS_REFERENCE",
    "memo_":          "CROSS_REFERENCE",
}


def _round4(x: float) -> float:
    return round(float(x), 4)


def _load_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _query_entity_types(query: str) -> set[str]:
    """Heuristic: entity types explicitly implied by a query string."""
    q = query.lower()
    return {et for kw, et in _KW_MAP.items() if kw in q}


# =============================================================================
# METRIC 1 — Training data leakage proxy
# =============================================================================

def compute_metric1(annotations: list[dict]) -> dict:
    """
    Corpus-level PII density — how much of the corpus a downstream trainer
    would ingest as PII-bearing training data.

    "PII entity" = annotation entity with severity >= 3.
    """
    n_docs = len(annotations)
    chunks_with_any_pii  = 0
    chunks_with_high_pii = 0
    total_pii_entities   = 0

    for doc in annotations:
        entities = doc.get("entities", []) or []
        n_pii = sum(1 for e in entities if e.get("severity", 0) >= 3)
        if n_pii > 0:
            chunks_with_any_pii += 1
        if n_pii >= 3:
            chunks_with_high_pii += 1
        total_pii_entities += n_pii

    return {
        "n_docs":                n_docs,
        "chunks_with_any_pii":   chunks_with_any_pii,
        "chunks_with_high_pii":  chunks_with_high_pii,
        "mean_pii_per_chunk":    _round4(total_pii_entities / n_docs),
        "pii_density_pct":       _round4(chunks_with_any_pii / n_docs * 100),
    }


# =============================================================================
# METRIC 2 — Retention overreach
# =============================================================================

def compute_metric2(records: list[dict]) -> dict:
    """
    Per-turn excess: how many entity types were returned beyond what the query
    implied. Measures data minimisation violations across all B2_CLEAN turns.
    """
    excess_values: list[int] = []
    turns_with_excess_gt_2 = 0

    for rec in records:
        events = rec.get("events", []) or []
        query  = rec.get("query", "")

        query_types    = _query_entity_types(query)
        response_types = {e["entity_type"] for e in events if e.get("entity_type")}

        excess = len(response_types - query_types)
        excess_values.append(excess)
        if excess > 2:
            turns_with_excess_gt_2 += 1

    n = len(excess_values)
    if n == 0:
        return {}

    sorted_excess = sorted(excess_values)
    p95_idx = max(0, int(0.95 * n) - 1)

    return {
        "n_turns":                     n,
        "mean_excess_entity_types":    _round4(sum(excess_values) / n),
        "p95_excess_entity_types":     int(sorted_excess[p95_idx]),
        "max_excess_entity_types":     int(sorted_excess[-1]),
        "turns_with_excess_gt_2":      turns_with_excess_gt_2,
        "pct_turns_with_excess_gt_2":  _round4(turns_with_excess_gt_2 / n * 100),
    }


# =============================================================================
# METRIC 3 — Cross-document linkability graph
# =============================================================================

def compute_metric3(records: list[dict]) -> dict:
    """
    Doc-pair co-occurrence graph across scenarios.
    Measures an aggregator's ability to reconstruct corpus topology
    by accumulating retrieval logs.
    """
    scenario_docs: dict[str, set[str]] = defaultdict(set)
    for rec in records:
        sid     = rec.get("scenario_id", "")
        doc_ids = rec.get("retrieved_doc_ids", []) or []
        if sid:
            scenario_docs[sid].update(doc_ids)

    n_scenarios         = len(scenario_docs)
    pair_counter        = Counter()
    pairs_per_scenario  = []
    chain_lengths       = []

    for docs in scenario_docs.values():
        docs_list = sorted(docs)
        chain_lengths.append(len(docs_list))
        pairs = list(combinations(docs_list, 2))
        pairs_per_scenario.append(len(pairs))
        for pair in pairs:
            pair_counter[pair] += 1

    total_unique_pairs = len(pair_counter)
    top_5 = [
        {"doc_a": p[0], "doc_b": p[1], "count": c}
        for p, c in pair_counter.most_common(5)
    ]

    return {
        "n_scenarios":                    n_scenarios,
        "total_unique_doc_pairs":         total_unique_pairs,
        "mean_doc_pairs_per_scenario":    _round4(
            sum(pairs_per_scenario) / n_scenarios if n_scenarios else 0
        ),
        "max_pair_count":                 int(max(pair_counter.values())) if pair_counter else 0,
        "top_5_most_linked_doc_pairs":    top_5,
        "mean_chain_length":              _round4(
            sum(chain_lengths) / n_scenarios if n_scenarios else 0
        ),
        "max_chain_length":               int(max(chain_lengths)) if chain_lengths else 0,
    }


# =============================================================================
# METRIC 4 — Vec2Text inversion risk (target enumeration only)
# =============================================================================

def compute_metric4(annotations: list[dict]) -> dict:
    """
    Enumerate "high-value" embedding targets: documents that contain both
    a named entity (PERSON) and at least one high-severity PII entity (sev >= 3).

    CRITICAL: This is target enumeration only. No vec2text inversion was run.
    """
    n_docs     = len(annotations)
    high_value = []

    for doc in annotations:
        entities   = doc.get("entities", []) or []
        has_person = any(e.get("type") in ("PERSON", "NAME") for e in entities)
        has_sev3   = any(e.get("severity", 0) >= 3 for e in entities)

        if has_person and has_sev3:
            n_sev3 = sum(1 for e in entities if e.get("severity", 0) >= 3)
            high_value.append({
                "document_id":    doc["document_id"],
                "document_type":  doc.get("document_type", ""),
                "n_sev3_entities": n_sev3,
            })

    high_value.sort(key=lambda x: x["n_sev3_entities"], reverse=True)

    return {
        "n_high_value_targets":      len(high_value),
        "pct_corpus_high_value":     _round4(len(high_value) / n_docs * 100),
        "top_5_highest_value_docs":  high_value[:5],
        "WARNING": (
            "TARGET ENUMERATION ONLY — no vec2text inversion attack was run. "
            "These documents are candidate targets for a future Phase 3 embedding "
            "inversion experiment; no reconstruction has been attempted here."
        ),
    }


# =============================================================================
# Summary markdown
# =============================================================================

def build_summary_md(
    m1: dict, m2: dict, m3: dict, m4: dict,
    n_docs: int, n_turns: int, n_scenarios: int,
) -> str:
    lines = [
        "# P4 Third-Party Aggregator — Offline Privacy Risk Analysis",
        "",
        "Generated by `scripts/analyze_p4_offline.py` (no API calls, $0 cost).",
        "",
        "## Sample Sizes",
        "",
        "| Source | Count |",
        "|--------|-------|",
        f"| Corpus documents (Phase 1) | {n_docs} |",
        f"| B2\\_CLEAN turns | {n_turns} |",
        f"| Distinct scenarios (B2\\_CLEAN) | {n_scenarios} |",
        "",
        "---",
        "",
        "## Metric 1 — Training Data Leakage Proxy",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Documents with any PII (sev≥3) | {m1['chunks_with_any_pii']}/{n_docs} ({m1['pii_density_pct']:.1f}%) |",
        f"| Documents with ≥3 PII entities | {m1['chunks_with_high_pii']}/{n_docs} ({_round4(m1['chunks_with_high_pii']/n_docs*100):.1f}%) |",
        f"| Mean PII entities per document | {m1['mean_pii_per_chunk']:.4f} |",
        "",
        "**What this means for P4:** A third-party aggregator that trains on accumulated",
        "RAG responses ingests PII-bearing content in {:.1f}% of retrieved chunks. With a".format(m1['pii_density_pct']),
        "mean of {:.2f} medium-to-high severity entities per document, even a short".format(m1['mean_pii_per_chunk']),
        "scraping campaign yields a training set dense with identifiable information.",
        "",
        "**Phase 3 mitigation:** Presidio output filtering applied at retrieval time would",
        "redact sev≥3 entities before chunks are returned, reducing effective pii\\_density\\_pct.",
        "",
        "---",
        "",
        "## Metric 2 — Retention Overreach",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total turns analysed | {m2.get('n_turns', 0)} |",
        f"| Mean excess entity types per query | {m2.get('mean_excess_entity_types', 0):.4f} |",
        f"| P95 excess entity types per query | {m2.get('p95_excess_entity_types', 0)} |",
        f"| Max excess entity types in one turn | {m2.get('max_excess_entity_types', 0)} |",
        f"| Turns with >2 excess types | {m2.get('turns_with_excess_gt_2', 0)} ({m2.get('pct_turns_with_excess_gt_2', 0):.1f}%) |",
        "",
        "**What this means for P4:** The RAG system returns entity types the query did",
        "not explicitly request. Each excess type is a data minimisation violation — the",
        "aggregator collects information beyond legitimate need without any active attack.",
        "",
        "**Phase 3 mitigation:** Per-query response filtering (whitelist only the entity",
        "categories the query targets) would drive mean excess toward 0.",
        "",
        "---",
        "",
        "## Metric 3 — Cross-Document Linkability Graph",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Distinct scenarios | {m3['n_scenarios']} |",
        f"| Unique co-retrieved document pairs | {m3['total_unique_doc_pairs']} |",
        f"| Mean co-retrieved pairs per scenario | {m3['mean_doc_pairs_per_scenario']:.4f} |",
        f"| Most-co-retrieved pair (max count) | {m3['max_pair_count']} times |",
        f"| Mean documents touched per scenario | {m3['mean_chain_length']:.4f} |",
        f"| Max documents touched in one scenario | {m3['max_chain_length']} |",
        "",
        "**Top 5 most frequently co-retrieved document pairs:**",
        "",
        "| Rank | Doc A | Doc B | Co-occurrences |",
        "|------|-------|-------|----------------|",
    ]
    for i, pair in enumerate(m3["top_5_most_linked_doc_pairs"], 1):
        lines.append(f"| {i} | `{pair['doc_a']}` | `{pair['doc_b']}` | {pair['count']} |")

    lines += [
        "",
        "**What this means for P4:** By accumulating retrieval logs across sessions, an",
        "aggregator can map which documents co-appear in responses. With {:.1f} documents".format(m3['mean_chain_length']),
        "touched per scenario and {total} linkable pairs overall, a sustained query".format(total=m3['total_unique_doc_pairs']),
        "campaign can reconstruct corpus topology without ever reading a raw document.",
        "",
        "**Phase 3 mitigation:** Retrieval ACL (restrict cross-document queries) and",
        "aggregation suppression (cap docs per session, randomise retrieval order) would",
        "reduce total\\_unique\\_doc\\_pairs and mean\\_doc\\_pairs\\_per\\_scenario.",
        "",
        "---",
        "",
        "## Metric 4 — Vec2Text Inversion Risk (Target Enumeration Only)",
        "",
        "> **WARNING:** This metric enumerates candidate targets only.",
        "> **No vec2text inversion attack was run.** The documents listed below",
        "> are high-value candidates for a future Phase 3 embedding-inversion experiment.",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| High-value target documents | {m4['n_high_value_targets']}/{n_docs} ({m4['pct_corpus_high_value']:.1f}%) |",
        "",
        "*Definition:* a document is \"high-value\" if it contains both a named entity",
        "(PERSON type) and at least one severity≥3 PII entity.",
        "",
        "**Top 5 highest-value embedding targets:**",
        "",
        "| Rank | Document ID | Type | Sev≥3 Entity Count |",
        "|------|-------------|------|-------------------|",
    ]
    for i, doc in enumerate(m4["top_5_highest_value_docs"], 1):
        lines.append(
            f"| {i} | `{doc['document_id']}` | {doc['document_type']} | {doc['n_sev3_entities']} |"
        )

    lines += [
        "",
        "**What this means for P4:** {:.1f}% of corpus documents contain an identifiable".format(m4['pct_corpus_high_value']),
        "person linked to high-severity attributes. These are the prime targets for an",
        "adversary using embedding inversion to reconstruct PII from vector representations",
        "without issuing explicit data-exfiltration queries.",
        "",
        "**Phase 3 mitigation:** Differential privacy noise injection at the vector store",
        "layer and retrieval ACL would reduce the accuracy of any embedding inversion",
        "attempt against these targets.",
        "",
        "---",
        "",
        "## Limitations",
        "",
        "**Metric 1 (Training data leakage proxy):** This is a corpus-level density",
        "estimate, not a demonstration of actual training-data extraction. It assumes",
        "retrieved chunks are ingested verbatim by the aggregator — real extraction",
        "success depends on the downstream training pipeline and chunking strategy.",
        "",
        "**Metric 2 (Retention overreach):** Query intent is inferred by simple keyword",
        "matching. Adversarial injection queries (e.g., jailbreak payloads) rarely",
        "contain data-category keywords, so their query\\_types set is empty — every leaked",
        "entity type counts as excess, which inflates the metric conservatively. A",
        "production measurement would use a semantic intent classifier.",
        "",
        "**Metric 3 (Cross-document linkability):** The graph is built from RAG retrieval",
        "co-occurrence logs, not from a membership-inference or document-graph attack.",
        "It captures potential linkability given observed retrieval patterns; a real",
        "adversary would need to accumulate many sessions to achieve equivalent coverage.",
        "",
        "**Metric 4 (Vec2Text inversion risk):** Target enumeration only. The list",
        "identifies which documents would be highest-value for an embedding inversion",
        "attack, but no such attack was executed. Actual vec2text inversion requires",
        "white-box or grey-box model access and is scoped to Phase 3 / future work.",
    ]

    return "\n".join(lines) + "\n"


# =============================================================================
# Main
# =============================================================================

def main() -> int:
    t0 = time.time()

    # ── Load annotations ───────────────────────────────────────────────────────
    if not ANNOTATIONS_FILE.exists():
        print(f"ERROR: {ANNOTATIONS_FILE} not found.", file=sys.stderr)
        return 1
    with ANNOTATIONS_FILE.open(encoding="utf-8") as fh:
        ann_raw = json.load(fh)
    annotations = ann_raw["annotations"]
    n_docs = len(annotations)
    print(f"Loaded {n_docs} annotated documents from {ANNOTATIONS_FILE.relative_to(ROOT)}")

    # ── Load B2_CLEAN ──────────────────────────────────────────────────────────
    if not B2_CLEAN_FILE.exists():
        print(f"ERROR: {B2_CLEAN_FILE} not found.", file=sys.stderr)
        return 1
    b2_clean = _load_jsonl(B2_CLEAN_FILE)
    n_turns     = len(b2_clean)
    n_scenarios = len({r["scenario_id"] for r in b2_clean})
    print(f"Loaded {n_turns} turns / {n_scenarios} scenarios from {B2_CLEAN_FILE.relative_to(ROOT)}")

    # ── Load B2_POISONED (informational, not used in metrics) ─────────────────
    n_poisoned = 0
    if B2_POISONED_FILE.exists():
        b2_poisoned = _load_jsonl(B2_POISONED_FILE)
        n_poisoned  = len(b2_poisoned)
        print(f"Loaded {n_poisoned} P3 turns from {B2_POISONED_FILE.relative_to(ROOT)} (informational)")

    # ── Compute metrics ────────────────────────────────────────────────────────
    print("\n[Metric 1] Training data leakage proxy …")
    m1 = compute_metric1(annotations)

    print("[Metric 2] Retention overreach …")
    m2 = compute_metric2(b2_clean)

    print("[Metric 3] Cross-document linkability graph …")
    m3 = compute_metric3(b2_clean)

    print("[Metric 4] Vec2Text inversion risk (target enumeration) …")
    m4 = compute_metric4(annotations)

    # ── Write JSON output ──────────────────────────────────────────────────────
    output = {
        "metadata": {
            "script":              "analyze_p4_offline.py",
            "n_docs":              n_docs,
            "n_turns_b2_clean":    n_turns,
            "n_turns_b2_poisoned": n_poisoned,
            "n_scenarios":         n_scenarios,
            "sources": {
                "annotations": str(ANNOTATIONS_FILE.relative_to(ROOT)),
                "b2_clean":    str(B2_CLEAN_FILE.relative_to(ROOT)),
                "b2_poisoned": str(B2_POISONED_FILE.relative_to(ROOT)),
            },
        },
        "metric1_training_leakage_proxy":   m1,
        "metric2_retention_overreach":      m2,
        "metric3_cross_doc_linkability":    m3,
        "metric4_vec2text_inversion_risk":  m4,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_JSON.open("w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2)
    print(f"\nWrote {OUT_JSON.relative_to(ROOT)}")

    # ── Write markdown summary ─────────────────────────────────────────────────
    md = build_summary_md(m1, m2, m3, m4, n_docs, n_turns, n_scenarios)
    OUT_MD.write_text(md, encoding="utf-8")
    print(f"Wrote {OUT_MD.relative_to(ROOT)}")

    # ── Verification block ─────────────────────────────────────────────────────
    elapsed = time.time() - t0

    print()
    print("=" * 65)
    print("VERIFICATION")
    print("=" * 65)

    print(f"\nSample sizes: {n_docs} docs | {n_turns} B2_CLEAN turns | {n_scenarios} scenarios")

    print("\n[Metric 1] Training data leakage proxy:")
    print(f"  pii_density_pct      = {m1['pii_density_pct']:.2f}%")
    print(f"  chunks_with_any_pii  = {m1['chunks_with_any_pii']}/{n_docs}")
    print(f"  chunks_with_high_pii = {m1['chunks_with_high_pii']}/{n_docs}")
    print(f"  mean_pii_per_chunk   = {m1['mean_pii_per_chunk']:.4f}")

    print("\n[Metric 2] Retention overreach:")
    print(f"  mean_excess_entity_types = {m2.get('mean_excess_entity_types', 0):.4f}")
    print(f"  p95_excess_entity_types  = {m2.get('p95_excess_entity_types', 0)}")
    print(f"  max_excess_entity_types  = {m2.get('max_excess_entity_types', 0)}")
    print(f"  turns_with_excess_gt_2   = {m2.get('turns_with_excess_gt_2', 0)}"
          f" ({m2.get('pct_turns_with_excess_gt_2', 0):.1f}%)")

    print("\n[Metric 3] Cross-document linkability:")
    print(f"  n_scenarios               = {m3['n_scenarios']}")
    print(f"  total_unique_doc_pairs    = {m3['total_unique_doc_pairs']}")
    print(f"  mean_doc_pairs_per_scen   = {m3['mean_doc_pairs_per_scenario']:.4f}")
    print(f"  max_pair_count            = {m3['max_pair_count']}")
    print(f"  mean_chain_length         = {m3['mean_chain_length']:.4f}")
    if m3["top_5_most_linked_doc_pairs"]:
        top = m3["top_5_most_linked_doc_pairs"][0]
        print(f"  most-linked pair          = ({top['doc_a']}, {top['doc_b']}) × {top['count']}")

    print("\n[Metric 4] Vec2Text inversion risk (TARGET ENUMERATION ONLY):")
    print(f"  n_high_value_targets  = {m4['n_high_value_targets']}/{n_docs}")
    print(f"  pct_corpus_high_value = {m4['pct_corpus_high_value']:.2f}%")
    print("  *** WARNING: No vec2text attack was run — targets identified only ***")

    print("\n--- Sanity checks ---")
    warns = 0

    if m1["pii_density_pct"] > 95:
        print("  WARN: pii_density_pct > 95% — suspiciously high")
        warns += 1
    elif m1["pii_density_pct"] < 5:
        print("  WARN: pii_density_pct < 5% — suspiciously low")
        warns += 1
    else:
        print(f"  OK  : pii_density_pct = {m1['pii_density_pct']:.1f}%  (expected 50–95%)")

    if m3["max_pair_count"] == 1:
        print("  WARN: max_pair_count == 1 — every doc pair co-occurred at most once")
        warns += 1
    else:
        print(f"  OK  : max_pair_count = {m3['max_pair_count']}  (pairs co-occur multiple times)")

    if m4["n_high_value_targets"] == 0:
        print("  WARN: n_high_value_targets == 0 — no high-value targets found (unexpected)")
        warns += 1
    else:
        print(f"  OK  : {m4['n_high_value_targets']} high-value targets identified")

    if warns == 0:
        print("  All sanity checks passed.")

    print(f"\nTotal runtime: {elapsed:.2f}s")
    print("=" * 65)

    return 0


if __name__ == "__main__":
    sys.exit(main())
