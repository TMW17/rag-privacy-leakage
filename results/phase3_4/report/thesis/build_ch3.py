# -*- coding: utf-8 -*-
# Build ch3_threat_formal.tex by LIFTING rich blocks from Threat_Model.tex and
# Formal_Leakage_Definitions_and_Ground_Truth.tex (preserving the author's prose
# and LaTeX escaping), and AUTHORING the reconciliation-sensitive sections from
# the committed (canonical) chapter. Heading levels are demoted; labels/refs are
# namespaced to ch3:*; cross-ref / taxonomy-count landmines are patched.
import re, os

ROOT = "/Users/user/Desktop/Final_Year_Project/Code"
TM = open(os.path.join(ROOT, "Threat_Model.tex"), encoding="utf-8").read()
F  = open(os.path.join(ROOT, "Formal_Leakage_Definitions_and_Ground_Truth.tex"), encoding="utf-8").read()
OUT_THREAT = os.path.join(ROOT, "results/phase3_4/report/thesis/ch3_threat_formal.tex")
OUT_FORMAL = os.path.join(ROOT, "results/phase3_4/report/thesis/ch3b_formal_groundtruth.tex")

def between(text, start, end):
    i = text.index(start)
    j = text.index(end, i + len(start))
    return text[i:j]

def between_next_section(text, start):
    i = text.index(start)
    m = re.search(r"\n\\section\{", text[i + len(start):])
    j = i + len(start) + m.start()
    return text[i:j]

def demote(s):
    s = s.replace(r"\subsubsection{", r"\paragraph{")
    s = s.replace(r"\subsection{", r"\subsubsection{")
    s = s.replace(r"\section{", r"\subsection{")
    return s

def prefix_labels(s):
    s = re.sub(r"\\label\{", r"\\label{ch3:", s)
    s = re.sub(r"\\(ref|cref|Cref|autoref|nameref)\{", lambda m: "\\" + m.group(1) + "{ch3:", s)
    return s

def drop_first_heading(s):
    # remove the block's leading demoted \subsection{...} line (redundant with the
    # authored \section heading); keep any following \label line.
    return re.sub(r"\\subsection\{[^}]*\}\s*\n", "", s, count=1)

def fixes(s):
    s = s.replace("L{", "W{")                                  # parametrized column -> W
    s = s.replace(r"_{\text{full-stack}}", r"_{\text{residual}}")  # normalize residual notation
    # taxonomy table (no "Table 6.1" exists in the thesis):
    s = s.replace("Table~6.1", r"Table~\ref{tab:ch3-taxonomy}")
    s = s.replace("Table 6.1", r"Table~\ref{tab:ch3-taxonomy}")
    # canonical taxonomy counts (sources are internally inconsistent: 35/36/37):
    s = s.replace("31 / 35", "31 / 36")
    s = s.replace("instantiates 33 of the 37 entity types", "instantiates 31 of the 36 entity types")
    s = s.replace("37 entity types total", "36 entity types total")
    # hard-coded chapter / section number references -> thesis \refs:
    s = s.replace("Chapter~1", r"Section~\ref{sec:ch3-linddun}")
    s = s.replace("Chapter~2", r"Section~\ref{sec:ch3-profiles}")
    s = s.replace("Chapter~4", r"Section~\ref{sec:ch3-arch}")
    s = s.replace("Chapter~6", r"Section~\ref{sec:ch3-formal}")
    s = s.replace("Section~2.2", r"Section~\ref{ch3:sec:cvss-framework}")
    s = s.replace("Section~3.3", r"Section~\ref{sec:ch3-limits}")
    s = s.replace(r"(Phase~2 Report,~\S4.5)", r"(offline; Section~\ref{sec:ch3-limits})")
    s = s.replace(r"Phase~2 Report,~\S4.5", r"offline assessment (Section~\ref{sec:ch3-limits})")
    s = s.replace(r"(Phase~2 Report~\S4.5)", r"(offline; Section~\ref{sec:ch3-limits})")
    # dangling refs to non-lifted (authored) sections, after ch3:-prefixing:
    s = s.replace("ch3:sec:reidentification", "sec:ch3-reid")
    s = s.replace("ch3:subsec:ldiv-explained", "sec:ch3-reid")
    s = s.replace("ch3:sec:engine", "sec:ch3-engine")
    s = s.replace("ch3:subsec:llm-judge-limit", "sec:ch3-engine")
    s = s.replace("ch3:sec:kappa", "sec:ch3-annotation")
    s = s.replace("ch3:subsec:kappa-representativeness", "sec:ch3-annotation")
    s = s.replace("ch3:sec:validation", "sec:ch3-annotation")
    s = s.replace("ch3:tab:deliverables", "sec:ch3-corpus")
    return s

