# Defense Day — Word-for-Word Script
### RAG Privacy Defense · 44 slides (36 main + 8 backup)
*Read these aloud. The same text is in each slide’s speaker-notes (presenter view).*

---

## 01 Title

Good morning, members of the jury. Thank you for being here. My name is Mohamed Walid Tadj, and this is my final-year State Engineering dissertation in Artificial Intelligence and Data Science, supervised by Professor Esma Aïmeur and Professor Souleyman Chaib. The title is 'Mapping and Reducing Data Leakage in Retrieval-Augmented Generation Systems.' In one sentence: this work asks not only whether we can defend the privacy of an enterprise AI system, but whether we can honestly measure that defense — and the second question turned out to be the harder one. Over the next thirty minutes I will take you through the problem, the framework I built, the results, and what they mean.

---

## 02 Agenda

Here is how I will structure the next half hour. I will start with the background and the core problem — what enterprise retrieval-augmented generation is, and why privacy leakage in it is a real and difficult problem. Then I will present my proposed solution and methodology: the measurement framework I designed, the system architecture, and the tools behind it. The largest part of the talk is the evaluation and results, organized around my five research questions. And I will finish with the conclusion, the limitations of the work, and concrete future directions, before opening the floor to your questions. One thread runs through all of it: the leak that is hardest to prevent is also the hardest to measure — and that is not a coincidence.

---

## 03 Context

Let me start with the domain. Organizations today hold years of sensitive internal data — HR files, medical reports, internal memos, system configurations. Retrieval-augmented generation, or RAG, lets employees simply ask questions of all that data in natural language. Instead of fine-tuning a model on the documents, the system keeps them in a searchable index, retrieves the few most relevant passages for each question, and pastes them into the model's context so the answer is grounded in real records. It is being adopted fastest in HR, healthcare, and finance — which are exactly the domains that hold the most sensitive personal data. The example on the screen is the whole problem in a single line: ask 'who in Finance is over 40?' and the system will faithfully retrieve the HR records and assemble a list of named individuals — no attack required, just a question it was never told to refuse. The convenience is the vulnerability.

---

## 04 Stakes

Why does this matter beyond the lab? Because the data at stake is legally protected. Under the GDPR, an unauthorized disclosure of personal data is a reportable breach, carrying notification duties and regulatory exposure. Medical and other special-category data fall under Article 9, the strictest protection of all — and my test corpus deliberately includes medical reports for exactly that reason. And there is a trust dimension that no regulation captures: a single visible leak can destroy confidence in an entire deployment, no matter how useful it is the rest of the time. So this is not a hypothetical risk. The moment an enterprise points a RAG system at its internal records, it has a compliance problem and a trust problem at the same time — which is what makes measuring and reducing that leakage worth a full thesis.

---

## 05 Gap

To position the work, I surveyed forty-nine primary sources from 2021 to 2026, and I want to be precise about what already exists and what does not. The field is genuinely strong: there are mature guardrail systems like NeMo Guardrails and Llama Guard, there are retrieval-time redaction techniques, there is excellent PII detection tooling such as Microsoft Presidio, and there is a growing literature on using a language model as a judge to evaluate other models. Each of those is either a defense or a detector. But here is the gap I found, and it is not the obvious one. The obvious claim would be 'we need more defenses' — that would be weak and incremental. The real, unaddressed gap is that the field reports how well defenses work without ever validating that the instrument measuring leakage is itself reliable on defended output — the shifted distribution, full of refusals and redactions, that a defense actually produces. Everyone measures the patient; nobody calibrates the thermometer on the sick. That gap is exactly what my third research question fills.

---

## 06 Problem

So here is the core problem, stated as concisely as I can. The intuitive assumption is that the hard part of this work is building the defenses. It is not. The hard part is measuring whether a defense actually worked — because the obvious measuring tool, a keyword or entity scanner, fails in two opposite directions at the same time. On the left: a paraphrased disclosure like 'the senior engineer in Building 4 who joined in 2019' contains no exact name, so a keyword scan sees nothing and misses a real leak — a false negative. On the right: the sentence 'I cannot share salary information' is a perfect refusal, yet it contains the word 'salary', so a naive scanner flags it as a leak that never happened — a false positive. These two errors do not cancel; they move in different directions depending on what the defense is doing. The consequence is severe: any published claim of 'we reduced leakage by X percent' is only as trustworthy as the instrument behind it. You cannot reduce what you cannot measure honestly.

