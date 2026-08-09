# Claude Code Task: Pre-Submission Blocker Fixes (Part A) — v3

> Paste this entire file into Claude Code. There is nothing to do beforehand; the
> environment setup is Phase S below, and the agent will tell you what it needs from you.

---

## 0. Context

You are working on the codebase and manuscript for a research project titled
**"Generative AI, Privacy and Personal Data: Mapping and Reducing Data Leakage in
Retrieval-Augmented Generation Systems."** The dissertation is complete and defended; a
condensed version is being prepared for submission to IEEE Transactions on Information
Forensics and Security (TIFS).

An external review identified **eight blocking defects (A1–A8)** that a reviewer would
reject the paper over. Your job is to fix them. Seven of the eight can be resolved from
data and logs that already exist in this repository — they are analysis tasks, not new
experiments.

### What the study measured (use these to verify you have the right data)

| Quantity | Value |
|---|---|
| Synthetic corpus | 155 documents, 2,190 PII annotations, Faker seed 42 |
| Attack campaign | 52 live scenarios, 8 families (F1–F8), 3 profiles (P1/P2/P3) |
| Executions | 52 × 3 runs = 156; 267 conversational turns |
| Ablation | 6 configurations, encoded `C[L1L2L3L4L5]`; 89 turns per defended cell (445 defended records total) |
| Baseline strict ASR | engine 0.192 (30/156), judge 0.288 (45/156) |
| Full-stack strict ASR | engine 0.000, judge 0.173 (27/156, = 9/52 scenarios) |
| Knee (C01100) | judge 0.192 |
| Judge validation | κ = 0.827 undefended (n=46), κ = 0.306 defended (n=46) |
| Cross-vendor judge | κ = 0.843, undefended only |
| Engine vs human | κ = 0.164 undefended, κ = −0.10 defended/linkage |
| Claimed noise floor | 0.08 judged, 0.04 engine (estimated, not measured) |
| System under test | Claude Sonnet 4.6, temperature 0 |
| Judge | Claude Opus 4.7 |
| Stack | LangChain + ChromaDB + all-MiniLM-L6-v2 (384-d), chunk 512/64, top-k 5 |
| Redaction | Microsoft Presidio + custom recognizers |

If the data you find does not reproduce these numbers, **stop and report the discrepancy
before doing anything else.** A mismatch means either you are reading the wrong files or
the published numbers are wrong — both must be resolved before any fix proceeds.

---

## 1. Hard rules (non-negotiable)

1. **Never fabricate, estimate, simulate, or interpolate a number.** Every value you
   produce must trace to a file in this repository or to a computation you performed on
   one. If a required input does not exist, write `DATA MISSING` in the output, explain
   precisely what is absent, and move to the next task. Do not fill gaps with plausible
   values. This is a paper whose entire contribution is measurement integrity; a
   fabricated number is a catastrophic failure, not a minor one.
2. **Never modify raw results files in place.** All derived output goes to
   `analysis/partA/` (create it). Raw logs stay read-only.
3. **Work on a branch:** `git checkout -b fix/part-a-blockers`. Commit after each task
   with the task ID in the message (e.g. `A2: measure run-to-run noise floor`).
4. **No paid model calls without explicit approval.** Tasks A1 and A8 may require API
   calls. Before making any, print an estimated call count and stop for confirmation.
   Always check for cached/previous outputs first.
5. **Determinism.** Any script you write must be re-runnable and produce identical
   output. Set and record seeds. No wall-clock or random dependence in results.
6. **Do not change any claim in the manuscript yourself.** You produce evidence and a
   *claims-delta* file (see §5). The author decides the wording.
7. **If a fix contradicts a published finding, say so plainly and prominently.** A result
   that flips a conclusion is the most valuable thing you can find, not a problem to
   smooth over.
8. **Record model provenance on every judgment.** Every row of every classification or
   labelling output file must carry a `classified_by_model` column naming the exact model
   that produced it (e.g. `claude-fable-5`). Every analysis markdown file must state, in
   its header, the model and effort level used. This is not bookkeeping — a mixed-model
   labelling pass is the same defect the paper itself reports, and provenance is what lets
   the author re-run only the affected rows instead of discarding the pass.
9. **Halt on a model-fallback notice.** This repository contains adversarial security
   material (jailbreak prompts, injection payloads, poisoned documents) that can trigger a
   safety-classifier fallback to a different model. If you see any notice that the model
   changed, **stop immediately**. Do not continue the current task on the new model. Record
   in `analysis/partA/MODEL_EVENTS.md`: the timestamp, the task and item you were on, the
   model before and after, and which output rows were already written. Then report and wait.
   Resuming a half-finished classification on a different model silently corrupts the
   dataset.
