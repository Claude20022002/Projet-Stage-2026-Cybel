# Reclaiming Closed Service Robots — IEEE ICRA 2027

**Venue:** 2027 IEEE International Conference on Robotics and Automation, Seoul.
**Limit:** 8 pages including references, IEEE two-column, submitted via PaperPlaza.
**First submission deadline:** 2026-09-15, 23:59 PST.

Currently compiles to **8 / 8 pages**. There is no margin: anything added has to be paid for by
cutting something else.

---

## Layout

`main.tex` holds no prose. It is a map of the paper, and everything else lives in one file per
concern, so a section can be rewritten without scrolling past a 40-line TikZ block.

```text
icra_2027/
├── main.tex               document skeleton: title, author, \input order
├── preamble.tex           packages, macros, \graphicspath
├── references.bib         bibliography (23 entries, all with DOI where one exists)
│
├── sections/              one file per section, in reading order
│   ├── 00-abstract.tex        abstract + keywords — rewrite LAST
│   ├── 01-introduction.tex    obstacles, research question, H1–H4, C1–C3
│   ├── 02-related-work.tex    six subsections + positioning table
│   ├── 03-platform.tex        hardware, network segments, what is locked
│   ├── 04-methodology.tex     principles, vantage points, seven-phase pipeline
│   ├── 05-command-surface.tex recovered protocol, edge stack, speech, interaction
│   ├── 06-evaluation.tex      hypothesis verdicts, measurements, comparison
│   ├── 07-discussion.tex      findings, generalisation, ethics, limitations
│   └── 08-conclusion.tex      conclusion + acknowledgment
│
├── figures/               one file per figure, \input from its section
│   ├── fig-robot.tex          Fig. 1  robot photograph
│   ├── fig-network.tex        Fig. 2  three network segments
│   ├── fig-vantage.tex        Fig. 3  vantage points and blind spots
│   ├── fig-h4-timeline.tex    Fig. 4  transport vs execution
│   ├── fig-vendor-map.tex     Fig. 5  vendor application and map
│   └── fig-results.tex        Fig. 6  the only data plot (full width)
│
├── tables/                one file per table
│   ├── tab-positioning.tex    Table I    positioning against related work
│   ├── tab-phases.tex         Table II   the seven-phase pipeline
│   ├── tab-metrics.tex        Table III  measurements + what each establishes
│   └── tab-compare.tex        Table IV   capability comparison
│
├── assets/                images referenced by \includegraphics
├── tools/
│   ├── stats.py               recompute every interval quoted in the paper
│   └── prepare_assets.py      regenerate the redacted photographs
│
├── build.ps1              Windows build (make is not installed here)
├── Makefile               same targets, for Unix and CI
└── review/                reviewer reports and our response
    ├── Review_CYBEL_Remarques.md
    ├── Reviewer_Report_CYBEL.md
    └── REPONSE.md             traceability of every remark and every number
```

Each file opens with a comment stating what belongs in it and which rule applies. Those comments
are not decoration: most of them record a specific reviewer objection that the current version
answers.

---

## Build

```powershell
.\build.ps1            # build, then report the page count
.\build.ps1 check      # build + errors, citations, placeholders, anonymisation
.\build.ps1 pages      # page count only
.\build.ps1 stats      # recompute every interval
.\build.ps1 assets     # regenerate the redacted photographs
.\build.ps1 clean
```

On Unix or in CI, `make`, `make check`, `make stats` do the same. Requires MiKTeX or TeX Live
with `IEEEtran`, `tikz`, `pgfplots`, `siunitx`, `booktabs`, `hyperref`.

---

## Rules this paper is written under

**Nothing is invented.** Every number traces to a repository file or a git commit. The mapping is
in [review/REPONSE.md](review/REPONSE.md) section 4. Three indicators are campaign readings with
no archived log; they carry a dagger in Table III and Section IV says so explicitly.

**Never hand-edit a confidence interval.** Run `.\build.ps1 stats` and copy the result into both
`tables/tab-metrics.tex` and `figures/fig-results.tex`. Note that the figure takes *offsets*, not
bounds. The two files must agree, because a reviewer who recomputes will see it if they do not.

**Concepts, not identifiers.** No source filenames, method names or vendor package names in the
prose. The one deliberate exception is the broadcast listing in Section V, which is itself the
contribution. This was an explicit reviewer request.

**Anonymised.** The institution is not named and the robot model is not identified; the photograph
in Fig. 1 has its identifying marks blurred. `.\build.ps1 check` enforces this. If ICRA 2027 turns
out to require double-blind submission, the author names and the repository citation must come out
too — see [review/REPONSE.md](review/REPONSE.md) section 5.

**Claims stay inside the evidence.** Proportions carry their `n` and a Wilson interval. The bench
comparison is not significant at `n = 3` per arm and the paper says so. Where the vendor system is
better, Table IV says that too.

---

## Before submitting

1. `.\build.ps1 check` — all four checks must pass and the page count must be 8 or fewer.
2. Make the repository cited in `references.bib` public, with the field logs behind Section IV.
3. Confirm on the call for papers whether the submission is double-blind.
4. Pick at least three keywords from the official IEEE-RAS list for the PaperPlaza form.
5. Read the PDF once end to end. The page budget is exhausted, so anything new displaces
   something old — Related Work and Discussion are the places to cut first.

## Related

- Reviewer reports and our point-by-point response: [review/](review/)
- Style reference used for structure and claim-hedging: [../exemple/wincom_paper.pdf](../exemple/wincom_paper.pdf)
- Earlier long-form draft: [../article_cybel_retroconception.md](../article_cybel_retroconception.md)
