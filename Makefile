.PHONY: install build validate stars plots

install:
	pip install -r requirements.txt

validate:
	python scripts/validate.py

plots:
	python scripts/plot_progress.py

build: validate plots
	python scripts/build_readme.py

stars:
	python scripts/update_stars.py