---

## 07 Two leaks

Before the research questions, I need to give you the one distinction that the entire thesis rests on, because every result depends on it. There are two fundamentally different ways a RAG system exposes a person. The first is direct PII — the model states a protected fact outright: 'Employee John Smith earns ninety-five thousand.' There is a named secret, and in principle you can detect it by looking for that secret. The second is re-identification by linkage, and it is subtler and more dangerous. The model never states a labelled secret — it gives a handful of individually harmless attributes, '58-year-old female manager in the Algiers Finance office', that together match exactly one real person. No single attribute is sensitive; their combination is identifying. And here is why this matters for defense: you can redact a named secret, but you cannot redact a combination of harmless facts without destroying the very information that makes the system useful. Please hold onto this distinction, because one of these two leaks can be largely defended and the other cannot — and that asymmetry is the heart of my results.

---

## 08 Questions

That problem becomes five research questions, and I will answer each one by name later in the talk. The first: what leakage occurs in an undefended enterprise RAG baseline, and which attacks dominate? The second: how much do existing defenses reduce that leakage, measured under matched conditions? The third, and this is the one that underwrites all the others: can a language-model judge detect leakage reliably — even on defended output? The fourth: which attacker is the hardest to defend against? And the fifth: what residual risk remains after the best defense, and how does it trade off against the system's usefulness? My objective was not to invent a new attack or a new defense. It was to build one unified, reproducible framework that can measure all of this honestly — and to report the answers, including the uncomfortable ones, with their real uncertainty.

---

## 09 Architecture

This is the framework I built, and it is a real, working system — every number in this talk comes from this one pipeline. Let me walk it left to right. It begins with a synthetic corpus of 155 documents, generated deterministically. That corpus is attacked by a campaign of 52 scenarios, organized into 8 attack families, run against 4 attacker profiles. The attacks hit a defended RAG system whose 5 defense layers can each be switched on or off independently — that is what I mean by ablatable, and it is the design choice that lets me isolate what each layer contributes instead of crediting the whole stack at once. Every response is then scored by two instruments in parallel: a deterministic rule engine, and a language-model judge. From those scores come the two metrics that run through the whole talk: the attack-success rate, and severity. Two properties make this credible — it is ablatable, so every causal claim about a layer is isolated; and it is fully reproducible, with a fixed seed and temperature zero, so every figure I show regenerates byte-for-byte on any machine.

---

## 10 Formal model

A defense evaluation is only meaningful if 'did it leak?' is a repeatable decision rather than a matter of opinion, so I defined leakage formally — and I keep the mathematics light on the screen. The first definition, L, is the leakage function. It takes the query, the response, the corpus, and crucially the user, and it returns one or zero: a leak is an above-threshold disclosure of personal data to a user who is not authorized to receive it. The dependence on the user is the important part — the same sentence can be a leak to an outsider and a perfectly authorized answer to an HR manager, so leakage is judged against who is asking, by their authenticated role, never guessed from the text. The second definition, S, is severity, on a discrete scale aligned to the LINDDUN privacy taxonomy and calibrated against CVSS, the standard used to score security vulnerabilities — so a leaked medical condition outranks a leaked office floor. Put simply: L tells you if a leak happened; S tells you how bad it was.

---

## 11 Profiles

I fixed the threat model in advance — I did not choose attackers to flatter the results. There are four profiles, and each carries its own breach threshold, meaning how much disclosure counts as a violation for that adversary. The curious insider, P1, is an authenticated employee with legitimate but limited access; their threshold is two, because some disclosure is normal in their work and only above-baseline disclosure is a breach. The external adversary, P2, has no access at all, so their threshold is zero — any sensitive disclosure to them is a breach by definition; that is the sharpest case. The malicious administrator, P3, has elevated access and a threshold of three, and can poison the corpus itself. And the third-party provider, P4 — the model API host or the vector-database operator — is a genuine cross-tenant risk that I assessed qualitatively rather than attacking live, and I flag that openly. The key point is that the profile is set by authenticated role, never inferred from the wording of the query — that is what makes leakage well-defined. Together, these four span all seven LINDDUN privacy-threat categories.

