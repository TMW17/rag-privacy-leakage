# IPM manuscript

Condensed paper for *Information Processing & Management*. **Separate from the
thesis** — nothing here reads from or writes to `results/phase3_4/report/thesis/`,
and `references.bib` is an independent copy, not a shared file. Editing the thesis
does not change this paper, and vice versa.

## Layout

| File | Role |
| ---- | ---- |
| `manuscript.tex` | **Anonymized** root. No names, affiliations, acknowledgements, ORCIDs, or identifying URLs. Upload as the manuscript. |
| `title_page.tex` | The only file carrying identifying information. Upload separately. |
| `sections/01_intro.tex` … `07_conclusion.tex` | Section bodies, `\input` by `manuscript.tex`. |
| `references.bib` | 57 entries, copied from the thesis. **Independent copy** — a change here does not affect the thesis, and a thesis bib change does not land here automatically. |

## Build

```bash
latexmk -pdf manuscript.tex
latexmk -pdf title_page.tex
```

Class is Elsevier CAS single-column (`cas-sc`), bibliography style
`cas-model2-names` (author–year), loaded with `natbib`. Both compile clean.

## Two things that will bite

**`cas-sc` will not run `\maketitle` without an author block.** The anonymized
root therefore carries an empty `\author[1]{}` with the affiliation
`Author details withheld for anonymized review`. Removing it does not make the
file "more anonymous" — it makes it fail to compile with
`! File ended while scanning use of \next`.

**The generative-AI declaration title is prescribed by Elsevier and must appear
verbatim**, immediately before the references:

> Declaration of generative AI and AI-assisted technologies in the manuscript
> preparation process

## Anonymization check before submitting

```bash
grep -rniE "tadj|mohamed|walid|sidi bel|algeria|tmw17|github\.com|@gmail" manuscript.tex sections/
grep -rnw "ESI" manuscript.tex sections/
```

Both should return nothing. Note `grep -i esi` alone produces false positives —
it matches inside *thesis* and *design*, so use `-w`.

## Section 1

`sections/01_intro.tex` is a placeholder. Overwrite the whole file with the
supplied draft; `manuscript.tex` already `\input`s it, so nothing else changes.
