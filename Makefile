.PHONY: install-dev python-version-check test coverage-check help-check whitespace-check docs-check scan-secrets repo-boundary-check removed-compat-file-check compat-import-check arch-boundary-check todo-check sync-config config-sync-check ruff-check format-check mypy-check check clean-runtime clean-dev package

ifeq ($(OS),Windows_NT)
PYTHON ?= py -3.10
else
PYTHON ?= python3.10
endif

python-version-check:
	$(PYTHON) scripts/check_all.py python-version

install-dev: python-version-check
	$(PYTHON) -m pip install -e ".[dev]"

test: python-version-check
	$(PYTHON) scripts/check_all.py test

coverage-check: python-version-check
	$(PYTHON) scripts/check_all.py coverage

help-check:
	$(PYTHON) scripts/check_all.py help

whitespace-check:
	$(PYTHON) scripts/check_all.py whitespace

docs-check:
	$(PYTHON) scripts/check_all.py docs

scan-secrets:
	$(PYTHON) scripts/check_all.py scan-secrets

repo-boundary-check:
	$(PYTHON) scripts/check_all.py repo-boundary

removed-compat-file-check:
	$(PYTHON) scripts/check_all.py removed-compat-file

compat-import-check:
	$(PYTHON) scripts/check_all.py compat-import

arch-boundary-check:
	$(PYTHON) scripts/check_all.py arch-boundary

todo-check:
	$(PYTHON) scripts/check_all.py todo

sync-config:
	$(PYTHON) scripts/sync_config.py

config-sync-check:
	$(PYTHON) scripts/check_all.py config-sync

ruff-check:
	$(PYTHON) scripts/check_all.py ruff

format-check:
	$(PYTHON) scripts/check_all.py format

mypy-check:
	$(PYTHON) scripts/check_all.py mypy

check:
	$(PYTHON) scripts/check_all.py

clean-runtime:
	$(PYTHON) scripts/run_alpha.py clean

clean-dev:
	$(PYTHON) scripts/clean_dev.py

package: sync-config
	$(PYTHON) -m build