---

## 12 Families

The adversarial campaign is organized into eight attack families — 52 scenarios in total. They range from the simplest case, just naming a record and asking for it, through forcing the system to correlate entities across documents, to the genuinely adversarial techniques: direct prompt injection, obfuscation to evade filters, jailbreak and role-play, reconnaissance that probes the corpus structure, social engineering with a fabricated emergency, and finally corpus poisoning, where malicious documents are planted in advance. The first seven families are available to the insider and the external attacker; corpus poisoning is an administrator capability, because it acts on the index before any query is made. Each scenario was run three times at temperature zero for reproducibility. I designed the taxonomy this way so that when the results come in, we can see not just how much leaks, but exactly which kind of attack is responsible.

---

## 13 Defense

My defense is not one monolithic filter — it is five distinct mechanisms, each of which I can switch on or off independently. The first layer is an input filter that screens the incoming query for injection and jailbreak patterns before anything is retrieved. The second, retrieval-time redaction, is the centerpiece — it strips high-severity entities out of the retrieved passages before the model ever sees them, on the simple principle that a model cannot disclose what was never placed in its context. The third, conversation-aware refusal, watches for sensitive facts accumulating across several turns and refuses when a dialogue is clearly assembling a profile. The fourth is an output filter, built on Presidio, that scrubs identifiers from the response as a last line. And the fifth, provenance and access control, quarantines untrusted or poisoned documents. Because each layer toggles independently, I can attribute the reduction to specific layers rather than crediting the whole bundle — and that is what lets me make the claim on the results slides credibly, rather than as a guess.

---

## 14 Stack

A word on the implementation, because reproducibility was a design goal, not an afterthought. The whole system is built in Python. The corpus is generated with the Faker library under a fixed seed. Retrieval uses the all-MiniLM embedding model, producing 384-dimensional vectors, stored in a ChromaDB vector database, with documents chunked at 512 tokens with 64 overlap and the top five chunks retrieved per query. Both the system under test and the judge are frontier language models run at temperature zero. And the conceptual frameworks anchor the metrics in established standards — LINDDUN for the privacy threat taxonomy and CVSS version 3.1 for the severity calibration. There is nothing exotic here, and that is deliberate: this is a faithful, ordinary enterprise stack, so the findings speak to systems organizations are actually deploying today.

---

## 15 Instruments

The heart of the methodology is that I measure every response with two instruments, not one, because each sees what the other is blind to. The rule engine is deterministic: it credits a leak only when an annotated ground-truth entity appears literally in the output. It is fast, exact, and perfectly reproducible — but it is blind to paraphrase and to cross-document correlation, and it cannot tell a refusal from a leak. Against human judgment its agreement is only kappa 0.164, barely better than chance. The language-model judge reads meaning: it catches the paraphrased disclosure and the re-identification the engine misses, and it distinguishes a refusal from a real leak. Against human annotation it reaches kappa 0.827, with 93.5 percent raw agreement — 43 of 46 cases. So the judge is my primary instrument, and the engine is a deliberately conservative lower bound. I will add one thing before anyone asks: the 0.827 figure is against a single annotator, myself, and a second annotator at kappa 0.875 and a cross-vendor judge at 0.843 came later and confirm the result is not an artifact of one labeller or one model.

---

## 16 Setup

Now the evaluation. First, the setup — how the system was tested. The ground truth is a synthetic corpus of 155 documents: 100 employee records, 30 medical reports, 20 internal memos, and 5 system configurations, generated deterministically under a fixed seed so that no real person is ever exposed and every run is identical. Within those documents, two human annotators independently tagged 2,190 personal-data entities across 31 of the 36 entity types in my taxonomy, and they agreed strongly — Cohen's kappa of 0.875. That annotated corpus is the gold standard against which every automated measurement is scored. On the experimental side, the 52 attack scenarios were each run three times, against six defense configurations — from the fully undefended baseline through to the full five-layer stack — and every response was scored by both instruments. So nothing in the results that follow is a one-off; it is an averaged, ablated, reproducible measurement.

---

## 17 RQ1 baseline

