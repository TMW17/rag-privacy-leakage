# Annotation-Count Reconciliation Report

**Question.** Two documents report different annotation counts for the *same*
seed-42 corpus:

| | Total | Distinct types | Severity-5 |
|---|---|---|---|
| **State A** — Phase 1 `.tex` (`Formal_Leakage_Definitions_and_Ground_Truth.tex`, `phase1.tex`) | 2,315 | 33 | 235 |
| **State B** — Phase 2 report, `Phase1.md`, frozen artifacts, `PROJECT.md` | 2,190 | 31 | 135 |
| **Delta (B − A)** | **−125** | **−2** | **−100** |

Reproduce the count from the frozen corpus and localize where the 125 entities,
2 types, and 100 severity-5 went. *This report does not pick which document is
correct — see §6.*

---

## 1. Fresh count (re-run on the frozen corpus)

`reconcile_annotations.py` imports the four annotation functions from
`scripts/annotate_dataset.py` and applies them to the frozen
`data/ground_truth/ground_truth.json` (seed 42). It never executes either
pipeline script's `__main__`, and writes only inside this directory — **no
frozen artifact was regenerated or modified** (`git status` clean for
`data/ground_truth/` and `scripts/`).

```
Total entities tagged : 2,190
Distinct types        : 31   (of a 35-entry ENTITY_SPECS dict)
Severity histogram    : {5: 135, 4: 865, 3: 490, 2: 700}
LINDDUN               : Identifiability 1060, Unawareness 500,
                        Disclosure 264, Detectability 225, Linkability 141
```

**Integrity check:** the fresh re-run reproduces the frozen
`ground_truth_annotations.json` *exactly* at the per-type level — confirming the
frozen answer key equals what the current code emits (it was not hand-edited).

> **"Distinct types" denominator.** `CROSS_REFERENCE` is created inline and is
> not in `ENTITY_SPECS`. "Distinct types in the annotations" = **31** (= 30
> spec-types that receive instances + `CROSS_REFERENCE`). The `ENTITY_SPECS`
> dictionary holds **35** entries (5 defined-but-unused: `CREDIT_CARD`,
> `PASSPORT_ID`, `QUASI_IDENTIFIER`, `PARTIAL_ADDRESS`, `MEMBERSHIP`).

---

## 2. Which document does the fresh count reproduce?

**State B (2,190), unambiguously.** The fresh re-run equals the Phase 2 report,
`Phase1.md`, `PROJECT.md`, and the frozen artifacts to the entity. It does **not**
reproduce the Phase 1 `.tex` terminal box (2,315 / 235). The two `.tex` files are
a **stale pre-cleanup snapshot** (State A), recoverable verbatim from git artifact
`1a19e73` — the script's git cross-check confirms `1a19e73`'s per-type counts equal
the embedded State-A table (`MATCH`).

---

## 3. Per-type and per-severity diff (A → B)

The 125-entity gap localizes to **exactly five types**; everything else is
unchanged:

| Type | Severity / LINDDUN | A (2,315) | B (2,190) | Δ | Cause |
|---|---|---:|---:|---:|---|
| **SSN** | 5 / Identifiability | 100 | 0 | **−100** | **removed** (redundant duplicate of `NATIONAL_ID`) |
| **RELIGIOUS** | 3 / Disclosure | 43 | 0 | **−43** | **removed** ("Religious feature") |
| MEDICAL | 3 / Disclosure | 83 | 93 | +10 | corpus-regen reshuffle |
| IMMIGRATION | 3 / Disclosure | 29 | 36 | +7 | corpus-regen reshuffle |
| CROSS_REFERENCE | 3 / Linkability | 40 | 41 | +1 | corpus-regen reshuffle |
| *(all 28 other types)* | — | = | = | 0 | unchanged |

**Net:** −100 − 43 + 10 + 7 + 1 = **−125.** ✓

**Per severity** (every bucket reconciles):

| Severity | A | B | Δ | Accounted by |
|---|---:|---:|---:|---|
| 5 | 235 | 135 | **−100** | SSN (−100) |
| 4 | 865 | 865 | 0 | — |
| 3 | 515 | 490 | **−25** | RELIGIOUS (−43) + MEDICAL (+10) + IMMIGRATION (+7) + CROSS_REF (+1) |
| 2 | 700 | 700 | 0 | — |