10. **You cannot change your own model or effort level.** `/model` and `/effort` are
    operator actions. Never claim to have switched. When a phase requires a different
    model, stop and ask the operator to switch, then confirm the new setting before
    continuing.

---

## 2. Phase S — Setup and preflight

Do this before Phase 0. Several steps need actions only the operator can take (updating
the CLI, restarting the session, switching models). For those: perform the check, state
exactly what the operator must do, and wait.

Everything in this phase is recorded in `analysis/partA/00_preflight.md`.

### S1 — Client version

Run `claude --version`. Compare against these floors:

- **Opus 5** requires Claude Code **v2.1.219** or later
- **Fable 5** requires Claude Code **v2.1.170** or later

An out-of-date client hides models from the picker rather than erroring, so a silent
downgrade to a weaker model is the failure mode here. If the installed version is below
the floor for the model this work will run on, stop and tell the operator to run
`claude update` and restart the session. Do not attempt to update the CLI from inside a
session.

Record the version and the pass/fail result.

### S2 — Disable silent model switching (critical — do this first)

Context you need in order to take this seriously: both Fable 5 and Opus 5 run safety
classifiers for cybersecurity and biology content. On either model, a cybersecurity-flagged
request re-runs on Opus 4.8, **and the session then continues on that fallback model.**

This repository is a worst case for those classifiers. It contains DAN jailbreak prompts,
Base64-encoded PII-extraction payloads, prompt-injection scenarios, and corpus-poisoning
documents. Offensive-security workloads trigger fallback frequently, often on the very
first request of a session — that request carries CLAUDE.md content and git status, so the
repository contents alone can trip the classifier before anything unusual is typed.

Why this matters more here than in ordinary coding work: if a fallback fires halfway
through A3 or A4, half the classification is produced by one model and half by another.
That is a single labelled dataset generated by two instruments — precisely the
methodological defect this paper reports. The fix must not reproduce the finding.

**Do:**

1. Read `~/.claude/settings.json` (note if it does not exist). Print its current contents.
2. Propose a merged version that adds `"switchModelsOnFlag": false`, **preserving every
   existing key**. Never overwrite the file wholesale.
3. Back up the original to `~/.claude/settings.json.bak-partA`.
4. Show the operator the diff and **ask for approval before writing**.
5. After writing, validate that the file parses as JSON.
6. Tell the operator the session must be restarted for the setting to take effect. Explain
   what changes: a flagged request will pause and offer two options — switch to the
   fallback model, or edit the prompt and retry on the current model — instead of migrating
   the session silently. **For this task the correct choice is almost always *retry*, never
   *switch*.**

**Also check and report:**

- **Headless detection.** If this session is running non-interactively (`-p` / headless), a
  flagged request ends the turn with a refusal rather than prompting. Tasks A1–A4 must be
  run interactively. If you detect headless mode, say so and stop.
- **Fallback already fired?** If a model-change notice has already appeared in this
  session, log it per hard rule 9 and tell the operator to restart on a clean session
  before proceeding.
- **Diagnostic to offer.** If the classifier fires at session start, the operator can run
  `claude --safe-mode`, which disables customizations (CLAUDE.md, skills, MCP servers,
  hooks) to determine whether those or the repository itself are the trigger. Git status
  and directory names are included either way.

### S3 — Model and effort plan

Present this table to the operator and confirm which model each phase will run on:

| Phase | Model | Effort | Why |
|---|---|---|---|
| Phase 0 — inventory | `sonnet` | default | mechanical file discovery |
| A1 cross-vendor judge | `fable` (or `opus`) | `high` | judgment plus careful metric work |
| A2 noise floor | `fable` (or `opus`) | `high` | can overturn three published verdicts |
| A3 zero-family audit | `fable` (or `opus`) | `xhigh` | the hardest judgment call in the set |
| A4 gap decomposition | `fable` (or `opus`) | `xhigh` | per-item classification, claim-critical |
| A5 ethics audit | `opus` | default | text scan and drafting |
| A6 artifact packaging | `sonnet` | default | mechanical |
| A7 statistics | `opus` | `high` | bounded, verifiable computation |
| A8 frontier figure | `opus` | default | plotting plus a cost decision |
| CLAIMS_DELTA | `fable` (or `opus`) | `high` | synthesis across all eight results |