def lift(block, drop_first=False):
    if drop_first:
        block = demote(block)
        block = drop_first_heading(block)
    else:
        block = demote(block)
    block = prefix_labels(block)
    block = fixes(block)
    return block.rstrip() + "\n"

# ----- extract source blocks -----
LINDDUN  = between(TM, r"\section{Rationale for the Choice of Framework}", r"\chapter{Formal Attacker Profiles}")
PROFILES = between(TM, r"\section{Specification Methodology}", r"\section{Consolidated Capability Matrix}")
CAPAB    = between(TM, r"\section{Consolidated Capability Matrix}", r"\chapter{Cross-Profile Analysis, Coverage, and Limitations}")
COVERAGE = between(TM, r"\section{Threat Surface Coverage}", r"\section{Limitations of the Threat Model}")
LIMITS   = between(TM, r"\section{Limitations of the Threat Model}", r"\chapter{System Architecture Diagrams}")
FDEF     = between(F,  r"\section{Formal Leakage Definitions}", r"\section{Ground Truth Corpus}")
FCORP    = between(F,  r"\section{Ground Truth Corpus}", r"\section{Entity-Level Annotation Protocol}")
FANNOT   = between_next_section(F, r"\section{Entity-Level Annotation Protocol}")

# ===================== AUTHORED preamble + connective tissue =====================
PRE = r"""% ============================================================================
%  Chapters: Threat Model (ch:threat) + Formal Leakage Definitions and Ground
%  Truth (ch:formal) -- two DUAL-MODE files emitted by build_ch3.py.
%  Thesis: Generative AI, Privacy & Personal Data — TADJ Mohamed Walid, ESI SBA
%
%  DUAL-MODE (standalone OR \input via \ThesisMaster). Each emitted file sets
%  one chapter label (the threat file ch:threat; the formal file ch:formal).
%
%  BUILT by build_ch3.py: the rich descriptive blocks (LINDDUN, the four
%  attacker profiles, CVSS calibration, capability matrix, coverage, limitations,
%  the formal L/S definitions, corpus, annotation) are LIFTED with the author's
%  wording from Threat_Model.tex and Formal_Leakage…tex; the reconciliation-
%  sensitive sections (engine+judge, re-identification, attack-family taxonomy,
%  entity taxonomy, diagrams, summary) are AUTHORED from the committed canonical
%  chapter. Source heading levels demoted one step; all source labels/refs
%  namespaced to ch3:*; numbers frozen to canonical (2,190 / 36-defined-31-
%  instantiated / thresholds 0,2,3 / 84-of-100 / 40-of-63 / kappa 0.875,0.968).
% ============================================================================
\ifdefined\ThesisMaster\else
  \documentclass[11pt,a4paper]{report}
  \usepackage[utf8]{inputenc}
  \usepackage[T1]{fontenc}
  \usepackage{lmodern}
  \usepackage[margin=2.5cm]{geometry}
  \usepackage[table,dvipsnames]{xcolor}
  \definecolor{navy}{HTML}{1B2A4A}\definecolor{steel}{HTML}{3D5A80}
  \definecolor{accent}{HTML}{C0392B}\definecolor{lightgray}{HTML}{F4F5F7}
  \definecolor{medgray}{HTML}{D5D8DC}\definecolor{codebg}{HTML}{F8F8F8}
  \definecolor{codeframe}{HTML}{CCCCCC}\definecolor{headerrow}{HTML}{2C3E50}
  \definecolor{rowodd}{HTML}{EBF5FB}\definecolor{roweven}{HTML}{FFFFFF}
  \definecolor{linddunblue}{HTML}{D4E6F1}\definecolor{ink}{RGB}{25,35,45}
  \definecolor{steellight}{HTML}{ECF0F1}\definecolor{steelmid}{HTML}{BDC3C7}
  \definecolor{blockbg}{HTML}{FAFBFC}\definecolor{danger}{RGB}{169,50,38}
  \definecolor{warn}{RGB}{175,96,26}\definecolor{safe}{RGB}{30,132,73}
  \definecolor{capyes}{RGB}{30,132,73}\definecolor{capno}{RGB}{169,50,38}
  \usepackage{booktabs}\usepackage{array}\usepackage{tabularx}\usepackage{longtable}
  \usepackage{colortbl}\usepackage{multirow}\usepackage{float}\usepackage{pifont}
  \usepackage{amsmath,amssymb}\usepackage{enumitem}\usepackage{graphicx}
  \usepackage{caption}\captionsetup{font=small,labelfont={bf,color=navy}}
  \usepackage{listings}
  \newcolumntype{L}{>{\raggedright\arraybackslash}X}
  \newcolumntype{C}[1]{>{\centering\arraybackslash}p{#1}}
  \newcolumntype{R}[1]{>{\raggedleft\arraybackslash}p{#1}}
  \newcolumntype{W}[1]{>{\raggedright\arraybackslash}p{#1}}
  \usepackage[most]{tcolorbox}
  \newtcolorbox{prosebox}{enhanced, breakable, colback=gray!3, colframe=gray!40, boxrule=0.5pt, arc=2pt, left=8pt, right=8pt, top=6pt, bottom=6pt}
  \newtcolorbox{notebox}{enhanced, breakable, colback=white, colframe=navy!40, boxrule=0.5pt, arc=2pt, borderline west={2.5pt}{0pt}{accent!70}, left=10pt, right=8pt, top=6pt, bottom=6pt}
  \newtcolorbox{profilebanner}[2]{enhanced, breakable, colback=blockbg, colframe=steel, leftrule=5pt, rightrule=0.4pt, toprule=0.4pt, bottomrule=0.4pt, arc=0pt, fonttitle=\bfseries\normalsize\color{steel}, title={#1}, after title={\hfill\textcolor{steel}{\small #2}}, top=5pt, bottom=5pt, left=10pt, right=8pt}
  \newtcolorbox{attackbox}{enhanced, breakable, colback=steellight, colframe=steelmid, leftrule=2pt, rightrule=0.2pt, toprule=0.2pt, bottomrule=0.2pt, arc=0pt, top=3pt, bottom=3pt, left=6pt, right=6pt, fontupper=\small\ttfamily\color{ink}}
  \newtcolorbox{cvssbox}[1]{enhanced, breakable, colback=blockbg, colframe=steel, leftrule=4pt, rightrule=0.4pt, toprule=0.4pt, bottomrule=0.4pt, arc=0pt, title={\textbf{\color{steel}CVSS v3.1 Base Score \quad #1}}, fonttitle=\normalsize, top=5pt, bottom=5pt, left=10pt, right=8pt}
  \newtcolorbox{limitbox}{enhanced, breakable, colback=blockbg, colframe=warn, leftrule=4pt, rightrule=0.3pt, toprule=0.3pt, bottomrule=0.3pt, arc=0pt, top=5pt, bottom=5pt, left=8pt, right=6pt}
  \newtcolorbox{defbox}[1][]{enhanced, breakable, colback=navy!3, colframe=navy!70, boxrule=0.8pt, arc=2pt, fonttitle=\bfseries\color{white}, coltitle=white, colbacktitle=navy!80, toptitle=3pt, bottomtitle=3pt, left=8pt, right=8pt, top=6pt, bottom=6pt, title={#1}}
  \newtcolorbox{resultbox}[1][]{enhanced, breakable, colback=lightgray, colframe=steel!60, boxrule=0.6pt, arc=2pt, fonttitle=\bfseries\small, toptitle=2pt, bottomtitle=2pt, left=8pt, right=8pt, top=6pt, bottom=6pt, title={#1}}
  \newcommand{\badgecritical}{\colorbox{danger}{\color{white}\small\textbf{~Critical~}}}
  \newcommand{\badgehigh}{\colorbox{warn}{\color{white}\small\textbf{~High~}}}
  \newcommand{\badgemedium}{\colorbox{safe}{\color{white}\small\textbf{~Medium~}}}
  \newcommand{\yes}{\textcolor{capyes}{\ding{51}}}
  \newcommand{\no}{\textcolor{capno}{\ding{55}}}
  \newcommand{\cvssvec}[1]{\texttt{\small #1}}
  \lstdefinestyle{termstyle}{basicstyle=\ttfamily\footnotesize, backgroundcolor=\color{codebg}, frame=single, rulecolor=\color{codeframe}, framesep=5pt, xleftmargin=5pt, xrightmargin=5pt, breaklines=true, showstringspaces=false, aboveskip=8pt, belowskip=8pt}
  \lstset{style=termstyle}
  \usepackage{microtype}
  \usepackage[hidelinks]{hyperref}
  \usepackage{cleveref}
  \begin{document}
\fi
"""

