# IEEE ICRA 2027 paper — CYBEL
MAIN = main
LATEX = pdflatex
BIBTEX = bibtex

.PHONY: all clean view

all: $(MAIN).pdf

$(MAIN).pdf: $(MAIN).tex references.bib
	$(LATEX) $(MAIN)
	$(BIBTEX) $(MAIN)
	$(LATEX) $(MAIN)
	$(LATEX) $(MAIN)
	@echo "--- Page count ---"
	@pdfinfo $(MAIN).pdf 2>/dev/null | grep Pages || echo "(install pdfinfo to show page count)"

clean:
	rm -f $(MAIN).pdf $(MAIN).aux $(MAIN).bbl $(MAIN).blg $(MAIN).log $(MAIN).out

view: $(MAIN).pdf
	@echo "Open $(MAIN).pdf with your PDF viewer"