State this rationale so the operator can decide: Fable 5 is the most capable model in
Claude Code, suited to tasks larger than a single sitting; it investigates before acting
and verifies its work more often than smaller models. Self-verification is the direct
antidote to this task's dominant failure mode — a model confidently producing a κ or a
p-value it never computed. Opus 5 is entirely adequate for the bounded tasks and cheaper.
If Fable 5 is unavailable on the operator's plan (it is not the default on any account
type, is selected with `/model fable`, and is unavailable under zero data retention), the
whole set runs fine on Opus 5 — this prompt is checkpointed so it does not depend on
single-sitting autonomy. `max` effort exists but shows diminishing returns and is prone to
overthinking; stay at `high`/`xhigh`.

Then, **at the start of every task**, ask the operator to confirm the active model and
effort level from `/status`, and record the confirmed values in that task's output header
(hard rule 8). You cannot read or change these yourself.

### S4 — Session discipline

Tell the operator: start each phase in a **fresh session** rather than switching
mid-analysis. The `/model` picker asks for confirmation when the conversation already has
output, because the next response re-reads the full history without cached context —
switching mid-run is expensive and risks context loss at exactly the wrong moment.

When a phase ends, state plainly which model the next phase needs and that a new session
is preferred.

### S5 — Path hints

Before doing any discovery, ask the operator whether they already know the paths to:

- the **defended 46-record calibration sample and its human labels** (needed by A1)
- the **52-scenario registry** (needed by A3)
- the **per-execution ablation results including retrieved document IDs and full response
  text** (needed by A2, A3, A4)

If they do, use those paths and verify them. If they don't, proceed to Phase 0 discovery.
Asking first removes the main way this task can silently read the wrong file.

### S6 — Preflight gate

Write `analysis/partA/00_preflight.md` recording: CLI version and pass/fail, the settings
file before and after, whether the session is interactive, any fallback events already
observed, the agreed model plan, and any operator-supplied paths.

**Stop. Report. Wait for confirmation before Phase 0.**

---

## 3. Phase 0 — Inventory (then stop and report again)

1. Map the repository. Produce `analysis/partA/00_inventory.md` containing:
   - Directory tree (depth 3), annotated with what each area contains.
   - Every results artifact: path, format, row count, columns/keys, date modified.
   - Where each of these lives (or `NOT FOUND`):
     - the 155-document corpus + generator script
     - the 2,190-entity annotation file
     - the 52-scenario registry (with profile/family/target-severity per scenario)
     - per-execution attack results **including retrieved document IDs and full
       response text** (baseline and all 6 ablation configurations)
     - engine (rule-based) verdicts per turn
     - judge verdicts per turn (including `leak_type`, severity, evidence quotes)
     - the two 46-record calibration samples (undefended + defended) with **human
       labels**
     - cross-vendor (gpt-oss) judge outputs
     - the 30 benign utility questions + RAGAS-style metrics per configuration
     - Presidio recall measurements per entity type
     - the k-anonymity probe (L7) and ingestion-generalization (P7) outputs
   - The manuscript source (LaTeX) and which files contain Tables 6.3–6.5, 7.4–7.7,
     8.1–8.5, and Figures 6.4–6.6, 7.2–7.7, 8.1–8.6.
2. Reproduce three sanity checks and report pass/fail:
   - Regenerate the corpus with seed 42 → exactly 155 documents; annotation pipeline →
     exactly 2,190 entities; severity distribution 135/865/490/700 for s=5/4/3/2.
   - Recompute baseline strict ASR from raw results → engine 0.192, judge 0.288.
   - Recompute full-stack strict ASR → engine 0.000, judge 0.173.
3. **Stop. Report the inventory and the sanity checks. Wait for confirmation before
   Phase 1.**

---

## 4. Phase 1 — The eight fixes

Execute in the order given. Each produces a numbered artifact in `analysis/partA/`.

At the start of every task, confirm the active model and effort with the operator (S3) and
write them into the task's output header.

---

### A1 — Break the vendor entanglement

**Problem.** The system under test (Claude Sonnet 4.6), the primary judge (Claude Opus
4.7), and the LM-redaction probe are all from one vendor. The cross-vendor corroboration
(κ = 0.843) was run **only on undefended output** — the distribution where it was least
needed. The paper's headline rests on the *defended* distribution, where the judge's
reliability collapsed to κ = 0.306 and where no independent vendor has ever checked it.

**Do:**
1. Locate the defended 46-record calibration sample and its human labels.
2. Locate the exact judge system prompt used (`judge_v2.txt` or equivalent) and the
   cross-vendor judge configuration used previously for the undefended κ = 0.843.