Let me answer research question one: what does an undefended baseline leak? Read through the judge, my primary instrument, 28.8 percent of attack attempts succeed — that is 45 of 156. Notice the gap to the engine, which sees only 19.2 percent: that ten-point difference is entirely paraphrased disclosures the engine is structurally blind to, and it is a preview of research question three. And these are not trivial leaks — the mean severity on a leaking turn is 7.96 out of 10. When this system leaks, it leaks things that matter: salaries, medical conditions, identities. So the baseline establishes two facts at once: leakage is frequent, nearly one attempt in three, and what leaks is serious. That combination is exactly what makes the reduction worth pursuing, and 28.8 percent is the number every later result is measured against.

---

## 18 RQ1 families

Breaking the baseline down by attack family tells the real story. Direct PII extraction, family one, succeeds 77.8 percent of the time. Cross-document linkability, family two, succeeds 60 percent. Everything else is far below: jailbreak and role-play at 0.20, corpus poisoning at 0.143 — and I will be honest that poisoning is a single scenario, so it is not robustness-comparable to the others. The four manipulation families — injection, obfuscation, reconnaissance, and social engineering — all sit at exactly zero, because the underlying model simply refuses them. And here is the number that matters: families one and two together account for 91.1 percent of all the leaks. So the leakage is not coming from clever adversarial tricks — the exotic attacks fail. It is coming from the two families that ask the system to do ordinary retrieval work. That is reassuring in one sense and sobering in another, because the two attacks that succeed are exactly the two you cannot simply refuse without breaking the product.

---

## 19 RQ1 shape

I want to dwell on the shape of that result, because it changes how we should think about the whole problem. Look at what succeeds versus what fails. What succeeds is the system doing exactly what it was designed to do: retrieving a record and relaying it, and retrieving several records and correlating them. What fails — at exactly zero — is every adversarial trick: jailbreaks, injection, obfuscation, social engineering. The model refuses all of them. So the threat is the feature, not the attacker's cleverness. You cannot fix this by hardening the model against jailbreaks, because jailbreaks were never the source of the leakage — the leak rides in on legitimate retrieval. This reframes enterprise RAG privacy from a guardrail problem, where you bolt on a better refusal classifier, into an architecture problem: the leak is a property of letting a helpful model retrieve freely over a sensitive corpus. That reframing is what drives the entire second half of my results, and it is why my conclusion lands on governance rather than on yet another filter.

---

## 20 RQ1 floor

One more thing about the baseline, and it protects the honesty of every number after it. 28.8 percent is a conservative floor, not an alarmist ceiling. Both instruments can only credit leakage that actually appears in a response they read; anything assembled from records the retriever never fetched, or built up gradually across conversational turns, goes uncounted. Two pieces of evidence. First, retrieval precision on the exact target document is only 8.3 percent — the system usually returns neighboring records rather than the one asked about, and a disclosure rebuilt from those neighbors is invisible to the engine. Second, a manual hand audit found 10 confirmed leaks that the automated pipeline never credited, including some of the most severe in the entire study. Put together: the true undefended rate is at least 28.8 percent. The measurement understates the risk by construction — so if my number is biased, it is biased toward under-reporting, not exaggeration. If you ask why retrieval precision is so low, the short answer is that RAG retrieves by semantic similarity, not exact lookup, and I have a backup slide on exactly that.

---

## 21 RQ2 headline

Research question two: how much do the defenses reduce that leakage? The full five-layer stack takes judged leakage from 28.8 percent down to 17.3 percent — a relative reduction of roughly forty percent. That is a genuine, useful, hard-won result against a problem the field finds slippery to even measure. But I want to say one word clearly, and stand by it: this is a reduction, not an elimination. More than half of the original leakage still persists. I say this deliberately, because a forty-percent reduction is real and valuable, and claiming the system is 'secured' or 'safe' would be false — and any one of you would catch it. By naming the limit before you do, I am showing you exactly where the boundary of the evidence lies. And that surviving half is not noise to be apologized for — it is the most interesting part of the thesis, because understanding why it survives is what the rest of the talk is about.

---

## 22 RQ2 knee

