# Task 3.7 — Regulatory alignment & DPIA (research prototype)

> **Honest scope.** This maps the prototype's **built artifacts** to **GDPR**, **NIS2**, and **ISO/IEC 27001
> (Annex A, 2013 numbering)** controls. It claims the system is **ALIGNED WITH / SUPPORTS** these controls —
> **not** "compliant," "certified," or "meeting obligations." A research prototype on a *synthetic* corpus
> cannot be compliant: that requires an accountable legal entity, a full processing inventory, organisational
> measures, and external audit, none of which are in scope. Every control row names the **specific aspect
> supported AND the gap**. Residual risks are stated, not omitted (see the DPIA below).

## 1. Control → artifact map

Each artifact is real and in-repo (path given). "Supports" = provides technical evidence toward the control;
"Gap" = what a compliant system would additionally need.

| Framework / control | Supported by (artifact + path) | Aspect supported | Gap / NOT covered |
|---|---|---|---|
| **GDPR Art. 5(1)(c) — Data minimisation** | **L2 retrieval redaction** + **sanitized index** (`scripts/phase3/defense_pipeline.py`, `scripts/phase3/build_sanitized_index.py`, `data/rag_index/sanitized_chromadb/`) | sev≥3 PII removed from retrieved context (query-time) and from the store (index-time) before it reaches the LLM | sev2 quasi-identifiers retained **by design**; MEDICAL/SURNAME/IMMIGRATION **detector gaps** (Task 0.1) → minimisation is partial, not complete |
| **GDPR Art. 25 — Data protection by design & by default** | **Layered defence L1–L5** + preventive sanitized index (`defense_pipeline.py`, `config_set6.json`) | privacy controls engineered into the pipeline; secure default = the C01100 knee (Task 3.2) | prototype depth only; 26/32 layer combinations are future work; "by default" not enforced at deploy time |
| **GDPR Art. 30 — Records of processing** | **audit_log** (`defense_pipeline.py` → `results/phase3/audit/*.jsonl`) | per-turn traceability: timestamp, profile, family, config, layers fired, retrieved_doc_ids, verdict, severity, source | a prototype event log, not an Art. 30 register (no controller/processor, purposes, retention, recipients) |
| **GDPR Art. 32 — Security of processing** | L1 input filter, L3 refusal, L4 output filter, L5 provenance/ACL, audit_log, **and the L/S evaluation + ablation framework** (`evaluation_engine.py`, `results/phase3/ablation/`) | technical measures for confidentiality + **Art. 32(1)(d) regular testing/evaluation of effectiveness** (the whole measured ablation) | **NO encryption at rest/in transit, no authentication/session security** — Art. 32 is broader than the implemented artifacts |
| **GDPR Art. 35 — DPIA** | **Risk matrix (Task 3.4)** + the DPIA in §2 (`results/phase3/risk_matrix/`, this file) | systematic, measured risk assessment of high-risk processing (PII + LLM) with residual-risk analysis | not a full DPIA (no stakeholder/DPO consultation, no real-data processing inventory, no sign-off) |
| **NIS2 Art. 21 — Risk-management *principles*** | risk matrix + ablation + L/S metrics | risk-based, *tested* security measures; effectiveness quantified | NIS2 binds **essential/important entities**, not prototypes — alignment is with the *principles*, not the legal obligations (no governance, no incident reporting) |
| **NIS2 — incident detection / logging** | audit_log + L3 refusal + **confidence (severity-S) circuit-breaker** (`defense_pipeline.py`) | detection + structured logging of anomalous/high-severity access; per-turn suppression | no SOC, alerting, retention, or 24/72h reporting workflow |
| **ISO 27001 A.8 — Asset management / classification** | **36-type severity taxonomy (31 instantiated in the corpus = the Task 3.4 entity-matrix rows) + ground-truth annotations** (`data/ground_truth/ground_truth_annotations.json`) | information classified by severity (2–5) and LINDDUN category | classification of the *synthetic* corpus only (31 of the 36 taxonomy types appear); no real asset inventory or ownership |
| **ISO 27001 A.9 — Access control** | **L5 provenance/ACL + 4 attacker-profile authorization model** (`config.py` AUTHORIZATION_LEVELS, `l5_tests/`) | logical access control *designed* per profile (auth thresholds); poisoned-collection isolation (provenance) was measured | **L5 ran provenance-only (`l5_acl=False`) in the ablation** — the corpus is uniformly sev≥3, so per-profile ACL had nothing to bite on; **per-profile enforcement is designed but unmeasured**. No real identity/authn; profile is a simulated parameter, not enforced IAM |
| **ISO 27001 A.10 — Cryptography** | **— NOT IMPLEMENTED —** | (none) | **Honest "no": no encryption at rest/in transit, no key management.** Out of scope for the prototype; required for any production deployment |
| **ISO 27001 A.12 — Operations security (A.12.4 logging)** | **audit_log** (`results/phase3/audit/`) | event logging of processing/access | no log integrity protection, retention policy, or monitoring infrastructure |

