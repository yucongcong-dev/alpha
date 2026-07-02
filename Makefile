.PHONY: test help-check whitespace-check scan-secrets ruff-check check clean-runtime

PYTHON ?= python3
PYTHONPATH ?= src
SECRET_PATTERN := github_[p]at_[A-Za-z0-9_]+|WQB_[P]ASSWORD=|Authorization: [B]asic

test:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m pytest -q

help-check:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m alpha --help >/dev/null

whitespace-check:
	git diff --check

scan-secrets:
	@if rg -n "$(SECRET_PATTERN)" . --glob '!Makefile'; then \
		echo "[check] sensitive literal scan failed" >&2; \
		exit 1; \
	fi

ruff-check:
	@if $(PYTHON) -m ruff --version >/dev/null 2>&1; then \
		$(PYTHON) -m ruff check .; \
	else \
		echo "[check] ruff not installed; run: $(PYTHON) -m pip install -r requirements.txt" >&2; \
		exit 1; \
	fi

check: test help-check whitespace-check scan-secrets ruff-check

clean-runtime:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m alpha clean