The reduction is not shared evenly across the five layers — and that has a direct, practical implication. The ablation shows that retrieval-time redaction, layer two, is the only layer whose individual contribution clears the noise floor; the other four each move the needle by amounts indistinguishable from noise. From that comes what I call the deployment knee — the point of best protection for least cost — which is just two layers: redaction plus conversational refusal. That two-layer configuration reaches 0.192 leakage, while the full five-layer stack reaches 0.173 — a difference of less than two points, sitting inside the noise band. In other words, you capture essentially all of the achievable security with two layers instead of five, at a fraction of the latency and engineering cost. I will be honest that the refusal layer adds no measurable reduction on its own here, but I keep it in the knee as cheap insurance against the multi-turn accumulation attacks that a single-turn campaign under-samples. So the recommendation is lean and evidence-based: deploy the knee, not the kitchen sink.

---

## 23 RQ3 collapse

Now research question three — and this is, I believe, the most important result in the thesis. Can the instruments be trusted on defended output? On undefended output the judge is excellent — kappa 0.827 against humans. But the moment the defenses are switched on, the output distribution shifts: it fills with refusals, partial redactions, and hedged phrasings the judge was never calibrated on, and its agreement with humans collapses to kappa 0.306 — from near-expert agreement down to barely acceptable. The rule engine fares even worse: on linkage specifically, its agreement with humans is minus 0.10 — literally worse than a coin flip, because it is structurally blind to re-identification and wrong in a consistent direction. Raw agreement tells the same story, falling from 93 percent to 70. The deep point, and the contribution, is this: the very tools we rely on to certify a defense become unreliable exactly when the defense is switched on — which is the one moment we most need them to be right. That is not a quirk of my particular judge; it is a general hazard the field has been overlooking.

---

## 24 RQ3 finding

I do not hide this disagreement — I present it as the discovery, because it is my most original contribution. Here is the defended confusion matrix over 46 cases: 7 true positives, 11 false positives, 3 false negatives, 25 true negatives. From that, a false-positive rate of 31 percent and a false-omission rate of about one in ten. The crucial structural fact is that the error is bidirectional — 11 over-flags, where the judge called a refusal a leak, against 3 under-detections, where it missed a real leak. Those do not cancel; they tell you the instrument is biased in a way that depends on what it is looking at. And here is the detail that matters most: all 3 of the missed leaks were linkage cases that the human annotator caught. That has two consequences. First, the residual leakage is corroborated by human judgment — it is not something the judge invented. Second, because the misses are real leaks the judge could not see, my 17.3 percent is a lower bound on what is actually leaking, not an over-estimate. The general lesson for the field is simple: any language-model judge must be re-calibrated on the defended distribution it will actually score — validating it once on easy text is not enough.

---

## 25 RQ3 range

This slide is about doing the honest thing when the textbook breaks. The standard tool for correcting a known error rate is the Rogan–Gladen estimator, and when I applied it here it returned minus 34 percent — an impossible, negative leakage rate. The reason is that my calibration sample was deliberately enriched: I took every case the judge flagged as positive, rather than a random draw, so the prevalence term the formula needs is undefined. And I enriched on purpose, because a random sample of 46 cases would have contained only about eight real leaks — far too few to estimate the judge's error rates at all. So enrichment was the correct design, and the honest price is that the closed-form correction simply does not apply. Rather than force a wrong number, I report an interval — from 5.3 to 25.8 percent — that contains my point estimate of 17.3, and I explicitly refuse to claim the true rate is lower, because the over-flagging I can see cannot be projected into a correction without introducing selection bias. Honest uncertainty beats a confident wrong number.

---

## 26 RQ4

Research question four: which attacker is the hardest to defend against? The table answers it directly. The privileged administrator, whose method is corpus poisoning, is brought all the way to zero by the defense — that is a clean win. The external attacker is roughly halved, from 0.296 down to 0.148, because their method is extraction, which redaction stops well. But look at the insider: from 0.333 down to 0.278, and then it does not move at all between the knee and the full stack. The insider is the hardest adversary — and the reason is precisely the conceptual spine from earlier: the insider already has legitimate access, so they do not need to extract anything. They attack by re-identification, by linkage, and that is the one thing the defense cannot touch. If you wonder why the insider's 0.333 does not match the linkage family's 0.60 from earlier, it is simply different denominators — 0.333 is the insider across all their attacks, most of which fail, while 0.60 is the linkage family in isolation. I have a backup slide on that.

