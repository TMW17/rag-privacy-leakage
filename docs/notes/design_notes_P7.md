# Phase 7 — design spine: ingestion-time generalization (kill the QI combination at the source)

> **STAGE 0 (this document): design + asset audit only. No corpus rebuild, no embedding, no API spend.**
> Reviewed before any build, like every chapter/phase spine.

> **HONEST FRAME.** This is an experiment, not a planned win. Expected outcome: a partial F2 reduction at
> a benign-utility cost — possibly a third clean negative. The deliverable is the tradeoff curve, whatever
> it shows. Do NOT design toward a win. (Linkage already resisted redaction and the query-time L7 gate; see
> [[phase6-L7-linkage-gate]].)

---

## 1. The mechanism, and why it differs structurally from L7

**L7 (Phase 6, committed null).** A stateful *query-time* gate generalized the *retrieved chunks*
post-retrieval. It failed: the judged F2 did not move (gate = random = baseline = 0.7 at the clean k=2
cell). **Crucially, the unredacted record still lived in the index** — L7 only altered the copy that came
back from a given query, so the identifying combination was always one retrieval away.

**P7 (this phase).** Generalize the **ground-truth records themselves, at ingestion**, *before* they are
serialized (`_employee_text`), chunked, and embedded — so the vector store **never contains** a chunk that
pins anyone below `k`. The intervention is on the **corpus/index**, evaluated with the **baseline RAG (no
query-time defense layer)**; it is orthogonal to L1–L7.

