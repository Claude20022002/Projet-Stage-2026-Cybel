# IEEE ICRA 2027 — LaTeX paper (8 pages max)

Companion technical paper for **CYBEL** (reverse-engineering the CIOT TY1251D-03195 reception robot; open rosbridge stack; voice and facial interaction).

**Venue:** 2027 IEEE International Conference on Robotics and Automation (ICRA), Coex Convention & Exhibition Center, Seoul, Republic of Korea.
**Format confirmed 2026-07-19** against <https://2027.ieee-icra.org/contribute/>: 8 pages for the complete paper including all material and references, submitted via PaperPlaza.
**First submission deadline:** 2026-09-15, 23:59 PST.

> Retargeted from an earlier ROSCon Korea 2027 draft (same venue city). ICRA is a broader robotics research audience than a ROS-specific workshop track, so the paper leans less on ROS-community jargon than the original draft did.

## Files

| File | Role |
|------|------|
| `main.tex` | Article, IEEE two-column (English) |
| `references.bib` | Bibliography |
| `Makefile` | Build automation |

## Prerequisites

- TeX Live or MiKTeX with packages: `IEEEtran`, `tikz`, `booktabs`, `hyperref`
- `IEEEtran.cls` is included in standard TeX distributions

## Build

```bash
cd paper/icra_2027
make          # or: pdflatex main && bibtex main && pdflatex main && pdflatex main
```

Output: `main.pdf`

## Page limit

Target: **$\leq$ 8 pages** including references (IEEE conference two-column). Confirmed compiling to exactly 8 pages as of this revision.

Before submission:
1. Replace remaining `\ph{...}` placeholders in `main.tex` with measured values collected on the robot (guided-tour completion rate, Termux autonomous uptime, voice round-trip latency, wake-word false-trigger rate, FAQ repeat-question success rate).
2. Compile and check page count: `pdfinfo main.pdf | grep Pages`.
3. Select at least three keywords from the official ICRA keyword list (IEEE-RAS) for the PaperPlaza submission form.
4. If $> 8$ pages after adding real data in place of placeholders: shorten the Related Work subsections or the Discussion first — they were the last things trimmed to fit the limit.

## Related

- Long-form markdown draft (earlier revision, being reconciled with this version): [../article_cybel_retroconception.md](../article_cybel_retroconception.md)
- Architecture: [../../docs/ARCHITECTURE_LOGICIELLE.md](../../docs/ARCHITECTURE_LOGICIELLE.md)
- Style reference: [../exemple/wincom_paper.pdf](../exemple/wincom_paper.pdf) (HESTIM-affiliated IEEE-format paper, used for title concision and claim-hedging conventions)
