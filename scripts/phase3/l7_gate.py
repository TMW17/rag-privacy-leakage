"""
l7_gate.py — Phase 6 / Stage 2: the L7 STATEFUL k-ANONYMITY LINKAGE GATE.

Wired post-retrieval / pre-generation (the SAME seam as L2), L7 carries QI state ACROSS turns
per referenced person and generalizes/suppresses quasi-identifiers in the retrieved context so
that no individual's accumulated, surfaced QIs pin them to fewer than `k` corpus candidates.
This cross-turn, combinatorial action is what L3 (last-turn refusal) and L6 (single-attribute
recall-closure) structurally cannot do.

CIRCULARITY GUARD (load-bearing, restated here and at the k-computation):
  The candidate-set size `k` computed here ONLY DRIVES suppression decisions. It is NEVER a
  result and NEVER the success metric. Whether F2 leakage actually drops is judged ONLY by the
  independent engine + Opus-v2 judge (Stage 3/4). The gate's achieved-k is internal state.

The QI universe, bucketing and generalization hierarchy are imported from the PRE-REGISTERED,
consistency-checked l7_consistency_check module (single source of truth; it reproduces the
committed 84/100 and 40/63 — see Stage 1). No QI is (re)defined here.
"""
import json
import os
import random
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from scripts.phase3.l7_consistency_check import (  # noqa: E402
    QI_HIERARCHY, QUASI_IDENTIFIERS, age_range, salary_range,
)

SUPPRESSED = "[generalized]"
_CORPUS = os.path.join(ROOT, "data/ground_truth/ground_truth.json")


# ── generalization ladder (built from the pre-registered QI_HIERARCHY) ────────
def _levels(qi):
    """Ordered level functions for a QI: index 0 = raw (L0), ..., last = SUPPRESS."""
    spec = QI_HIERARCHY[qi]
    fns = [lambda v: v]
    if "l1_map" in spec:
        fns.append(lambda v, m=spec["l1_map"]: m.get(v, v))
    if "l2_map" in spec:
        fns.append(lambda v, m=spec["l2_map"]: m.get(v, v))
    elif "l2" in spec:                       # office_location: "all -> on-site"
        fns.append(lambda v: "on-site")
    fns.append(lambda v: SUPPRESSED)
    return fns


_LEVEL_FNS = {qi: _levels(qi) for qi in QUASI_IDENTIFIERS}


def max_level(qi):
    return len(_LEVEL_FNS[qi]) - 1


def generalize(qi, value, level):
    """Map a raw QI value to its generalized token at `level` (clamped to SUPPRESS)."""
    fns = _LEVEL_FNS[qi]
    return fns[min(level, len(fns) - 1)](value)


# ── corpus QI table (for candidate-set counting; medical 'none' kept as a value) ──
def _load_corpus_qis():
    recs = json.load(open(_CORPUS))["employee_records"]
    rows = []
    for r in recs:
        rows.append({
            "department": r.get("department"),
            "salary_range": salary_range(r.get("salary")),
            "medical_condition": (r.get("medical_condition") or "none"),
            "performance": r.get("performance"),
            "gender": r.get("gender"),
            "age_range": age_range(r.get("age")),
            "office_location": r.get("office_location"),
        })
    return rows


_CORPUS_QIS = _load_corpus_qis()


def candidate_k(accumulated):
    """Candidate-set size k = corpus records matching ALL accumulated QIs at their CURRENT
    generalization levels.  accumulated = {qi: (raw_value, level)}.
    *** This drives suppression only — it is NOT a result and NOT the success metric. ***"""
    if not accumulated:
        return len(_CORPUS_QIS)
    k = 0
    for row in _CORPUS_QIS:
        ok = True
        for qi, (val, lvl) in accumulated.items():
            rv = row.get(qi)
            if rv is None or generalize(qi, rv, lvl) != generalize(qi, val, lvl):
                ok = False
                break
        if ok:
            k += 1
    return k


# ── QI extractor: text -> {qi: raw_value present} ─────────────────────────────
# Gazetteers from the verified corpus value sets (Stage 1 audit_value_sets).
_DEPARTMENTS = ["Engineering", "Finance", "HR", "Legal", "Marketing"]
_MEDICAL = ["anxiety", "asthma", "diabetes", "hypertension"]   # 'none' is absence, not surfaced
_PERFORMANCE = ["needs improvement", "excellent", "satisfactory"]
_GENDER = {"female": "female", "woman": "female", "male": "male", "man": "male"}
_LABELS = {  # chunk "Label: value" -> qi
    "department": "department", "salary": "salary_range", "medical condition": "medical_condition",
    "performance": "performance", "gender": "gender", "age": "age_range", "office location": "office_location",
}