3. Run the **independent-vendor judge** over the 46 defended records using the *identical*
   prompt, profile, and threshold logic. Do not rewrite the prompt. If credentials are
   unavailable, write the runner script, document the exact command, and mark
   `PENDING EXECUTION`.
4. Compute, against the human labels, for **both** judges on the defended sample:
   raw agreement, Cohen's κ (with 95% CI), false-positive rate, false-discovery rate,
   false-omission rate, sensitivity, specificity, and the full 2×2 confusion matrix.
5. Compute cross-judge κ (primary vs independent) on the defended sample.
6. Re-run the calibration-corrected residual estimator
   `p = PPV·q + FOR·(1−q)` with the independent judge's rates, propagate binomial
   uncertainty, and report the interval alongside the published [5.3%, 25.8%].

**Output:** `analysis/partA/A1_cross_vendor_defended.md` + `A1_metrics.json` + a table
formatted for direct insertion as a new column in manuscript Table 7.6. `A1_metrics.json`
must record the exact model identifier and snapshot of **every** judge involved.

**Interpretation guidance (state explicitly which case holds):**
- If cross-vendor κ *also* collapses on defended output → the degradation is a property of
  the **distribution**, not of one vendor. This *strengthens* the thesis. Say so.
- If cross-vendor κ *holds up* → the degradation may be vendor-specific, and the
  single-vendor judge is a genuine threat to validity that must be stated as a limitation
  and, ideally, corrected by adopting the independent judge as primary.

**Acceptance:** the paper can state a defended-distribution reliability figure for at
least two vendors, or explicitly report that it could not and why.

---

### A2 — Measure the noise floor instead of estimating it

**Problem.** A noise floor of 0.08 (judged) / 0.04 (engine) is asserted and carries three
conclusions: (a) the input filter L1 does nothing (+0.077 "within noise"), (b) the
conversational refusal L3 does nothing (+0.058), and (c) the knee ≈ the full stack (gap
0.019). §9.7 admits the floor was *estimated per scenario*, never measured. But the
campaign ran 3 runs × 52 scenarios at temperature 0 — the variance is computable.

**Do:**
1. Determine, from the raw logs, **how many runs each ablation configuration actually
   has.** State it explicitly per configuration. (The baseline appears to have 3; the
   defended cells may have 1. If defended cells are single-run, the floor can only be
   measured at baseline and this must be stated as a limitation.)
2. For every scenario with ≥2 runs, compute the across-run leak-verdict agreement for
   **both** instruments. Report the distribution of "leaked in 0/3, 1/3, 2/3, 3/3 runs."
3. Compute the empirical run-to-run noise floor as the standard deviation of the
   configuration-level ASR across runs, and separately as the 95th percentile of
   |ASR(run i) − ASR(run j)| over all run pairs. Report both.
4. Verify the arithmetic identity that motivated this task: is
   45/156 = 15/52 exactly, and does the same identity hold per-profile
   (P1 6/18, P2 8/27, P3 1/7) and per-family (F1 7/9, F2 6/10, F5 1/5, F8 1/7)? If yes,
   run-to-run variance at baseline is **zero** and the 0.08 floor is unsupported by the
   campaign's own evidence.
5. Re-evaluate the three "within noise" verdicts against the *measured* floor. Produce a
   revised version of Table 7.5 with a `Verdict (measured floor)` column.

**Output:** `analysis/partA/A2_noise_floor.md` + `A2_run_variance.csv` + revised Table 7.5.

**Flag loudly if:** the measured floor is below 0.019, because then the knee-vs-full-stack
gap becomes a real difference and the deployment recommendation (§8.1, §9.5) changes; or
if it is below 0.077, because then the input filter's effect is not noise and the claim
"only retrieval-time redaction clears the floor" is wrong.

---

### A3 — Resolve the retrieval confound on the zero families

**Problem.** Families F3 (direct injection), F4 (obfuscation), F6 (reconnaissance) and F7
(social engineering) all report strict ASR = 0.000, and the paper concludes that "the
underlying model largely refuses adversarial manipulation." But overall retrieval
precision is 8.3%, and F3/F4/F7 never retrieved their named target document at all. A zero
is therefore indistinguishable from "there was nothing sensitive in the context to leak."
This confound undermines an RQ1 headline.

**Do:**
1. For **every execution** in F3, F4, F6, F7 (baseline configuration), extract: the
   retrieved document IDs, the full response text, and the active profile threshold.
2. Join retrieved document IDs against the annotation file. Compute, per execution,
   whether the retrieved context contained **at least one entity above the profile's
   authorization threshold**.
