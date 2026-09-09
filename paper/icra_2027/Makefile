# ============================================================================
#  Reclaiming Closed Service Robots — IEEE ICRA 2027
#  make          build the PDF and report the page count
#  make pages    page count only (hard limit: 8)
#  make stats    recompute every interval quoted in the paper
#  make assets   regenerate the redacted photographs
#  make check    build, then run the pre-submission checks
#  make clean    remove build artefacts
# ============================================================================
MAIN   = main
LATEX  = pdflatex -interaction=nonstopmode
BIBTEX = bibtex
LIMIT  = 8

SOURCES = $(MAIN).tex preamble.tex references.bib \
          $(wildcard sections/*.tex) $(wildcard figures/*.tex) \
          $(wildcard tables/*.tex) $(wildcard assets/*)

.PHONY: all pages stats assets check clean

all: $(MAIN).pdf

$(MAIN).pdf: $(SOURCES)
	$(LATEX) $(MAIN)
	$(BIBTEX) $(MAIN)
	$(LATEX) $(MAIN)
	$(LATEX) $(MAIN)
	@$(MAKE) --no-print-directory pages

pages:
	@python -c "import re,sys; \
d=open('$(MAIN).pdf','rb').read(); \
n=len(re.findall(rb'/Type\s*/Page[^s]',d)); \
print(f'pages: {n} / $(LIMIT) max'); \
sys.exit(0 if n<=$(LIMIT) else 1)"

stats:
	@python tools/stats.py

assets:
	@python tools/prepare_assets.py

check: $(MAIN).pdf
	@echo "--- LaTeX errors ---"
	@! grep -E '^!' $(MAIN).log || (echo "FAILED"; exit 1)
	@echo "none"
	@echo "--- unresolved citations and references ---"
	@! grep -E 'Citation .* undefined|Reference .* undefined' $(MAIN).log || (echo "FAILED"; exit 1)
	@echo "none"
	@echo "--- leftover placeholders ---"
	@! grep -rniE 'TODO|FIXME|\\\\ph\{' $(MAIN).tex preamble.tex sections figures tables || (echo "FAILED"; exit 1)
	@echo "none"
	@echo "--- anonymisation ---"
	@! grep -rniE 'hestim|casablanca|morocco|ciot|ty1251|welcomepatrol|sentrymove|cerim' \
	    $(MAIN).tex preamble.tex references.bib sections figures tables \
	    || (echo "FAILED"; exit 1)
	@echo "clean"

clean:
	rm -f $(MAIN).pdf $(MAIN).aux $(MAIN).bbl $(MAIN).blg $(MAIN).log $(MAIN).out \
	      $(MAIN).fdb_latexmk $(MAIN).fls