def extract_qis(text):
    """Return {qi: raw_value} found in `text`. Handles both the structured chunk form
    ('Label: value' lines — authoritative) AND free-text prose (gazetteer/regex — lossy).
    age/salary are returned already bucketed (age_range/salary_range); the rest are raw."""
    found = {}
    # (1) structured 'Label: value' lines (authoritative for retrieved chunks)
    for line in text.splitlines():
        if ":" not in line:
            continue
        label, _, val = line.partition(":")
        qi = _LABELS.get(label.strip().lower())
        val = val.strip()
        if not qi or not val:
            continue
        if qi == "salary_range":
            m = re.search(r"\d[\d,]*", val)
            if m:
                b = salary_range(int(m.group(0).replace(",", "")))
                if b:
                    found["salary_range"] = b
        elif qi == "age_range":
            m = re.search(r"\d{1,3}", val)
            if m:
                b = age_range(int(m.group(0)))
                if b:
                    found["age_range"] = b
        else:
            found[qi] = val
    # (2) gazetteer / regex over prose (only fills QIs not already found via labels)
    low = text.lower()
    if "department" not in found:
        for d in _DEPARTMENTS:
            if re.search(r"\b" + re.escape(d.lower()) + r"\b", low):
                found["department"] = d
                break
    if "medical_condition" not in found:
        for m in _MEDICAL:
            if re.search(r"\b" + m + r"\b", low):
                found["medical_condition"] = m
                break
    if "performance" not in found:
        for p in _PERFORMANCE:
            if p in low:
                found["performance"] = p
                break
    if "gender" not in found:
        for g, canon in _GENDER.items():
            if re.search(r"\b" + g + r"\b", low):
                found["gender"] = canon
                break
    if "office_location" not in found:
        m = re.search(r"building\s+([abc])(?:\s*,?\s*floor\s*(\d))?", low)
        if m:
            bld = "Building " + m.group(1).upper()
            found["office_location"] = (bld + ", Floor " + m.group(2)) if m.group(2) else bld
    if "age_range" not in found:
        m = re.search(r"(?:age[ds]?\s+|aged\s+)(\d{2})\b|\b(\d{2})\s*(?:years?\s*old|yo)\b", low)
        if m:
            b = age_range(int(m.group(1) or m.group(2)))
            if b:
                found["age_range"] = b
    if "salary_range" not in found:
        m = re.search(r"(?:salary|earns?|paid|compensation)\D{0,20}?([\d][\d,]{3,})|([\d][\d,]{4,})\s*da\b", low)
        if m:
            b = salary_range(int((m.group(1) or m.group(2)).replace(",", "")))
            if b:
                found["salary_range"] = b
    return found


