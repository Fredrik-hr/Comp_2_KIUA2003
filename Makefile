# Linux/macOS/CI. On Windows use .\make.ps1 <target> (same targets).
PY ?= .venv/bin/python
AGENDA ?= tests/cases/algorithms_synthetic/agenda.yaml

.PHONY: setup test lint run eval eval-live ui watch purge synthetic

setup:
	python3 -m venv .venv && $(PY) -m pip install -e ".[dev]"

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check src eval tests

run:
	PYTHONPATH=src $(PY) -m briefer run $(AGENDA)

# Deterministic and free: replays recorded LLM answers (fails on a cache miss).
eval:
	$(PY) eval/harness.py $(if $(CASE),--case $(CASE))

# Calls the configured models and refreshes the replay cache.
eval-live:
	$(PY) eval/harness.py --live $(if $(CASE),--case $(CASE))

ui:
	PYTHONPATH=src $(PY) -m briefer ui

watch:
	PYTHONPATH=src $(PY) -m briefer watch

purge:
	PYTHONPATH=src $(PY) -m briefer purge

synthetic:
	$(PY) tests/cases/make_synthetic.py