THREAT_HEAD = r"""\chapter{Threat Model}
\label{ch:threat}

This chapter fixes \emph{who} the attacker is and \emph{how} the attack reaches the system. It
defines four attacker profiles grounded in the LINDDUN privacy-threat framework and calibrated
against CVSS; organises the adversarial campaign into eight attack families; maps the system's
attack surface and trust boundaries; and states the threat model's limits. The formal metrics
that score what these attackers disclose, and the synthetic ground truth they disclose it from,
are the subject of Chapter~\ref{ch:formal}. One note on scope: the foundations summarised here
were written before the experimental campaign and, in a few places, anticipated components the
campaign then revised; where that happens this chapter states what was actually built and points
forward, rather than repeating a superseded plan.

\section{Privacy threat modelling with LINDDUN}
\label{sec:ch3-linddun}

"""

FORMAL_HEAD = r"""\chapter{Formal Leakage Definitions and Ground Truth}
\label{ch:formal}

The threat model of Chapter~\ref{ch:threat} fixed who attacks and how; this chapter fixes
\emph{what counts as a leak} and \emph{what the ground truth says was there to leak}. It gives
the two formal metrics --- the binary leakage function $L$ and the severity score $S$ --- that
turn ``the system revealed something it should not have'' into a number two researchers would
compute identically; the deterministically generated synthetic corpus; the entity-level
annotation that serves as the answer key; the post-hoc measurement engine and the language-model
judge that operates within it; and the re-identification evidence behind the linkability
residual. These are the definitions the results chapters use: the $(L,S)$ framework that
Chapters~\ref{ch:defenses} and~\ref{ch:tradeoff} measure leakage and severity through.

\section{Formal leakage definitions}
\label{sec:ch3-formal}

"""

