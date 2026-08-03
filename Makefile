.PHONY: install-dev python-version-check test coverage-check help-check whitespace-check docs-check scan-secrets repo-boundary-check removed-compat-file-check compat-import-check arch-boundary-check todo-check sync-config config-sync-check ruff-check format-check mypy-check check clean-runtime clean-dev package

ifeq ($(OS),Windows_NT)
GIT_EXEC_PATH := $(shell git --exec-path)
WINDOWS_SHELL := $(patsubst %/mingw64/libexec/git-core,%/usr/bin/sh.exe,$(GIT_EXEC_PATH))
SHELL := $(WINDOWS_SHELL)
export PATH := $(dir $(WINDOWS_SHELL));$(PATH)
ifndef PYTHON
PYTHON := $(shell if command -v py >/dev/null 2>&1; then echo "py -3.10"; elif command -v python >/dev/null 2>&1; then echo python; else echo python; fi)
endif
else
ifndef PYTHON
PYTHON := $(shell if command -v python3.10 >/dev/null 2>&1; then echo python3.10; elif command -v python3 >/dev/null 2>&1; then echo python3; else echo python; fi)
endif
endif
PYTHONPATH ?= src
RUFF ?= ruff
MYPY ?= $(PYTHON) -m mypy

python-version-check:
	$(PYTHON) scripts/check_python_version.py

install-dev: python-version-check
	$(PYTHON) -m pip install -e ".[dev,httpx]"

test: python-version-check
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m pytest -q

coverage-check: python-version-check
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m pytest --cov=alpha --cov-report=term:skip-covered --cov-report=json:.coverage.json -q
	$(PYTHON) scripts/check_critical_coverage.py .coverage.json

help-check:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m alpha --help >/dev/null

whitespace-check:
	git diff --check

docs-check:
	$(PYTHON) scripts/check_docs.py

scan-secrets:
	$(PYTHON) scripts/check_repo.py scan-secrets

repo-boundary-check:
	$(PYTHON) scripts/check_repo.py repo-boundary

removed-compat-file-check:
	$(PYTHON) scripts/check_repo.py removed-compat-file

compat-import-check:
	$(PYTHON) scripts/check_repo.py compat-import

arch-boundary-check:
	$(PYTHON) scripts/check_repo.py arch-boundary

todo-check:
	$(PYTHON) scripts/check_repo.py todo

sync-config:
	$(PYTHON) scripts/sync_config.py

config-sync-check:
	$(PYTHON) scripts/sync_config.py --check

ruff-check:
	@if $(RUFF) --version >/dev/null 2>&1; then \
		$(RUFF) check .; \
	else \
		echo "[check] ruff executable not installed; install the dev dependencies or Ruff binary" >&2; \
		exit 1; \
	fi

format-check:
	@if $(RUFF) --version >/dev/null 2>&1; then \
		$(RUFF) format --check src tests scripts; \
	else \
		echo "[check] ruff executable not installed; install the dev dependencies or Ruff binary" >&2; \
		exit 1; \
	fi

mypy-check:
	@if PYTHONPATH=$(PYTHONPATH) $(MYPY) --version >/dev/null 2>&1; then \
		PYTHONPATH=$(PYTHONPATH) $(MYPY) src/alpha; \
	else \
		echo "[check] mypy is not installed; install the dev dependencies" >&2; \
		exit 1; \
	fi

check: coverage-check help-check whitespace-check docs-check scan-secrets repo-boundary-check removed-compat-file-check compat-import-check arch-boundary-check todo-check config-sync-check ruff-check format-check mypy-check

clean-runtime:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m alpha clean

clean-dev:
	$(PYTHON) scripts/clean_dev.py

package: sync-config
	$(PYTHON) -m build