3. Classify each execution into exactly one bucket:
   - **(i) Refusal under pressure** — above-threshold content was in context AND the
     response refused or withheld it.
   - **(ii) Empty context** — no above-threshold entity was in the retrieved context;
     the zero is a retrieval artifact, not a refusal.
   - **(iii) Compliance below threshold** — the model complied but disclosed only
     at-or-below-threshold content.
   - **(iv) Unclassifiable** — state why.
4. For bucket (i), detect refusal using **two independent signals** (a documented pattern
   list AND the judge's own verdict/leak_type). Report disagreements between the two
   signals rather than silently picking one.
5. Repeat the same classification for **F1**, as a positive control: F1 has 0% target
   retrieval precision yet 0.778 ASR, so its executions should land overwhelmingly in a
   "leaked from non-target adjacent documents" category. This validates the classifier.

**Output:** `analysis/partA/A3_zero_family_audit.md` +
`A3_execution_classification.csv` (one row per execution, with the mandatory
`classified_by_model` column) + a new manuscript table (suggest Table 6.6).

**Model discipline:** classify every execution in a single uninterrupted pass on one
model. If a fallback notice appears mid-pass, halt per hard rule 9 and report which rows
were already written.

**Consequence to state:** if bucket (ii) dominates, the claim "adversarial manipulation is
largely refused" must be **weakened** to "adversarial manipulation did not surface
above-threshold content on this corpus, in part because the retriever did not fetch the
targeted records." That is a smaller claim, and it is the honest one.

---

### A4 — Quantify how much of the engine–judge gap is definitional

**Problem.** The paper's central methodological claim is that the deterministic engine is
*structurally blind* to semantic and cross-document leakage. But the two instruments do
not score the same taxonomy: the judge prompt assigns severity 3 to document-ID
cross-references (a category with **no corresponding entity type** in the engine's 36-type
taxonomy) and lists "religious affiliation," which §5.3 says was removed from the corpus
schema. Part of the gap may therefore be *definitional mismatch*, not perceptual blindness.

**Do:**
1. Reconstruct the baseline turn-level cross-tabulation: engine fired on 95 turns, judge
   on 57, union 115, of which 37 were both, 58 engine-only (severity-2 refusal artifacts),
   and **20 judge-only**. Verify these counts from raw data.
2. For each of the 20 judge-only turns, classify by the judge's own `leak_type` and by
   inspection of the evidence quote:
   - **(a) Cross-reference / document-ID** — definitional: the engine has no such entity
     type, so this is a taxonomy gap, not blindness.
   - **(b) Paraphrased direct PII** — genuine semantic blindness: the entity is annotated
     on a retrieved document but was reworded.
   - **(c) Cross-document linkage** — genuine emergent leakage: no single annotated span.
   - **(d) Judge false positive** — human labels say no leak.
3. Report the gap decomposition as counts and percentages. Compute what the judge–engine
   gap would be **if document-ID cross-references were excluded** from the judge's rubric.
4. Audit the judge prompt against the corpus schema. List every severity rule in
   `judge_v2.txt` that has no counterpart in Table 5.4, and every entity type in Table 5.4
   absent from the judge prompt. Produce a reconciliation table.
5. Recompute the headline baseline and full-stack judged ASR **excluding** category (a),
   as a robustness check. Report both the original and the excluded-doc-ID figures.

**Output:** `analysis/partA/A4_gap_decomposition.md` + `A4_judge_only_turns.csv` (with
`classified_by_model`) + `A4_taxonomy_reconciliation.md`.

**Model discipline:** as in A3 — one model, one pass, halt on any fallback notice.

**Expected result (verify, don't assume):** Figure 6.5 suggests cross-reference leaks are
~4.9% of turns, so categories (b) and (c) should dominate and the finding should survive.
If so, say it with the numbers. If category (a) dominates, the central methodological
claim needs substantial revision.

---

### A5 — Fix the ethics contradiction

**Problem.** Chapter 6 states "no real personal data is used at any stage." Section 8.7
runs a probe against a real Enron mailbox. The Enron corpus contains genuine
correspondence from real, non-consenting individuals. In a privacy paper this is a
credibility-destroying inconsistency.

**Do:**
1. `grep` the manuscript for every absolute claim about synthetic-only data (search:
   `no real personal data`, `wholly synthetic`, `no real person`, `machine-fabricated`,
   `correspond to no real individual`). List every occurrence with file and line number.
2. Draft a scoped replacement for each: the claim should be limited to the **main
   campaign and the released artifact**, with the Enron probe explicitly carved out.
3. Draft a 3–5 sentence ethics statement for the Enron probe covering: it is an
   established, publicly released research corpus; no re-identification of any individual
   was attempted; no personal data from it is reproduced in the paper or the released
   artifact; only aggregate disclosure counts are reported; and the reason a real-prose
   probe was methodologically necessary.
4. Scan **all** manuscript files, figures, tables, appendices, and any released data for
   Enron-derived names, email addresses, or message content. Report every hit. Nothing
   from Enron may appear verbatim.
5. Check whether the released artifact bundle (A6) would contain Enron data or derived
   annotations. If yes, exclude it and document the exclusion.

**Output:** `analysis/partA/A5_ethics_audit.md` with the occurrence list, the drafted
replacements, the drafted ethics statement, and the verbatim-content scan results.

---

### A6 — Publish the artifact

**Problem.** The entire contribution is *reproducible measurement*, TIFS explicitly
expects reproducibility materials for deep-learning papers, and there is no repository
link, DOI, or version pinning anywhere in the document.

**Do:**
1. Build a clean, self-contained artifact under `artifact/` containing:
   - corpus generator + annotation pipeline (must reproduce 155 docs / 2,190 entities
     from seed 42 — verify by hash)
   - the 52-scenario registry with profile, family, target severity, and prompts
   - the evaluation engine (L, S implementation) and the judge harness
   - all judge system prompts, verbatim, versioned
   - the 6 ablation configurations
   - raw per-execution results for every configuration
   - the calibration samples **with human labels**
   - the L7 k-anonymity probe and P7 ingestion-generalization scripts
   - the utility-measurement harness and the 30 benign questions
   - every analysis script produced in this task set
2. **Secret scan.** Search the full repository *and git history* for API keys, tokens,
   `.env` files, and connection strings. Report and remediate before anything is
   published. Do not push until this passes.
3. Pin the environment: `requirements.txt` with exact versions, plus a
   `environment_capture.json` recording Presidio version, spaCy model name+version,
   LangChain version, ChromaDB version, embedding model revision, SUT and judge model
   identifiers and snapshot dates, OS, and Python version. **Include the model identifiers
   used for the A1–A4 analyses themselves.** If a version cannot be recovered from logs or
   lockfiles, write `UNRECOVERABLE` — do not guess.
4. Write `artifact/README.md`: one-command reproduction path, expected runtime, expected
   API cost, a table mapping **every numbered table and figure in the paper** to the
   script and command that regenerates it, and a "what cannot be reproduced without API
   credentials" section.
5. Add `LICENSE` (code) and a separate data-use statement for the synthetic corpus.
6. Add `.zenodo.json` metadata and a `CITATION.cff`. Prepare the release but **do not
   publish** — report the exact steps for the author to mint the DOI.
7. Produce the LaTeX snippet for the paper's reproducibility statement, with a DOI
   placeholder.

**Output:** the `artifact/` tree + `analysis/partA/A6_artifact_report.md` documenting the
determinism verification, the secret scan result, and any `UNRECOVERABLE` items.

---

### A7 — Report real statistics

**Problem.** The headline reduction (28.8% → 17.3%) is reported as "directional, not
powered," justified by an **unpaired** two-proportion power bound that does not apply to
the study's paired design (the same 52 scenarios before and after). No confidence
intervals accompany most rates, and a single-scenario rate (F8 = 0.143) is tabled
alongside multi-scenario rates as though comparable.

**Do:**
1. Build the paired 52-scenario contingency table (baseline C00000 vs full stack C11111,
   judged verdicts): both leak / baseline only / full-stack only / neither.
2. Run **McNemar's exact test** (binomial, two-sided) on the discordant pairs. Report b,
   c, the exact p-value, and the odds ratio with CI. External estimate from the published
   tables was b ≈ 7, c ≈ 1 → p ≈ 0.07; verify against real data and report whatever it is.
3. Repeat McNemar for: baseline vs knee (C01100), and knee vs full stack.
4. Compute **Wilson 95% intervals** for every rate in Tables 6.3, 6.4, 6.5, 7.4, 8.2, 8.3,
   8.5. Produce drop-in replacement tables with intervals.
5. Compute a proper **paired** power analysis for the observed discordance, replacing the
   unpaired bound in §7.8.
6. Flag every rate resting on fewer than 5 scenarios as statistically uninterpretable —
   at minimum F8 (0.143, one scenario) and F6 (3 scenarios). Add an explicit marker and
   footnote to each affected table.
7. Note the multiple-comparison exposure (6 configurations × 8 families × 2 instruments)
   and either apply a correction to the family-level comparisons or state explicitly that
   family-level rates are descriptive, not inferential.

**Output:** `analysis/partA/A7_statistics.md` + `A7_tables.tex` (drop-in replacements) +
`A7_mcnemar.json`.

---

### A8 — Fix or drop the frontier figure

**Problem.** Figure 8.1 plots a composite `Security = 0.70·(1−judged ASR) +
0.15·precision + 0.15·prevention`. These weights appear **nowhere** in the text. The
figure's own fine print concedes that four of six configurations use *proxied*, not
measured, utility. The deployment recommendation ("deploy at the knee") is partly built on
this figure — but the prose argument (0.192 vs 0.173, inside the noise floor) does not
need the composite at all.

**Do — choose one path and state which:**

- **Path 1 (preferred): measure utility for all six configurations.** Run the 30 benign
  questions through each of C00000, C10000, C00100, C01000, C01100, C11111 and record
  faithfulness, answer relevance, context precision, latency, and refusal rate. That is
  180 executions — estimate the cost, print it, and stop for approval before running.
  Then replot the frontier with **all points measured**, and use judged ASR directly on
  the x-axis rather than a composite. This also fills the gap Table 8.1 admits (utility
  measured only at the two extremes, knee cost never isolated).
- **Path 2 (fallback, no API budget): drop the composite entirely.** Replot using only
  measured points (C00000 and C11111), plot raw judged ASR against measured context
  precision, and mark the knee's security value with the utility explicitly labelled
  "not measured." Remove all proxied points from the figure.

**In either path:**
1. If any composite score is retained anywhere, document the weights, their derivation,
   and a sensitivity analysis over alternative weightings in the text — not in a figure
   caption.
2. Fix the truncated axes or annotate the truncation; the current ranges
   (0.82–0.87 utility, 0.675–0.875 security) visually exaggerate small differences.
3. Verify that the deployment recommendation in §8.1, §9.5 and §9.6 rests on the ASR
   comparison and the noise floor, **not** on the composite. Rewrite any sentence that
   depends on the composite.

**Output:** regenerated figure source + `analysis/partA/A8_frontier.md` documenting which
path was taken, the measured values, and every manuscript sentence affected.

---

## 5. Phase 2 — Claims delta

After A1–A8, produce `analysis/partA/CLAIMS_DELTA.md`. For **every** number, table,
figure, or sentence in the manuscript whose truth status changed, record:

| Location (file:line) | Current text | New evidence | Required change | Severity |
|---|---|---|---|---|

Severity levels:
- **CRITICAL** — a headline claim is now wrong or unsupported (e.g. a "within noise"
  verdict flips, the zero-family refusal claim collapses, the engine–judge gap is mostly
  definitional).
- **MAJOR** — a number changes or a claim must be materially weakened.
- **MINOR** — a caveat, interval, or footnote must be added.

Sort by severity. Do **not** edit the manuscript prose yourself — produce the delta and
let the author decide the wording. You *may* produce drop-in LaTeX for tables and figures,
clearly marked as proposals.

---

## 6. Final deliverables

```
analysis/partA/
  00_preflight.md                  (Phase S: version, settings, model plan, paths)
  00_inventory.md
  MODEL_EVENTS.md                  (fallback/model-change log; empty file if none occurred)
  A1_cross_vendor_defended.md      A1_metrics.json
  A2_noise_floor.md                A2_run_variance.csv
  A3_zero_family_audit.md          A3_execution_classification.csv
  A4_gap_decomposition.md          A4_judge_only_turns.csv
                                   A4_taxonomy_reconciliation.md
  A5_ethics_audit.md
  A6_artifact_report.md
  A7_statistics.md                 A7_tables.tex   A7_mcnemar.json
  A8_frontier.md
  CLAIMS_DELTA.md
  SUMMARY.md
artifact/                          (self-contained reproduction bundle)
```

`SUMMARY.md` must contain, in this order:

1. A table of eight rows — one per task — each marked `RESOLVED` / `PARTIAL` /
   `BLOCKED (DATA MISSING)` / `FINDING CHANGES A CLAIM`.
2. A **model-provenance table**: which model and effort level produced each task's output,
   and whether any fallback event occurred during it.
3. A plain-language paragraph on **what changed in the paper's conclusions**.
4. A ranked list of anything still outstanding.

---

## 7. Working style

- Report after Phase S and stop for confirmation.
- Report after Phase 0 and stop for confirmation.
- Report after each of A1, A2, A3, A4 individually — these four can each overturn a
  published claim, and the author needs to see each result before you build on it.
- A5–A8 may be batched.
- Prefer a small number of well-documented analysis scripts over ad-hoc shell pipelines,
  so that every number in the final paper has a named script that regenerates it.
- When you are uncertain whether a classification is correct, output the ambiguous cases
  to a separate file for human review rather than deciding silently.
- Never split a single classification pass (A3, A4) across models or across a model
  change. One pass, one model, provenance recorded.
- If at any point you find yourself about to write a number you did not compute from data
  in this repository, stop and write `DATA MISSING` instead.

---

## 8. Amendments — v3.1 (binding from Phase 0 onward)

Issued by the operator at the start of the post-restart Phase 0 session, 2026-08-09.
These override or extend the text above wherever they conflict. Recorded here so they
survive future session restarts.

### Amendment 1 — NEW HARD RULE 11: every statistic comes from a committed script

Every statistic must be emitted by a committed, re-runnable script under
`analysis/partA/`. **No number is ever typed into prose.** Any numeric literal appearing
in a markdown deliverable without a named generating script is treated as *unverified*
and must be flagged in `SUMMARY.md`.

Before Phase 2, run a **number audit**: grep every markdown deliverable for numeric
literals and confirm each traces to a script output.

### Amendment 2 — phase entry procedure

Every phase begins by reading `TASK_SPEC.md`, then `00_preflight.md`. (This §8 is why.)

### Amendment 3 — Phase 0: `results/phase3_4/baseline_regen/`, expanded

**(a) Provenance from file contents, not inference.** Determine what the regen is from:
the judge model identifier inside `judge_cache_regen.jsonl`; the config in the two
`_summary.json` files; file mtimes; and whether the regen response text is byte-identical
to `experiment_logs/B2_CLEAN_main-w3.jsonl`. **Report findings before classifying.**

**(b) If it IS a re-judge, do not set it aside.** It then measures *judge-side variance* —
the second, equally unmeasured half of the 0.08 floor. Judged ASR carries variance from
**both** the SUT and the judge, and the paper never separates them. A2 must report the
floor **decomposed**: SUT variance (3 baseline runs) + judge variance (re-judge). If the
judge returned any different verdict on byte-identical input, that is a finding for
`CLAIMS_DELTA` — the primary instrument is not deterministic.

**(c) Canonicity.** The canonical baseline is whichever source reproduces
**engine 0.192 / judge 0.288**. If both do, say so. If they disagree, or if neither
reproduces, **STOP and report at CRITICAL severity** — that would mean the published
baseline is not reproducible. Do not pick one and proceed.

### Amendment 4 — Phase 0: truncated response text

If response text is truncated, check whether the judge's `evidence_quote` fields were
persisted. The judge prompt requires exact verbatim quotes, so they are a **partial**
substitute for A4's classification of the 20 judge-only turns. They do **not** rescue A3,
whose refusal detection needs the whole response. Report exactly which of A3/A4 each
available field supports **before** declaring either `BLOCKED`.

### Amendment 5 — corrected model/effort confirmation procedure

`/status` does **not** report effort — Model only. §3's instruction to confirm both from
`/status` is only half-satisfiable. Corrected procedure, in force from Phase 0 onward:

- **Model** — from `/status`.
- **Effort** — from the session header next to the model name, or from `/effort`.

### Amendment 6 — Phase S effort is permanently unconfirmable

Record it as: *"ultracode — observed from transcript, never confirmed; `/status` does not
report effort and the session has since restarted."* Do not upgrade it to confirmed.
Phase S produced no statistics, so nothing downstream depends on it.

### Amendment 7 — resolved model ID in every header

Record the resolved model ID (`claude-opus-5`, 1M context) in every header from Phase 0
on, and note in A6's `environment_capture.json` whether it was reached via **Default** or
an **explicit pin**.

### Amendment 8 — effective settings, not file contents

Two setting sources are active (User + Project local). Verify the **effective** value of
`switchModelsOnFlag`, not just the contents of `~/.claude/settings.json`: check whether
any project-local file also sets it, and report the precedence outcome.

Also report whether the 6 unauthenticated MCP servers are needed for Part A; if not, note
that disabling them reduces context bloat and first-request classifier surface.

### Two verifications on the cleanup commits (Part A builds on them)

- `git show --stat 34f9c02` — confirm all 39 deletions were build artifacts, no source
  file caught.
- `git log -p -- test.py | grep -i -A2 bearer` — confirm the OpenRouter value was the
  literal placeholder in **every** historical version, not a live key later replaced.
  A6's secret scan blocks on this.