**Per LINDDUN:** Identifiability −100 (SSN); Disclosure −26 (RELIGIOUS −43,
MEDICAL +10, IMMIGRATION +7); Linkability +1 (CROSS_REF). All exact.

---

## 4. Hypothesis tests

These are **one mechanism**, not three independent facts. Removing the `SSN` and
`RELIGIOUS` *fields/specs* required regenerating the corpus with the modified
generator. Under the same seed 42, dropping per-record random calls shifts the
downstream PRNG stream, so the conditional/sampled fields redraw — which is what
produces the +18 reshuffle (`MEDICAL`/`IMMIGRATION`/`CROSS_REFERENCE`). The arithmetic:
**−143 removed + 18 reshuffle = −125.**

**(a) Was the corpus regenerated between phases? — YES (intentional, recorded).**
Git commit `a541481` is titled *"Corpus regenerated: 2,280 → 2,190 entities,
remove Religious feature; purge API key"*; commit `f974351` ("removing the
Religious feature") also rewrote the corpus. The current frozen corpus is the
post-regeneration seed-42 corpus, and it remains reproducible: under seed 42 all
**annotation-relevant** draws (national IDs, names, salaries, categoricals,
memo samples) are byte-identical; only today-relative date fields
(`date_of_birth`, visit/memo dates, and 5 derived ages) drift on re-run — a latent
non-determinism in `generate_dataset.py` that affects **no count**. *(Noted, not
in scope to fix.)* The +18 reshuffle above is the count-level footprint of this
regeneration.

**(b) Were 2 entity types removed from the schema? — YES, exactly 2: `SSN` and
`RELIGIOUS`.** `ENTITY_SPECS` went **37 → 35** (`entity_spec_count` in the frozen
metadata is 35). The same two are the −2 in "distinct types in annotations"
(33 → 31). Both framings give 2 and name the same pair.

**(c) Sev-5 drop is exactly 100 — a 100-instance class? — YES: `SSN`, dropped as a
redundant duplicate (not reclassified).** State A annotated **two** sev-5
Identifiability fields per HR record — `ssn` → `SSN` **and** `national_id` →
`NATIONAL_ID` (100 each). Both modelled the national identity number; the cleanup
removed the redundant `ssn` and kept the Algerian NNI (`NATIONAL_ID`). That single
deletion is the **entire** −100 in severity-5 and −100 in Identifiability. This is
coverage **de-duplication**, not coverage loss.

---

## 5. The full chain (git-traced)

| Commit | Event | Total | Sev-5 | Specs |
|---|---|---:|---:|---:|
| `1a19e73` | Phase 1 complete (= `.tex` State A) | 2,315 | 235 | 37 |
| `f974351` | remove RELIGIOUS field + regen | 2,280 | 235 | 37 |
| `a541481` | remove SSN dup, drop SSN+RELIGIOUS specs, regen, purge API key | 2,190 | 135 | 35 |
| `HEAD` | current (= frozen) | 2,190 | 135 | 35 |

---

## 6. Your decision (not made here)

**Neither count is an "error" — each is correct for its schema.**

- **2,190** is the current, frozen, reproducible value. The fresh re-run, the
  frozen answer key, `git HEAD`, the Phase 2 report, `Phase1.md`, and `PROJECT.md`
  all agree, and the locked Phase 2 metrics (ASR_strict, κ) rest on this corpus.
  **No canonical number is contradicted by this analysis** — so no stop condition
  was triggered.
- **2,315** survives only in the two `.tex` files (`Formal_Leakage_Definitions_and_Ground_Truth.tex`,
  `phase1.tex`) as the pre-cleanup (State-A) snapshot, before `SSN` and
  `RELIGIOUS` were removed.

The decision is whether the thesis text should reflect the post-cleanup schema.
If yes, the two `.tex` files are the documents to update (terminal box →
2,190 / 31 distinct types / sev-5 135, and the LINDDUN line), and the prose about
the entity taxonomy should drop `SSN`/`RELIGIOUS`. This report does not make that
edit.

---

### Artifacts in this directory
- `reconcile_annotations.py` — non-destructive re-run + diff generator
- `fresh_count.json` — deliverable #1 (fresh counts + integrity check)
- `version_diff.json` — deliverable #3 (per-type / per-severity / per-LINDDUN diff)
- `reconciliation_report.md` — this report