TAXONOMY = r"""
\section{The attack taxonomy}
\label{sec:ch3-families}

The adversarial campaign is organised into eight attack families (F1--F8), each a distinct
mechanism with a distinct scoring profile, together spanning the operational threat space
(Table~\ref{tab:ch3-families}). The families map to the profiles exactly as
Chapter~\ref{ch:baseline} uses them: F1--F7 are shared by the Internal and External profiles;
corpus poisoning (F8) is an Admin capability, since it acts on the index before any query; and
the Third-Party profile runs no live family. The fifty-two scenarios in the campaign are drawn
from this taxonomy.

\begin{table}[h]
\centering
\caption{The eight attack families and their profile assignment. Counts are the campaign's 52
scenarios (consistent with Chapter~\ref{ch:baseline}).}
\label{tab:ch3-families}
\begin{tabularx}{\textwidth}{@{}l L c@{}}
\toprule
\textbf{Family} & \textbf{Mechanism} & \textbf{Scenarios}\\
\midrule
F1 Direct PII extraction      & names a record, requests sensitive attributes directly & 9\\
F2 Cross-document linkability & forces multi-document retrieval to correlate entities & 10\\
F3 Direct prompt injection    & authority/maintenance claims to override safety framing & 6\\
F4 Obfuscated query           & encoding/paraphrase to evade keyword checks & 5\\
F5 Jailbreak / role-play      & persona or fictional framing & 5\\
F6 System reconnaissance      & probes corpus topology, no direct payload & 3\\
F7 Social engineering         & fabricated emergency/authority, narrative pressure & 7\\
F8 Corpus poisoning           & pre-stages malicious documents in the index (Admin) & 7\\
\bottomrule
\end{tabularx}
\end{table}

"""