---

## 27 RQ5

Research question five: what remains after the best defense, and how does it trade against utility? I will answer in both registers of my formal framework. In leakage: 17.3 percent survives, and family two, linkability, is the dominant unreduced component — it stays flat at around 0.60 to 0.70 across every configuration, while direct PII collapses from 0.778 down to 0.222. Of the cases that survive, roughly two-thirds are the detector's recall gap — a salary written out in prose, a condition phrased in open language — and one-third is genuine, irreducible linkage. In severity: the full stack cuts mean severity by 0.494, leaving a residual of 0.371 — so the defense reduces not just how often leaks happen but how serious they are. The single sentence to take from this slide: what remains is not something you can fix by tuning a threshold, because it is not an extraction the filter missed — it is a person reassembled from facts that are each, individually, harmless.

---

## 28 Linkage math

Let me show you why linkage is intractable, because this is the mathematical heart of the discussion. Re-identification is a property of the information itself, not a flaw in any particular defense — this is Latanya Sweeney's classic result, and it holds here. On my corpus, 84 of 100 employees are uniquely identified by just four ordinary, individually-harmless attributes: department, medical condition, age range, and office location. No single one is sensitive; the combination singles out a specific person. And that creates a fundamental tension: any transformation strong enough to break that uniqueness — generalizing the attributes, suppressing them — also destroys the very information that makes the data useful to answer legitimate questions. You cannot remove the clues without removing the usefulness. I will be honest about one thing: 84 out of 100 is an upper bound on intrinsic uniqueness, because my synthetic data has independent attributes; real data with correlated attributes might be lower. But the direction of the result is robust, and it is the reason the next slide shows three separate defenses all failing.

---

## 29 Three negatives

This is the strongest structural result in the thesis, and I prove it three independent ways. First, retrieval-time redaction leaves the linkage rate completely unmoved — from 0.60 to 0.60 — because there is no single named entity to remove. Second, query-time k-anonymity has no measured effect, because the identifying combination already sits inside a single retrieved chunk, so anonymizing across chunks does nothing — and I tested that directly, it is a genuine null result, not an untried idea. Third, ingestion-time k-anonymity is foreclosed at construction: reaching even k equals two costs 0.52 in information loss and drops nine percent of the records outright, gutting the corpus before any attack is even run. Three different mechanisms, three independent failures, all triangulating the same wall. And I want to state this plainly, the way my thesis does: these negative results are the contribution, not a shortfall. Showing rigorously that a whole class of model-layer defenses cannot solve linkage is exactly what tells us the solution must live somewhere else — which is where I go next.

---

## 30 Reframe

Let me interpret what all of this means. First, severity reshuffles the priorities. Weighted by harm, linkability is the dominant residual risk at 2.80 — higher than direct PII at 1.11, even though direct PII is individually more severe, because redaction crushed its frequency. Both ways of reading the data — by family and by entity type — agree that the residual is linkage. And that leads to the central reframe of the thesis. If linkage cannot be removed at the model layer without destroying utility, then it is not a model-layer problem at all — it is a data-governance problem. The resolution is not a smarter filter; it is to minimize what enters the corpus in the first place, to gate retrieval by authorization, and to audit the residual that remains. This is not my preference — it is the conclusion the three failed defenses force. One precise point: authorization-gated retrieval cleanly solves the external attacker, who should never reach the data, but for the authorized insider it only bounds the residual; it cannot eliminate it, because the insider is allowed to see the very attributes that enable re-identification. We did not just measure the leak — we located it, and showed which layer of the stack can actually own it.

---

## 31 Practice

