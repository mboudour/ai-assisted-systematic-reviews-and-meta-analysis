.PHONY: all paper supplement clean check

all: paper supplement check

paper:
	mkdir -p build/paper
	latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build/paper jdiq_experience_paper.tex
	cp build/paper/jdiq_experience_paper.pdf jdiq_experience_paper.pdf

supplement:
	mkdir -p build/supplement
	latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build/supplement jdiq_online_supplement.tex
	cp build/supplement/jdiq_online_supplement.pdf jdiq_online_supplement.pdf

check:
	@test "$$(pdfinfo jdiq_experience_paper.pdf | awk '/^Pages:/{print $$2}')" = "10"
	@test "$$(pdfinfo jdiq_online_supplement.pdf | awk '/^Pages:/{print $$2}')" -ge "1"
	@! grep -E 'Overfull \\[hv]box|undefined references|Citation.*undefined' build/paper/jdiq_experience_paper.log build/supplement/jdiq_online_supplement.log

clean:
	rm -rf build jdiq_experience_paper.pdf jdiq_online_supplement.pdf