# entity taxonomy table appended at the end of the formal-definitions section
TAXTABLE = r"""
\subsection{The leakage taxonomy that supplies \texorpdfstring{$s(e)$}{s(e)}}
\label{subsec:ch3-taxonomy}

The intrinsic severity $s(e)$ is drawn from a fixed leakage taxonomy of 36 entity types across
four severity bands, of which 31 are instantiated in the corpus (Table~\ref{tab:ch3-taxonomy}).
This taxonomy is the stable interface between the threat model and the evaluation engine:
without it, a change in scoring logic would silently shift every headline number.

\begin{table}[h]
\centering
\caption{The leakage taxonomy: four severity bands with representative entity types. The corpus
instantiates 31 of the 36 defined types; the uncovered types are discussed in
Section~\ref{sec:ch3-annotation}.}
\label{tab:ch3-taxonomy}
\begin{tabularx}{\textwidth}{@{}c l L@{}}
\toprule
\textbf{$s(e)$} & \textbf{Band} & \textbf{Representative entity types}\\
\midrule
5 & Critical & national identifier, API key, JWT, password hash, private key\\
4 & High     & full name, email, phone, address, date of birth, IBAN, health-record identifier\\
3 & Medium   & salary, employee ID, medical condition, immigration status, age$+$gender\\
2 & Low      & department, job title, performance rating, office location, project\\
\bottomrule
\end{tabularx}
\end{table}

"""

ENGINE = r"""
\section{The measurement engine and the judge}
\label{sec:ch3-engine}

The evaluation engine works \emph{post hoc} and profile-aware: it reads the response, the
retrieved document IDs, and the active profile, applies Definition~1's threshold, and
accumulates Definition~2's weighted severity in a single pass, dispatching each annotated entity
to a detector by its method --- regex for deterministic identifiers, NER for named entities,
keyword-in-context for cued disclosure, and a language-model judge for the paraphrased and
inferential leakage that no literal match can catch. The foundations scoped this judge as a
component to be calibrated against baseline measurements rather than against a stub; in the
experimental campaign it was realised as a \emph{single validated judge} (Claude Opus~4.7),
agreeing with the human at $\kappa = 0.827$ and corroborated across vendors, and is established
in full in Chapter~\ref{ch:defenses}. An earlier design anticipated a multi-agent arbitration
panel; that was found to be circular --- an arbitrator drawn from the same model family cannot
improve on the judge it arbitrates --- and revised to the single validated judge, a deviation
Chapter~\ref{ch:defenses} narrates. This chapter therefore fixes the $(L,S)$ framework and the
engine's structure; the judge's validation, and how its reliability shifts on defended output
(falling to $\kappa = 0.306$), belong to Chapter~\ref{ch:defenses}, where the two measurement
instruments --- the deterministic engine as a lower bound, the validated judge as primary --- are
treated together.

"""

REID = r"""
\section{Re-identification: empirical evidence for the linkability threat}
\label{sec:ch3-reid}

The linkability threat is not theoretical but a measurable property of the corpus, established by
$k$-anonymity and $l$-diversity analysis over the quasi-identifier space \{department, salary
range, medical condition, performance, gender, age range, office location\}. Across all 2-, 3-,
and 4-attribute combinations, the worst --- department, medical condition, age range, office
location --- uniquely identifies \textbf{84 of 100 employees} without ever requesting a name or
any directly identifying field; sixty-one combinations leave a majority of the population in
singleton classes. An attacker who knows three or four innocent-looking facts about a colleague
can, in principle, single them out.

\paragraph{Reading the 84-in-100 figure honestly.} This number is best read as an \emph{upper
bound} on the corpus's intrinsic combinatorial uniqueness, not a conservative one. Because each
attribute is sampled \emph{independently}, the synthetic corpus maximises the number of distinct
quasi-identifier combinations; a real corpus, where attributes correlate (salaries cluster,
conditions track age and occupation), would yield \emph{fewer} distinct combinations and thus
less intrinsic uniqueness. This is a separate matter from the observation that real-world
re-identification risk could nonetheless be \emph{higher}, because a real attacker brings
auxiliary information --- public records, social media, directories --- that the synthetic setting
deliberately omits. The two arguments point in opposite directions and must not be conflated.

\paragraph{$l$-diversity, and a self-caught error.} The companion $l$-diversity analysis
illustrates the framework catching its own mistake. The original computation returned 100\%
vulnerability, but this was a definitional artefact: \texttt{medical\_condition} appeared in both
the grouping keys and the sensitive set, forcing $l = 1$ on every class by construction. The
corrected analysis (sensitive set \{name, national ID, salary\}) reports \textbf{40 of 63
equivalence classes (63\%) vulnerable} at $n = 100$ for the seed-42 corpus. A 200-trial Monte
Carlo simulation --- each drawing a fresh 100-employee corpus --- shows the $n = 100$ rate is not
an artefact of the particular seed (mean 58.7\%, range $[47.5\%, 65.7\%]$); scaling the
\emph{population size} then shows the threat is genuinely sample-size driven, the rate falling to
4.7\% at $n = 1{,}000$, which on a thousand-employee enterprise still implies roughly 47
individuals in sensitive-attribute-leaking classes. The threat is real at every population size
relevant to enterprise RAG; the small-corpus expression of it simply looks more dramatic.

"""