Before I summarize, I want to translate the findings into practice, because a measurement is only useful if it tells a practitioner what to do. Every recommendation on this slide is anchored to a specific number from my study — nothing is asserted beyond the evidence. Redaction is necessary but not sufficient: I say that because linkability stayed flat at 0.60 even with redaction on, and that maps to the data-minimization duty of GDPR Article 5(1)(c). Entity detection cannot certify the absence of linkage: I say that because the engine scored minus 0.10 on linkage, worse than chance, which bears on the accountability principle of Article 5(2). Any language-model judge must be re-calibrated on defended output: that follows directly from the judge's collapse from 0.827 to 0.306, and again touches Article 5(2). Linkage should be treated as a data-governance obligation, grounded in the three mechanisms that failed, which maps onto frameworks like NIS2 and ISO 27001. Deploy at the knee and report the trade-off honestly — that is the security-by-design principle of Article 25. And finally, always say 'reduces,' not 'eliminates,' grounded in the move from 28.8 to 17.3 percent, which speaks to the security-of-processing duty of Article 32. I want to be precise about the regulatory column: this is a mapping to obligations to show real-world bearing — it is not a legal compliance certification, and I do not claim it as one.

---

## 32 Contributions

Let me summarize what this work contributes. Four things. First, an integrated, reproducible framework for measuring privacy leakage in RAG — corpus, threat model, defenses, and dual-instrument scoring in one pipeline. Second, and this is the one I would highlight, the two-instrument finding: that measurement of a defended system is instrument-dependent, and a single deterministic instrument records its own blindness as protection — it reads safe precisely because it cannot see what survives. Third, the triangulated result that linkage is intractable at the model layer, proven by three independent failed defenses. And fourth, a set of governance controls calibrated to exactly what each can do, mapped to specific GDPR obligations. The headline I want you to leave with is not a single percentage — it is the method. The durable contribution is that a defended retrieval system must be measured by an instrument that is itself validated on the output the defense actually produces. The negatives and the measurement discipline are the contribution.

---

## 33 Limitations

I want to name the limitations of this work plainly, because doing so is part of the methodology, not an apology. There are three clusters. On the instrument: my primary judge is from a single vendor, my redactor shares that vendor so they may share a blind spot, and the defended-side validation was done by one annotator. On the corpus: it is synthetic with independent attributes, so the absolute numbers are demonstrations rather than predictions — only the relative findings transfer — and my 84-out-of-100 uniqueness figure is an upper bound, and corpus poisoning was only a single scenario. On utility: I measured three quality dimensions, and I measured cost at the extremes rather than isolating it at the knee. These limitations compound, because each is a single-vendor or single-annotator exposure on the same apparatus, and I say so. The honest scope of the whole thesis is this: it is a measurement methodology demonstrated on a controlled corpus — the direction of the findings generalizes, but the precise magnitudes do not, and I would not claim otherwise.

---

## 34 Future work

Each future direction answers a limitation I just named — that is deliberate. First, to close the instrument exposure: a second annotator and a multi-vendor judge panel, with the goal of lifting that collapsed defended-distribution agreement back above 0.306. Second, validation on real corpora beyond my single Enron probe, since the open question there is whether the judge over-flags on real-world prose. Third, and most promising, linkage-specific defenses: entity resolution for the genuine one-third, per-attribute recognizers for the recall-gap two-thirds, and — this is the one my evidence actually points to — an ingestion-time intervention that splits records so that no single retrievable chunk ever carries the full identifying combination. That is structurally different from the query-time gate that failed, which is exactly why it is worth trying. And fourth, per-configuration utility measurement and compositional, multi-actor threats — for instance a supply-chain compromise that hands an external attacker insider access, which is the setting where the linkage residual would matter most.

---

## 35 Conclusion

Let me close with the whole thesis in one breath, and I will say it slowly. A layered defense reduces enterprise RAG leakage by roughly forty percent — from 28.8 to 17.3 percent — but it cannot eliminate re-identification by linkage, which is a data-governance problem rather than a model-layer one; and measuring any of this honestly requires more than one instrument, because the tools we use to detect leakage become unreliable exactly when a defense is active. Three things to remember: reduce is not eliminate; linkage is governance; and measurement is instrument-dependent. Thank you.

---

## 36 Q&A

That concludes my presentation. To restate the contribution in one line before your questions: we measured the leak, cut it by roughly forty percent, learned how to trust that measurement, and found that what remains is a governance problem we now know how to manage. I have prepared backup material on several points you may wish to probe — the annotator and cross-vendor validation, why the Rogan–Gladen correction breaks, the full k-anonymity sweep, why retrieval precision is so low, the Enron real-data probe, and the complete ablation table. I would be very glad to take your questions. Thank you.

---

## B1 Validation

