# ROSCon Korea 2027 — LaTeX paper (8 pages max)

Companion technical paper for a ROSCon Korea talk proposal on **CYBEL** (reverse-engineering CIOT TY1251D + open rosbridge stack).

> **Note:** ROSCon events typically accept **talk proposals** (title, abstract, summary) rather than formal peer-reviewed papers. This 8-page IEEE-format document serves as a **technical report / proceedings draft** to accompany slides, submit to a workshop track if offered, or publish as preprint.

## Files

| File | Role |
|------|------|
| `main.tex` | Article IEEE two-column (English) |
| `references.bib` | Bibliography |
| `Makefile` | Build automation |

## Prerequisites

- TeX Live or MiKTeX with packages: `IEEEtran`, `tikz`, `booktabs`, `hyperref`
- `IEEEtran.cls` is included in standard TeX distributions

## Build

```bash
cd paper/roscon_korea_2027
make          # or: pdflatex main && bibtex main && pdflatex main && pdflatex main
```

Output: `main.pdf`

## Page limit

Target: **$\leq$ 8 pages** including references (IEEE conference two-column).

Before submission:
1. Replace `[Author Name]` and email in `main.tex`
2. Compile and check page count: `pdfinfo main.pdf | grep Pages`
3. If $> 8$ pages: shorten Section 6 or move tables to appendix

## ROSCon Korea talk proposal (separate)

Prepare in parallel (typical ROSCon KR format):
- **Title** (max ~30 chars Korean CFP / 70 chars global)
- **Abstract** for program committee
- **Summary** (50 chars for schedule)
- **Link:** GitHub repo or `docs/ARCHITECTURE_LOGICIELLE.md`

Suggested talk title: *CYBEL: Reverse-Engineering a Closed Android ROS Reception Robot*

## Related

- Long-form markdown: [../article_cybel_retroconception.md](../article_cybel_retroconception.md)
- Architecture: [../../docs/ARCHITECTURE_LOGICIELLE.md](../../docs/ARCHITECTURE_LOGICIELLE.md)