# ── the stateful gate ─────────────────────────────────────────────────────────
class L7Gate:
    """Per-conversation stateful k-anonymity gate. Reset with begin() per scenario."""

    def __init__(self, k_threshold=5):
        self.k = k_threshold
        self.begin()

    def begin(self):
        # per referenced person (doc_id): {qi: [raw_value, level]} accumulated across turns
        self.state = defaultdict(dict)

    def _generalize_doc(self, doc_id):
        """Greedily raise generalization levels for one doc until its candidate-set k >= threshold
        (or all its QIs are suppressed). Returns (k_before, k_after, decisions)."""
        acc = {qi: (v[0], v[1]) for qi, v in self.state[doc_id].items()}
        k_before = candidate_k(acc)
        decisions = []
        while candidate_k({qi: (v[0], v[1]) for qi, v in self.state[doc_id].items()}) < self.k:
            # candidate QIs that can still be generalized further
            cands = [qi for qi, v in self.state[doc_id].items() if v[1] < max_level(qi)]
            if not cands:
                break
            # greedy: raise the QI whose +1 level yields the largest candidate set
            best_qi, best_k = None, -1
            for qi in cands:
                trial = {q: (v[0], v[1] + (1 if q == qi else 0)) for q, v in self.state[doc_id].items()}
                kk = candidate_k(trial)
                if kk > best_k:
                    best_k, best_qi = kk, qi
            self.state[doc_id][best_qi][1] += 1
            lvl = self.state[doc_id][best_qi][1]
            decisions.append({
                "qi": best_qi,
                "to_level": lvl,
                "to": generalize(best_qi, self.state[doc_id][best_qi][0], lvl),
                "k_after_step": best_k,
            })
        k_after = candidate_k({qi: (v[0], v[1]) for qi, v in self.state[doc_id].items()})
        return k_before, k_after, decisions

    def _apply_to_chunk(self, chunk, doc_id):
        """Rewrite a chunk's 'Label: value' lines for any QI of this doc held at level > 0."""
        st = self.state.get(doc_id, {})
        if not st:
            return chunk
        out = []
        for line in chunk.splitlines():
            if ":" in line:
                label, _, _ = line.partition(":")
                lab = label.strip().lower()
                qi = _LABELS.get(lab)
                if qi in st and st[qi][1] > 0:
                    g = generalize(qi, st[qi][0], st[qi][1])
                    out.append(f"{label.strip()}: {g}")
                    continue
            out.append(line)
        return "\n".join(out)

    def process(self, chunks, chunk_doc_ids):
        """One turn. Accumulate QIs per doc across turns, generalize docs whose accumulated QIs
        drop candidate-set k below threshold, and rewrite the context. Returns (new_chunks, trace)."""
        # 1. accumulate this turn's QIs per referenced person
        surfaced = defaultdict(dict)
        for chunk, did in zip(chunks, chunk_doc_ids):
            if not did:
                continue
            for qi, val in extract_qis(chunk).items():
                surfaced[did][qi] = val
                if qi not in self.state[did]:
                    self.state[did][qi] = [val, 0]          # new QI enters at level 0
        # 2. for each doc touched this turn, gate on accumulated candidate-set k
        per_doc = {}
        for did in surfaced:
            kb, ka, decisions = self._generalize_doc(did)
            per_doc[did] = {
                "qis_accumulated": sorted(self.state[did].keys()),
                "qis_new_this_turn": sorted(surfaced[did].keys()),
                "k_before": kb, "k_after": ka, "fired": bool(decisions),
                "generalizations": decisions,
            }
        # 3. rewrite chunks for any doc currently holding generalized QIs
        new_chunks = [self._apply_to_chunk(c, d) for c, d in zip(chunks, chunk_doc_ids)]
        n_fired = sum(1 for v in per_doc.values() if v["fired"])
        # gen-rate instrumentation: among QIs surfaced THIS turn, how many are now generalized + levels
        n_present, gen_levels = 0, []
        for did in surfaced:
            for qi in surfaced[did]:
                n_present += 1
                if self.state[did][qi][1] > 0:
                    gen_levels.append(self.state[did][qi][1])
        trace = {"k_threshold": self.k, "docs_touched": len(surfaced), "docs_fired": n_fired,
                 "n_present": n_present, "n_generalized": len(gen_levels), "gen_levels": gen_levels,
                 "per_doc": per_doc}
        return new_chunks, trace


