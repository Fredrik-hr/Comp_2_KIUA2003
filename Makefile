# Linux/macOS/CI. On Windows use .\make.ps1 <target> (same targets).
PY ?= .venv/bin/python
AGENDA ?= tests/cases/fylkesutvalget_2026-09-29/agenda.yaml
MEETING_PDF := fylkesutvalget_2026-09-29.pdf
MEETING_URL := https://prod01.elementscloud.no/publikum/920717152/DmbMeeting/1544

.PHONY: setup test lint run eval eval-live ui watch purge synthetic

setup:
	python3 -m venv .venv && $(PY) -m pip install -e ".[dev]"

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check src eval tests

run:
	@case "$(AGENDA)" in *fylkesutvalget_2026-09-29*) test -f $(MEETING_PDF) || \
	  { echo "$(MEETING_PDF) is missing in the project root. Download it from $(MEETING_URL) (see README)."; exit 1; };; esac
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
