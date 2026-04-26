MAIN = main

.PHONY: report clean watch

report:
	latexmk -xelatex -interaction=nonstopmode $(MAIN).tex

watch:
	latexmk -xelatex -pvc $(MAIN).tex

clean:
	latexmk -C
	rm -f *.aux *.bbl *.bcf *.blg *.log *.run.xml *.toc *.out *.xdv
