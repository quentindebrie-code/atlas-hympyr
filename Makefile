.PHONY: install test lint run telecharger donnees docker

install:
	pip install -e ".[dev,etl]"

test:
	pytest

lint:
	ruff check . && ruff format --check .

run:
	streamlit run app.py

# Données réelles (après avoir complété config/settings.yaml et déposé les fichiers dans data/raw/)
telecharger:
	python -m atlas_hympyr.etl.telecharger

donnees:
	python -m atlas_hympyr.etl.build

docker:
	docker build -t atlas-hympyr .