**The structural difference (the honest reason P7 *might* succeed where L7 didn't):**
- L7 acts **after retrieval** — the unredacted record is still in the index and can be surfaced.
- P7 acts **before indexing** — the unredacted record is **never in the index at all**.

**And the honest reasons it might still fail:** (a) the *generalized* corpus may still be unique (k-anonymity
on a 100-record, QI-dense corpus can leave residual singletons unless generalized hard); (b) reaching `k`
may require **near-blanket** generalization, which both destroys benign utility and re-introduces the
bulk-redaction confound (now at the corpus level — see §4); (c) the leak may be carried by attributes
outside the QI set (names, free-text), which ingestion k-anonymity does not touch.

---

## 2. The generalization policy (reuse the pre-registered hierarchy)

Reuse the **frozen, consistency-checked QI hierarchy** from Phase 6 (`l7_consistency_check.py:QI_HIERARCHY`
— the same 7 QIs `{department, salary_range, medical_condition, performance, gender, age_range,
office_location}`, the same generalization ladders, **verified to reproduce the committed 84/100 + 40/63**
and re-confirmed exit-0 in this audit). No QI is (re)defined.

**Global k-anonymity at ingestion.** Apply the ladders to the *whole corpus* until every equivalence class
(records sharing the same generalized QI tuple) has size **≥ k** *against the generalized corpus itself* —
global k-anonymity, not the per-query candidate-set L7 computed. Algorithm: a Datafly-style full-domain
recoding — iteratively raise the generalization level of the QI with the most distinct remaining values
until no equivalence class is smaller than `k`, then suppress any residual outliers. (Implementation is
Stage 2; this spine fixes the policy, not the code.)

**Target-k sweep `{2, 5, 10}`** — identical to L7, for direct comparability of the two interventions.

The generalized records are re-serialized with the existing `_employee_text` and chunked with the existing
512/64 splitter, then embedded into a **new ChromaDB collection per arm** (e.g.
`p7_kgen{2,5,10}_seed42`, `p7_random_seed42`); the baseline collection `phase2_baseline_seed42` is
**untouched**.

---

## 3. Circularity guard (same discipline as L7)

The re-identification `k` drives **which records are generalized to which level** — it is **NEVER** the
success metric (that would be circular: generalizing to k makes k rise by construction). **Success =
judged F2** (engine + the validated **Opus-v2** judge) on the F2 attacks run against a RAG built over the
**generalized corpus**, compared to the committed baseline. Achieved-k is internal state, never reported as
a result.

---

## 4. The two confound controls (same as L7, lifted to the corpus level)

1. **Random-same-rate corpus.** Generalize the **same number of QI-cells** (record × QI) as the k-driven
   corpus, chosen **at random** rather than by k, to a matched level distribution (seed 42). This separates
   *"principled k-anonymity at ingestion"* from *"we blurred a large fraction of the corpus."* If F2 falls
   the same on the random corpus, the k-anonymity logic added nothing over bulk corpus degradation.
2. **gen_rate / information-loss, reported alongside F2, with a pre-registered reading rule.** Report the
   fraction of QI-cells generalized (and mean level) at each k. **Rule (fixed before the run):** an F2 drop
   that only appears at **near-blanket** corpus generalization is *"the corpus was gutted,"* **not**
   *"ingestion-time k-anonymity works"* — the effectiveness-claim analogue of the circularity guard.

---

## 5. Utility measurement (this matters MORE here than in L7)

L7 only altered chunks for attack queries; **P7 degrades the corpus for *every* query.** A benign user
asking a legitimate question now retrieves *generalized* records. So P7 **must** measure benign utility on
the **generalized corpus**, at each k, with the thesis's committed metrics — **faithfulness** and
**context-precision** (RAGAS definitions via `utility_runner.py`, the Opus-4.7 judge) — over the **30
committed benign queries** (`benign_queries.json`, each with `query` + `reference_answer`). Because
context-precision scores retrieved chunks against the *original* reference answer, it directly captures the
information lost to generalization (e.g. "which departments?" answered from a corpus where departments are
coarsened).

**The central tension, stated up front:** ingestion generalization that reduces F2 will **also** reduce
benign utility, possibly severely. The experiment's honest core is the **F2-vs-utility tradeoff curve
across k** — not an F2 number in isolation.

---

## 6. Evaluation plan

**Corpora (arms):** (a) **baseline** `phase2_baseline_seed42` (committed, reused); (b) **k-generalized**
×{2,5,10}; (c) **random-same-rate** (matched volume). Each is a separate ChromaDB collection built by the
modified index pipeline over the (generalized) records.

**Workloads:** the **10 live F2 attacks** (unchanged) + the **30 benign utility queries** (unchanged), run
against each corpus with the **baseline RAG** (`RAGSystem(collection)` — no query-time defense layer).

**Metrics:** judged-strict **F2** (engine + Opus-v2 judge), **gen_rate / info-loss** per k, **benign
utility** (faithfulness, context-precision). Never achieved-k.

**Staging (engine-first, as in L7):** engine F2 as a free direction check, then the Opus-v2 judge — but
note the engine's linkage-blindness (κ=−0.10) again limits it; the judge is the verdict. Utility needs the
judge regardless (RAGAS is judge-computed).

**Invariants (identical to the thesis):** SUT Sonnet 4.6 / temp 0 / max_tokens 1024; judge Opus 4.7 /
prompt v2 / Anthropic; embeddings all-MiniLM-L6-v2; ChromaDB top-k 5; chunk 512/64; seed 42.

**Budget (Stage 2+, not now):** embedding the generalized corpora is local/free; the spend is the SUT (F2
+ benign × 4–5 corpora) and the Opus judge (F2 verdicts + RAGAS utility). Estimate at Stage-2 pre-flight;
engine-first to gate the judge spend.

---

## 7. Honest expectations (pre-registered)

- P7 **may** reduce F2 where L7 did not — it removes the record from the index rather than the retrieved
  copy. It **may not** — generalized records can remain unique, or reaching `k` may demand near-blanket
  generalization (the §4 confound at corpus scale).
- P7 **will** cost benign utility; the only question is how much for how much F2.
- A reduction that appears **only** at near-blanket gen_rate, or that the random-same-rate corpus matches,
  is **not** a win for k-anonymity — it is corpus degradation. Read against §4.
- Whatever the tradeoff curve shows is the result. No optimization toward a win; a third clean negative is
  a legitimate, publishable outcome that further strengthens the intractability claim.

---

## 8. Asset audit (verified on disk — path · schema · status)

| Asset | Path | Schema / note | Status |
|---|---|---|---|
| QI hierarchy + check | `scripts/phase3/l7_consistency_check.py` | `QI_HIERARCHY` (7 QIs, ladders); re-ran → **exit 0**, reproduces 84/100 + 40/63 | **EXISTS / PASS** |
| Ground-truth records | `data/ground_truth/ground_truth.json` | 155 docs / 100 `employee_records` with the 7 QI fields (+ name etc.) | **EXISTS** |
| Record→chunk serializer | `scripts/build_index.py` → `_employee_text` (l.93), `chunk_document` (l.234) | "Label: value" lines; split 512/64. **P7 generalizes the record dict BEFORE `_employee_text`.** | **EXISTS** |
| Index-build pipeline | `scripts/build_index.py` | ChromaDB `PersistentClient` @ `data/rag_index/chromadb`, all-MiniLM-L6-v2, collection `phase2_baseline_seed42`. P7 builds new per-arm collections. | **EXISTS** |
| F2 attack scenarios | `scenarios/registry/v1_queries.json` | 10 live F2 (P1-LINK-001..007 + P2-LINK-001..003) | **EXISTS** |
| **Benign utility set** | `results/phase3/utility/benign_queries.json` | **30 queries**, each `{id, query, reference_answer, dimension}` | **EXISTS** ✓ |
| Utility harness | `scripts/phase3/utility_runner.py` | RAGAS faithfulness / context-precision / relevancy via Opus-4.7 judge. **`make_systems` hardcodes the baseline collection → Stage-2 must add a collection parameter.** | **EXISTS (needs 1-arg extension)** |
| Baseline — F2 | `results/phase3/ablation/metrics/final_metrics.json` | committed C00000 judged F2 = **0.60** (C11111 also 0.60 — survives) | **EXISTS** |
| Baseline — utility | `results/phase3/utility/utility_results.json` | per-query C00000/C11111 faithfulness + context-precision (the comparator) | **EXISTS** |

**No missing asset. No blocker.** The one and only non-trivial Stage-2 build note is the
`utility_runner.make_systems` collection parameter (a one-argument extension, behavior-preserving).

---

## 9. Stage-0 confirmations + STOP

- **L7-vs-P7 structural difference:** L7 = query-time, after retrieval (unredacted record stays in the
  index); P7 = ingestion-time, before indexing (unredacted record never enters the index). ✔ (§1)
- **Circularity separation:** re-id k drives which records generalize; success = engine + Opus-v2 judge on
  the generalized-corpus RAG; achieved-k never reported. ✔ (§3)
- **Confound controls:** random-same-rate corpus + gen_rate/info-loss with the pre-registered
  near-blanket = corpus-gutted reading rule. ✔ (§4)
- **Benign-utility measurement plan, with the benign query set CONFIRMED TO EXIST on disk** (30 queries,
  `benign_queries.json`) — the F2-vs-utility tradeoff curve is the experiment's core. ✔ (§5, §8)
- **Honest-expectations frame:** partial reduction at a utility cost, possibly a third negative; no
  optimization toward a win. ✔ (§7)
- **Blockers:** none.

**PAUSE — Stage 0 ends here. No corpus rebuild, no embedding, no API spend until this spine + audit are
reviewed.**
