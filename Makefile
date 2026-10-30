# Checks of the draft specification. No Go in this repository; the Python
# tooling runs from a local virtualenv.

PYTHON     ?= python3
VENV       ?= .venv
VENV_PY    := $(VENV)/bin/python
VENV_STAMP := $(VENV)/.install-stamp

.DEFAULT_GOAL := help

.PHONY: help check fmt-check lint test

help: ## This help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z0-9_-]+:.*?## / {printf "%-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

$(VENV_STAMP): scripts/requirements.txt
	$(PYTHON) -m venv $(VENV)
	$(VENV_PY) -m pip install --quiet -r scripts/requirements.txt
	@touch $@

check: fmt-check lint test ## Run every check

fmt-check: $(VENV_STAMP) ## Fail on CR, trailing whitespace or a missing final newline
	$(VENV_PY) scripts/validate.py fmt

lint: $(VENV_STAMP) ## Check the schema against JSON Schema 2020-12 and parse the YAML files
	$(VENV_PY) scripts/validate.py lint

test: $(VENV_STAMP) ## Validate every example against the schema
	$(VENV_PY) scripts/validate.py test