## 2. DPIA (GDPR Art. 35 structure)

**(a) Description of processing.** An enterprise Retrieval-Augmented Generation assistant answers natural-language
queries by embedding them, retrieving the top-k chunks from a vector store built over a 155-document corpus of
employee/medical/system records (2,190 annotated PII entities, severity 2–5), and generating an answer with an LLM.
The privacy risk is **leakage of personal data to an unauthorised requester**, evaluated against four attacker
profiles (Internal/External/Admin/ThirdParty) and eight attack families (F1–F8).

**(b) Necessity & proportionality.** Retrieval over the corpus is necessary for the assistant's function; the
exposure is minimised proportionately by **L2/sanitized-index redaction** (sev≥3 PII), gated by **L5/profile access
control**, and bounded by **L1/L3/L4** rails. The recommended operating point is the **C01100 (L2+L3) knee**
(Task 3.2): it captures essentially all the measured security benefit at the lowest layer count and **zero measured
over-refusal** on benign queries (Task 3.1: 0/30).

**(c) Risks to data subjects** *(quantified — cited from the Task 3.4 risk matrix; JUDGED metric, primary)*:
- **Re-identification via LINKABILITY (F2) — the dominant residual.** Judged ASR is **unreduced** by the stack
  (~0.60→0.70→0.60 across C00000/C01100/C11111). Combining retained quasi-identifiers re-identifies individuals
  even when direct identifiers are redacted.
- **Sensitive-attribute DISCLOSURE via detector gaps.** Presidio **misses** MEDICAL (recall_any **0.0**, open
  vocabulary), IMMIGRATION (**0.0**), and half of SURNAME_TITLE (**0.51**) — Task 0.1 — so these sev≥3 attributes
  survive L2 redaction. AGE_GENDER (sev3, recall 0.0, LINDDUN=Linkability) is the bridge feeding F2.
- **By-design retention of sev2 quasi-identifiers** (department, job title, office, schedule, project, training,
  performance): L2 redacts sev≥3 only, so these remain in context and form the linkability substrate.
- **Prose-form salary** survives even though structured salary is redacted (recall 1.0) — a format-drift gap.

**(d) Measures to reduce risk** (the built artifacts): the L1–L5 stack + sanitized index reduce the overall
**judged** attack-success rate from **0.289 (C00000) → 0.192 (C01100)** (~33%), with Direct-PII (F1) cut
**0.78 → 0.22** and injection/jailbreak/poisoning (F3/F5/F8) driven to judged 0.0; per-turn **audit_log** for
traceability and a severity-S **circuit-breaker** for high-risk suppression. **This ~33% is not uniform
protection:** it is carried almost entirely by F1, while **F2 linkability rises (0.60→0.70) and is not reduced**
— the aggregate must always be read with the per-family residual of point (c).

**(e) Residual risks & known limitations** *(explicitly retained, not omitted)*:
1. **Linkability is not mitigated** — F2 survives every configuration (Task 2.3 headline; `linkability_diagnosis`).
   Closing it needs entity resolution + generalizable attribute recall (future work), not threshold tuning.
2. **Detector recall gaps** — MEDICAL/IMMIGRATION (0.0) and SURNAME (0.51): a learned medical NER + prose-money
   detector are required; a corpus gazetteer does not generalize.
3. **The judged residual is a LOWER BOUND** (finding F1): the LLM judge, like the rule engine, cannot see all
   cross-document re-identification, so **true risk ≥ the reported figures**.
4. **No cryptography** (ISO A.10 / GDPR Art. 32): no encryption or key management.
5. **Utility cost**: the redaction stack costs ~0.10 context-precision and ~1.9× latency (Task 3.1) and can return
   faithful-but-empty answers — relevant to data-*availability*/accuracy obligations.
6. **Prototype on synthetic data**: not certified; no organisational/legal measures; results are a defensible
   *evidence base*, not a conformity statement.

**(f) Conclusion.** The system **supports and is aligned with** the data-minimisation, privacy-by-design,
access-control, traceability, and risk-assessment *intent* of GDPR/NIS2/ISO 27001, with measured evidence for each.
It is **not compliant or certified.** The **residual cross-document linkability risk** is the principal barrier to
a production privacy posture and is scoped as future work.