If you press me on whether the judge's validation rests on my own labelling alone — it does not. A second, independent annotator agreed at kappa 0.875. A judge from a different vendor agreed at kappa 0.843. And the original judge-versus-human agreement on undefended output was 0.827. Three independent points of corroboration, across two annotators and two vendors. So the validation does not rest on a single labeller or a single model family.

---

## B2 Rogan-Gladen

If you ask why I report a range rather than a single corrected number: the standard Rogan–Gladen correction, applied here, returns minus 34 percent — an impossible negative rate. It breaks because my calibration sample was enriched: I took every case the judge flagged positive, rather than a random draw, so the prevalence term the formula needs is undefined. And I enriched deliberately, because a random sample of 46 cases would have contained only about eight real leaks — far too few to validate the judge at all. So I report an honest interval instead, from 5.3 to 25.8 percent, which contains my point estimate of 17.3. The enriched sample was the right methodological call; breaking Rogan–Gladen is the honest price I pay for it.

---

## B3 k-sweep

If you want the full k-anonymity result, here it is. Read the honest cell, k equals two: the gate, the random same-rate control, and doing nothing all leak at 0.7 — no separation whatsoever. The apparent dip at k equals five, where the gate drops to 0.4, is within the plus-or-minus 0.30 noise band, and it reverses at k equals ten, where the gate climbs back to 0.6 while leakage stays at 0.7. Meanwhile the generalization rate — the utility cost — climbs from 0.34 to 0.73 to 0.77. So combinatorial k-anonymity returns a null: it does not reduce linkage, and what little movement appears is noise that reverses.

---

## B4 Precision

If you wonder why retrieval precision is only 8.3 percent, the answer is that this is how RAG works, not a defect. RAG retrieves by semantic similarity, not by exact identifier lookup. In a corpus of around a hundred very similar HR records, the exact target record is rarely the single top hit — the retriever returns a cluster of near-neighbors. And that is precisely why direct PII extraction still reaches 77.8 percent success despite zero percent precision on the exact target document: the model simply leaks from a neighboring record instead. The attacker does not need the right document — only a nearby one.

---

## B5 Enron

If you ask whether any of this holds outside my synthetic corpus, I ran a probe on a real Enron mailbox. Two things happened, and naming which is the point. Redaction transferred: on real data it reduced direct disclosure in the same direction as on synthetic, from four out of four down to two out of four. But the judge, which was validated on synthetic text, over-flagged on real prose — its calibration did not transfer. That cross-corpus transfer limitation is itself a finding: one tool generalized, the other did not, and being able to say precisely which is exactly the kind of honesty this thesis is about.

---

## B6 Ablation

If you want any specific configuration, here is the full ladder. The undefended baseline, C-zero, is 28.8 percent judged leakage. The full five-layer stack, C-one-one-one-one-one, is 17.3 percent. And the knee, C01100 — redaction plus refusal — is 0.192, which is essentially the full-stack result once you account for the 0.08 noise floor. The point this table makes is that the reduction is concentrated almost entirely in redaction; the knee captures it with just two layers, and the remaining three layers add defense-in-depth without a measurable further drop.

---

## B7 Validity

If you challenge me on whether this would hold on real, correlated data rather than my synthetic corpus — this is the most important rebuttal, so let me be precise. My exact numbers are corpus-specific; only the direction transfers, and I have always said so. But here is the key argument: real-world correlated attributes — title with salary, department with location — create MORE re-identification paths, not fewer. My corpus has independent attributes, which means it is actually the hardest case for an attacker, the case with the fewest linkages. So if linkage defeats every model-layer defense even here, it defeats them more easily on real, correlated data. The finding gets stronger, not weaker. Correlation makes linkage worse, so the conclusion survives.

---

## B8 Panel

If you ask why I used a single validated judge rather than an arbitration panel of several models — this was a deliberate design decision, not a shortcut. A panel whose members all share a model family produces the appearance of independence without the substance: a same-family arbitrator cannot, even in principle, correct the judge it is arbitrating, because they share the same blind spots — exactly the echo-chamber effect the literature predicted. The honest resolution is one validated judge, corroborated across a genuinely different vendor at kappa 0.843. So this is a finding about how to design LLM-as-judge evaluation, not a retreat from rigor.

---

