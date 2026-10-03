.PHONY: install build validate sync

install:
	pip install -r requirements.txt

validate:
	python scripts/validate.py

build: validate
	python scripts/build_readme.py

sync:
	python scripts/sync_arxiv.py