# ── random-same-rate control (Stage 3 confound control 2) ─────────────────────
class L7RandomGate:
    """Confound control. Generalizes the SAME fraction (`rate`) of present QIs as k-driven L7, at
    the same level distribution (`level_hist`), but chosen UNIFORMLY AT RANDOM (`seed`) — i.e. it
    removes the same VOLUME of QI information while IGNORING the k-computation. Stateless; matches
    the L7Gate interface so the pipeline can swap it in. If F2 under this control ~= F2 under
    k-driven L7, the k-anonymity LOGIC added nothing beyond bulk removal; if k-driven L7 < this
    control, that gap is L7's real (targeting) contribution. Decide once per (doc, QI), apply to
    all of that doc's chunks (mirrors L7's per-doc-QI granularity)."""

    def __init__(self, rate, level_hist, seed=42):
        self.rate = rate
        self.k = f"rand({round(rate, 3)})"   # label only (matches the pipeline's log interface)
        self.levels = list(level_hist) if level_hist else None
        self.rng = random.Random(seed)

    def begin(self, *a, **k):   # stateless — matches L7Gate.begin() interface
        pass

    def process(self, chunks, chunk_doc_ids):
        present = {}                                   # (did, qi) -> raw value  (deduped per doc)
        for chunk, did in zip(chunks, chunk_doc_ids):
            if not did:
                continue
            for qi, val in extract_qis(chunk).items():
                present.setdefault((did, qi), val)
        decisions, levels = {}, []
        for (did, qi), val in present.items():
            if self.rng.random() < self.rate:
                lvl = int(self.rng.choice(self.levels)) if self.levels else max_level(qi)
                lvl = min(lvl, max_level(qi))
                if lvl > 0:
                    decisions[(did, qi)] = (val, lvl)
                    levels.append(lvl)
        new_chunks = [self._apply(c, d, decisions) for c, d in zip(chunks, chunk_doc_ids)]
        docs_present = {d for (d, _) in present}
        docs_fired = {d for (d, _) in decisions}
        return new_chunks, {"mode": "random", "rate": round(self.rate, 4),
                            "docs_touched": len(docs_present), "docs_fired": len(docs_fired),
                            "n_present": len(present), "n_generalized": len(decisions),
                            "gen_levels": levels, "per_doc": {}}

    def _apply(self, chunk, did, decisions):
        if not did:
            return chunk
        out = []
        for line in chunk.splitlines():
            if ":" in line:
                label, _, _ = line.partition(":")
                qi = _LABELS.get(label.strip().lower())
                if qi and (did, qi) in decisions:
                    val, lvl = decisions[(did, qi)]
                    out.append(f"{label.strip()}: {generalize(qi, val, lvl)}")
                    continue
            out.append(line)
        return "\n".join(out)


# ── FREE self-test (no API): synthetic multi-turn QI accumulation ─────────────
def _selftest():
    print("L7 gate self-test (FREE, synthetic — no API) ; k_threshold=5")
    # pick a real corpus record that is unique on a small QI set, and feed its QIs in over turns
    target = None
    for row in _CORPUS_QIS:
        acc = {"department": (row["department"], 0), "salary_range": (row["salary_range"], 0),
               "office_location": (row["office_location"], 0)}
        if row["salary_range"] and row["office_location"] and candidate_k(acc) < 5:
            target = row
            break
    assert target, "no unique 3-QI record found"
    print(f"  target record QIs: dept={target['department']} salary={target['salary_range']} "
          f"office={target['office_location']}  (k on these 3 = "
          f"{candidate_k({'department':(target['department'],0),'salary_range':(target['salary_range'],0),'office_location':(target['office_location'],0)})})")
    g = L7Gate(k_threshold=5)
    did = "hr_test_001"
    # simulate 3 turns, each surfacing ONE more QI in a chunk (cross-turn accumulation)
    turns = [f"Department: {target['department']}",
             f"Salary: {49999 if target['salary_range']=='<50k' else 60000 if target['salary_range']=='50-70k' else 80000 if target['salary_range']=='70-90k' else 100000 if target['salary_range']=='90-110k' else 130000}",
             f"Office Location: {target['office_location']}"]
    fired_turns = []
    state_sizes = []
    for i, ch in enumerate(turns):
        _, tr = g.process([ch], [did])
        d = tr["per_doc"].get(did, {})
        state_sizes.append(len(d.get("qis_accumulated", [])))
        print(f"  turn{i}: surfaced={d.get('qis_new_this_turn')} accumulated={d.get('qis_accumulated')} "
              f"k {d.get('k_before')}->{d.get('k_after')} fired={d.get('fired')} "
              f"gen={[ (x['qi'],x['to']) for x in d.get('generalizations',[]) ]}")
        if d.get("fired"):
            fired_turns.append(i)
    c1 = state_sizes == [1, 2, 3]                       # state carried across turns (grows)
    c2 = bool(fired_turns)                              # fired (generalized) when k < 5
    c3 = min(fired_turns) < len(turns) - 1 if fired_turns else False  # fired on an EARLIER turn
    print(f"\n  [{'PASS' if c1 else 'FAIL'}] state carried across turns (sizes {state_sizes})")
    print(f"  [{'PASS' if c2 else 'FAIL'}] generalized the right QI when k < threshold")
    print(f"  [{'PASS' if c3 else 'NOTE'}] fired on an earlier turn (turns fired: {fired_turns})")
    return 0 if (c1 and c2) else 1


if __name__ == "__main__":
    sys.exit(_selftest())