DIAGRAMS = r"""
\section{System-architecture diagrams}
\label{sec:ch3-arch}

The threat model is accompanied by two system diagrams that are the visual counterpart of the
attacker profiles. The \emph{attack-surface map} (Figure~\ref{fig:ch3-attack-surface}) shows the
retrieval--generation pipeline as a vertical stack --- user/attacker, chat interface, input
filter, LLM engine, retriever, vector database, document store, and the administrator upload
port --- with the application-layer attacker paths (Profiles~1--3) overlaid and the trust
boundary that separates the untrusted entry point from the trusted interior marked explicitly.
The \emph{trust-boundary map} (Figure~\ref{fig:ch3-trust-boundary}) reorganises the same
components into trusted and untrusted zones, answering the complementary question of \emph{where}
data crosses from attacker-controllable to organisation-controlled territory. Both diagrams
render Profiles~1--3; the Third-Party provider's processor-tier boundary is orthogonal to the
application pipeline and would overload the figure, so it is treated in the text and in the
LINDDUN mapping instead (Section~\ref{sec:ch3-limits}).

\begin{figure}[hbtp]
\centering
\includegraphics[width=\textwidth]{fig_attack_surface_map.png}
\caption{RAG system --- attack-surface map. The seven-component pipeline with the three
application-layer attacker paths (Internal, External, Admin) overlaid; the dashed line marks the
trust boundary between the untrusted entry point and the trusted interior.}
\label{fig:ch3-attack-surface}
\end{figure}

\begin{figure}[hbtp]
\centering
\includegraphics[width=\textwidth]{fig_trust_boundary_map.png}
\caption{RAG system --- trust-boundary map. The same components reorganised into trusted and
untrusted zones, showing where data crosses from attacker-controllable to
organisation-controlled territory.}
\label{fig:ch3-trust-boundary}
\end{figure}

"""

KAPPA = r"""
\subsection{Annotation validity}
\label{subsec:ch3-kappa}

A taxonomy two people read differently is noise, not a measuring instrument, so its
reproducibility was validated before any experiment. Two annotators independently labelled the
same set of 20 RAG responses against the taxonomy; binary agreement reached Cohen's
$\kappa = 0.875$ ($P_o = 0.95$, $P_e = 0.60$) and weighted ordinal agreement $\kappa_w = 0.968$,
both in the ``strong''/``near-perfect'' band and clearing the $\kappa \geq 0.80$ acceptance bar.
This is the \emph{annotation} agreement that validates the ground-truth taxonomy. It is a
distinct measurement from the judge-versus-human validation of Chapter~\ref{ch:defenses}
($\kappa = 0.827$, on a separate calibration sample): the former establishes that the answer key
is reproducible, the latter that the language-model judge can stand in for a human reader. They
must not be conflated.

"""

SUMMARY_THREAT = r"""
\section{Summary}
\label{sec:ch3-threat-summary}

This chapter fixed who attacks and how. Four LINDDUN-grounded, CVSS-calibrated attacker
profiles --- curious insider, external adversary, malicious administrator, and offline
third-party --- with explicit authorization thresholds; eight attack families mapping to those
profiles; and the system's attack surface and trust boundaries, with the threat model's scope
limits stated explicitly. The metrics that score these attacks, and the synthetic corpus they
run against, are established in Chapter~\ref{ch:formal}.
"""

