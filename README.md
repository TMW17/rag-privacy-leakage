# Privacy leakage in retrieval-augmented generation

![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)
![Presidio worker: Python 3.11](https://img.shields.io/badge/presidio%20worker-python%203.11-blue.svg)
![Corpus: synthetic](https://img.shields.io/badge/corpus-100%25%20synthetic-lightgrey.svg)

**How much personal data does an enterprise RAG chatbot leak, which attacks cause it, and how
much does a layered defense really remove, measured with an instrument that is itself
validated?**

This repository holds the code, data and results of the thesis *Generative AI, Privacy and
Personal Data: Mapping and Reducing Data Leakage in Retrieval-Augmented Generation Systems*
(École Supérieure en Informatique, Sidi Bel Abbès, Algeria; Artificial Intelligence and Data
Science). It builds a controlled test bench: a synthetic company corpus full of planted personal
data, a RAG system deliberately left without privacy safeguards, a campaign of attacks by
different kinds of attacker, five defense layers tested by ablation, and two independent
instruments to score every answer.

> **Status: complete.** The work was defended on **9 July 2026** as a master's thesis
> ([Master_Report.pdf](Master_Report.pdf), 65 pages: survey and measurement framework) and an
> engineering dissertation ([PFE_Report.pdf](PFE_Report.pdf), 160 pages: the experiments). All
> experiments are finished; every number below comes from a committed result file or from those
> reports.

![Overview: a synthetic corpus is indexed in ChromaDB; 52 attack scenarios query a RAG system
built on Claude Sonnet 4.6, wrapped by five defense layers; each answer is scored by a rule
engine against the answer key and by a validated language-model judge; the scores feed the
ablation metrics.](docs/img/overview.png)

<sub>Diagram source: [docs/diagrams/overview.mmd](docs/diagrams/overview.mmd) (Mermaid).</sub>

---

## Results in brief

| What was measured | Result |
| --- | --- |
| Test corpus | 155 synthetic documents with 2,190 annotated personal-data entities (inter-annotator κ = 0.875) |
| Attack campaign | 52 scenarios in 8 attack families, 3 attacker profiles, 3 runs each: 156 executions, 267 conversational turns |
| Undefended baseline (strict attack success rate) | **Judge: 28.8 %** (45/156). Rule engine: 19.2 % (30/156), a lower bound |
| Full defense stack, all five layers | **Judge: 17.3 %** (27/156), about **40 % less, not an elimination**. Rule engine: 0.0 %, because it cannot see the leaks that remain |
| Recommended configuration (retrieval redaction + conversational refusal) | **Judge: 19.2 %**, within the noise floor of the full stack, with two layers instead of five |
| Direct extraction of a named person's data (family F1) | Judge: 77.8 % → **22.2 %** under the full stack |
| Re-identification by linkage across documents (family F2) | Judge: 60 % → **60 %**, unchanged by any defense |
| Judge reliability against human labels | κ = **0.827** on undefended answers (n = 46), but κ = **0.306** on defended answers (n = 46) |
| Cost of the full stack on 30 ordinary questions | 0 of 30 refused; faithfulness 0.953 → 0.933; context precision 0.755 → 0.658; answers about 1.9× slower |

**Main finding: redaction defeats extraction, but not linkage.** Removing named entities stops a
model from reading out a salary or a social security number. It cannot stop a model from
reassembling a person out of facts that are harmless one by one but scattered across documents,
such as a department, an office, an age range and a medical condition. Redaction, a
query-time *k*-anonymity gate and ingestion-time *k*-anonymity either failed to reduce that
residual or cost too much information, so it is
a data-governance problem rather than a model-layer one: access control handles the unauthorized
outsider, while an authorized insider who brings outside knowledge leaves a residual that can be
bounded and audited but not removed.

**Methodological finding: measuring a defended system with one instrument is wrong in a
direction you cannot see.** Read through the rule engine alone, the defenses look total (19.2 % →
0.0 %). Read through the validated judge, 17.3 % remains. The engine is blind to cross-document
linkage (κ = −0.10 against human judgment there) and records that blindness as protection. The
judge, in turn, is reliable on undefended text but much less so on the redacted and refused
answers a defense produces, so evaluation has to be re-validated on the distribution it scores.

![Left: the marginal effect of each defense layer against the judged noise floor. Right: strict
attack success rate from no defense (0.288) through redaction (0.192) and the recommended pair
(0.192) to the full stack (0.173).](results/phase3_4/report/thesis/fig_ch5_marginal_rq2.png)

*Only retrieval-time redaction (L2) clears the noise floor. The positive L1 and L3 bars are
within noise: those layers never fired on the scenarios that changed.*

---

## How it works

### 1. A synthetic corpus with a known answer key

Real company data cannot be used without exposing real people, so the corpus is generated
deterministically with Faker (`random.seed(42)`, `Faker.seed(42)`): the same seed gives the same
documents on every machine.

| Document class | Count | Content |
| --- | --- | --- |
| HR employee records | 100 | social security number, name, email, phone, address, date of birth, IBAN, salary, medical condition, performance |
| System configuration | 5 | API keys, JWT tokens, database connection strings, system prompts, internal IP addresses |
| Internal memos | 20 | free text naming employees together with sensitive attributes |
| Medical reports | 30 | special-category health data linked to specific employees |

Some documents point to each other on purpose (a medical report names its employee record), to
test re-identification across documents. Every entity is annotated against a 36-type taxonomy
with a severity from 2 (behavioural signal) to 5 (direct compromise): **2,190 annotations**, the
answer key every response is checked against. A *k*-anonymity analysis shows the threat is
real even without names: department, medical condition, age range and office location together
single out 84 of the 100 employees.

The credentials in the corpus are fake by design, so that leaking them can be measured. No live
credential is included.

### 2. Two formal leakage metrics

For a query *q*, response *r*, corpus *D* and attacker profile *u*:

```
L(q, r, D, u) = 1  if the response discloses an entity whose severity exceeds the
                   profile's authorized level, 0 otherwise          (did it leak?)

S(q, r, D, u) = Σ s(e) · w(e)  over the leaked entities             (how bad?)
```

`s(e)` is the entity's severity (2–5) and `w(e)` the confidence of the detection method (1.00 for
regular expressions down to 0.60 for a language-model judgment). The **attack success rate (ASR)**
is the mean of `L` over a batch.

### 3. Four attacker profiles

| Profile | CVSS v3.1 | Authorized up to severity | Threat |
| --- | --- | --- | --- |
| P1 Internal employee | 6.5 | 2 | a curious insider asking plain questions |
| P2 External adversary | 8.2 | 0 | prompt injection, jailbreaks, obfuscation |
| P3 Privileged admin | 9.1 | 3 | poisons the corpus before any query is made |
| P4 Third-party provider | 7.7 | 3 | an API or vector-database provider bound only by contract |

The profiles map to the seven LINDDUN privacy-threat categories. P1–P3 were attacked live; P4
was evaluated offline from the campaign logs.

### 4. The attack campaign

| Family | Scenarios | Undefended ASR (engine / judge) |
| --- | --- | --- |
| F1 Direct PII extraction | 9 | 0.556 / 0.778 |
| F2 Cross-document linkability | 10 | 0.400 / 0.600 |
| F3 Direct prompt injection | 6 | 0.000 / 0.000 |
| F4 Obfuscated query | 5 | 0.000 / 0.000 |
| F5 Jailbreak / role-play | 5 | 0.200 / 0.200 |
| F6 System reconnaissance | 3 | 0.000 / 0.000 |
| F7 Social engineering | 7 | 0.000 / 0.000 |
| F8 Corpus poisoning | 7 | 0.000 / 0.143 |

By profile: 18 Internal, 27 External and 7 Admin scenarios. Each ran three times.

### 5. The system under test

Deliberately minimal: LangChain, ChromaDB, `all-MiniLM-L6-v2` embeddings (384 dimensions),
chunk size 512 with an overlap of 64, top-5 retrieval, and **Claude Sonnet 4.6** at temperature 0 with a
generic system prompt containing no privacy instruction. Any protection therefore comes from the
defense layers being measured, not from the prompt.

### 6. Five defense layers, tested by ablation

| Layer | What it does |
| --- | --- |
| L1 Input filter | blocks injection, jailbreak and encoding attempts before retrieval (regex + classifier) |
| L2 Retrieval redaction | removes personal data from retrieved chunks with Microsoft Presidio and custom recognizers |
| L3 Conversational refusal | refuses based on the conversation state, using the evaluation engine |
| L4 Output filter | Presidio redaction on the outgoing answer |
| L5 Provenance check | quarantines poisoned documents |

Configurations are written as bit codes over L1–L5: `C00000` is the undefended baseline,
`C01100` is L2 + L3, `C11111` is the full stack. Six configurations were measured. Two exploratory
probes target linkage outside the ablation: L6, a recall-closure probe on the linkage pathway,
and L7, a cross-turn *k*-anonymity gate, whose result was null.

| Configuration | Layers | Judged ASR (primary) | Engine ASR (lower bound) |
| --- | --- | --- | --- |
| C00000 | none | 0.288 | 0.192 |
| C10000 | L1 | 0.365 | 0.231 |
| C00100 | L3 | 0.346 | 0.192 |
| C01000 | L2 | 0.192 | 0.019 |
| C01100 | L2 + L3 (recommended) | 0.192 | 0.019 |
| C11111 | full stack | 0.173 | 0.000 |

The L1-only and L3-only increases are inside the judged noise floor (±0.08), not real increases.

### 7. Two instruments, both checked

- **The rule engine** scores `L` and `S` by matching each answer against the annotations of the
  retrieved documents. It is fast and deterministic, but its agreement with humans is low
  (κ = 0.164), and it cannot attribute a leak whose entities are annotated on a document that
  was not retrieved. Its numbers are lower bounds.
- **The language-model judge** (Claude Opus 4.7, versioned prompts in
  [`scenarios/judge_prompts/`](scenarios/judge_prompts/)) is the primary instrument. Against human
  labels it reaches κ = 0.827 on undefended answers, corroborated by an independent model family
  (κ = 0.843, agreement only, not validation), and κ = 0.306 on defended answers.

### 8. Security against utility

![Security against utility across the six configurations: the frontier runs from no defense
through the recommended pair (judged ASR 0.192) to the full stack (0.173).](results/phase3_4/report/thesis/fig_ch6_pareto.png)

The recommended pair captures the measured security benefit with two layers. The full stack's
further step is within noise and is justified only as defense in depth, at the cost of lower
context precision and about twice the latency.

---

## Limitations

- **The corpus is synthetic.** Faker samples each attribute independently, so the *relative*
  findings (which layer helps, which attacker is hardest, how the residual is made up) are what
  transfer to a real deployment; the absolute percentages are not predictions for any
  organization.
- **Three of four profiles were attacked live**, and **six of the 32 possible configurations**
  were measured.
- **The judge is less reliable on defended output** (κ = 0.306), and the defended distribution has
  a single human annotator.
- **Run-to-run variation is real.** The three baseline runs give judged ASR of 28.8 %, 30.8 % and
  26.9 %; the ±0.08 judged and ±0.04 engine noise floors are estimates.
- **Utility was measured at the two extremes** (no defense, full stack) on 30 structural
  questions, not per configuration.
- This is a measurement framework and its findings, **not a certified or secure product**.

---

## Repository layout

```
├── Master_Report.pdf  PFE_Report.pdf   the two defended reports
├── PROJECT.md                          motivation and design (written at the start; see the reports for final numbers)
├── CITATION.cff  .zenodo.json          citation and archive metadata
├── Makefile  requirements.txt
├── scripts/            corpus generation, annotation, evaluation engine, RAG system, judge, campaign runner
│   └── phase3/         defense layers (l1_…, l2_…), ablation, probes and their tests
├── scenarios/          attack scenario registry, judge prompts, poisoned documents
├── data/ground_truth/  the synthetic corpus and its 2,190 annotations
├── experiment_logs/    campaign summaries and cost ledger
├── results/            every measurement: baseline, judge calibration, phase 3 ablation, figures,
│   └── phase3_4/report/thesis/   LaTeX sources of the thesis
├── analysis/partA/     post-defense verification scripts and their outputs
├── app/                chatbot demo running the recommended configuration (live API calls)
├── dashboard/          read-only Streamlit dashboard over the committed results
├── webapp/             both of the above in one web application
├── paper/              manuscript sources (separate from the thesis)
└── docs/               design notes and the original phase plans
```

---

## Running it

**Environments.** The main scripts were run with Python 3.14. Microsoft Presidio and spaCy cannot
be imported there, so they live in a separate Python 3.11 environment, `.venv-presidio/`, reached
through a subprocess (`scripts/phase3/presidio_bridge.py`). Without that worker, the redaction
layers fail closed instead of passing personal data through. `requirements.txt` lists the
packages of both environments: `spacy` and `presidio-*` belong in `.venv-presidio/` only, and
installing them in the main environment breaks it. [`CLAUDE.md`](CLAUDE.md) §5 gives the exact
worker versions and how to recreate it.

```bash
make validate                       # ground-truth consistency check, no API calls
```

**Explore the results without spending anything.** The dashboard only reads committed result files:

```bash
pip install streamlit pandas
python3 dashboard/check.py          # every artifact loads
streamlit run dashboard/app.py      # http://localhost:8501
```

**Live demo and experiments cost money.** The chatbot (`app/`), the combined web app
(`webapp/`) and every `scripts/phase3/*_runner.py` call the Claude API and need
`ANTHROPIC_API_KEY` in a local `.env` file, which git ignores. Most runners accept `--dryrun`, and
`python3 app/preflight.py` checks the setup for free before any paid call. The vector index is not
committed; [`scripts/build_index.py`](scripts/build_index.py) builds it into
`data/rag_index/chromadb/`.

**Not in this repository:** the two full per-execution baseline logs
(`experiment_logs/B2_CLEAN_main-w3.jsonl` and `B2_POISONED_poisoned-w4.jsonl`) are kept outside
git; their summaries are committed.

---

## Where to read more

| For | Read |
| --- | --- |
| The experiments, results and discussion | [PFE_Report.pdf](PFE_Report.pdf) |
| The survey of 49 primary sources and the framework design | [Master_Report.pdf](Master_Report.pdf) |
| Cross-cutting findings, including why the engine is a lower bound | [results/phase3/FINDINGS.md](results/phase3/FINDINGS.md) |
| Final per-configuration, per-family and per-profile numbers | [results/phase3/ablation/metrics/RQ_answers.md](results/phase3/ablation/metrics/RQ_answers.md) |
| Security–utility readout | [results/phase3/tradeoff/READOUT.md](results/phase3/tradeoff/READOUT.md) |
| Codebase conventions, environments, free versus paid commands | [CLAUDE.md](CLAUDE.md) |
| A guided demonstration | [SUPERVISOR_DEMO.md](SUPERVISOR_DEMO.md) |

---

## Author and citation

Built by **Tadj Mohamed Walid** ([@TMW17](https://github.com/TMW17)), ESI Sidi Bel Abbès.
Supervised by Dr. Souleyman Chaib (ESI Sidi Bel Abbès) and co-supervised by Pr. Esma Aïmeur
(DIRO, Université de Montréal).

Citation metadata is in [CITATION.cff](CITATION.cff). A journal article based on this work is in
progress; the archived research artifact will be published alongside it, under CC BY 4.0 as
declared there. This repository does not yet include a license file.