SUMMARY_FORMAL = r"""
\section{Summary}
\label{sec:ch3-formal-summary}

This chapter fixed what counts as a leak and what was there to leak: the binary leakage function
$L$ and the severity score $S$, with the derived $\Delta S$ and $\bar{S}_{\text{residual}}$; a
deterministically generated 155-document corpus with 2{,}190 taxonomy-validated annotations
($\kappa = 0.875$, distinct from the judge validation of Chapter~\ref{ch:defenses}); the
profile-aware measurement engine and its validated judge; and re-identification evidence --- 84
of 100 uniquely identifiable on four quasi-identifiers, read as an upper bound on intrinsic
corpus uniqueness --- that grounds the linkability threat the later chapters find hardest to
defend. The profiles, families, metrics, and thresholds established across
Chapters~\ref{ch:threat} and~\ref{ch:formal} are binding for Chapters~\ref{ch:baseline},
\ref{ch:defenses}, and~\ref{ch:tradeoff}.
"""

CLOSE = "\n\\ifdefined\\ThesisMaster\\else\n  \\end{document}\n\\fi\n"

# ===================== assemble (two chapters) =====================
threat = [PRE, THREAT_HEAD]
threat.append(lift(LINDDUN))                                 # LINDDUN (keep first heading)
threat.append("\n\\section{The attacker profiles}\n\\label{sec:ch3-profiles}\n\n")
threat.append(lift(PROFILES))                                # methodology + CVSS + P1-4
threat.append(lift(CAPAB))                                   # capability matrix
threat.append(lift(COVERAGE))                                # coverage + adequacy
threat.append(TAXONOMY)                                      # authored attack families
threat.append(DIAGRAMS)                                      # authored figures
threat.append("\n\\section{Limitations of the threat model}\n\\label{sec:ch3-limits}\n\n")
threat.append(lift(LIMITS, drop_first=True))                 # limitations
threat.append(SUMMARY_THREAT)
threat.append(CLOSE)

formal = [PRE, FORMAL_HEAD]
formal.append(lift(FDEF, drop_first=True))                   # L/S defboxes
formal.append(TAXTABLE)                                      # entity taxonomy table
formal.append("\n\\section{The ground-truth corpus}\n\\label{sec:ch3-corpus}\n\n")
formal.append(lift(FCORP, drop_first=True))                  # corpus
formal.append("\n\\section{Entity-level annotation}\n\\label{sec:ch3-annotation}\n\n")
formal.append(lift(FANNOT, drop_first=True))                 # annotation
formal.append(KAPPA)                                         # annotation validity (kappa)
formal.append(ENGINE)                                        # engine + judge (authored)
formal.append(REID)                                          # re-id (authored)
formal.append(SUMMARY_FORMAL)
formal.append(CLOSE)

t_text = "".join(threat)
f_text = "".join(formal)
open(OUT_THREAT, "w", encoding="utf-8").write(t_text)
open(OUT_FORMAL, "w", encoding="utf-8").write(f_text)

# ----- diagnostics -----
for name, text in (("THREAT (" + OUT_THREAT.split("/")[-1] + ")", t_text),
                   ("FORMAL (" + OUT_FORMAL.split("/")[-1] + ")", f_text)):
    print(f"--- {name} --- lines {text.count(chr(10))} | sections {text.count(chr(92)+'section{')}")
    for chk in ("L{", "Chapter~1", "Chapter~2", "Section~2.2", "Section~3.3",
                "Table~6", "Phase~2 Report", "full-stack", "31 / 35", "33 of the 37"):
        c = text.count(chk)
        if c:
            print(f"      RESIDUAL {chk!r}: {c}")
print("label ch:threat in THREAT:", "\\label{ch:threat}" in t_text,
      "| label ch:formal in FORMAL:", "\\label{ch:formal}" in f_text)
print("ch:formal NOT in THREAT:", "\\label{ch:formal}" not in t_text,
      "| ch:threat NOT in FORMAL:", "\\label{ch:threat}" not in f_text)
