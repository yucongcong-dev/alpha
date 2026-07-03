.PHONY: test help-check whitespace-check scan-secrets repo-boundary-check compat-import-check arch-boundary-check ruff-check check clean-runtime

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

repo-boundary-check:
	@if find . -maxdepth 1 -type f \( -name 'tmp_*.txt' -o -name 'tmp_*.json' \) | rg -n .; then \
		echo "[check] root tmp_* files are not allowed; move them to tmp/ or data/templates/<dataset>/" >&2; \
		exit 1; \
	fi

compat-import-check:
	@if rg -n "from alpha\.models\.base|from alpha\.(bootstrap|run_loop|finalize|loop_)" tests; then \
		echo "[check] tests should import canonical modules instead of compatibility exports" >&2; \
		exit 1; \
	fi

arch-boundary-check:
	@if rg -n "(from alpha\.app|import alpha\.app|from \.\.app|from \.app)" src/alpha \
		--glob '!app/**' \
		--glob '!bootstrap.py' \
		--glob '!bootstrap_cleanup.py' \
		--glob '!bootstrap_fields.py' \
		--glob '!bootstrap_state.py' \
		--glob '!finalize.py' \
		--glob '!main.py' \
		--glob '!loop_future_support.py' \
		--glob '!loop_persistence.py' \
		--glob '!loop_support.py' \
		--glob '!run_loop.py' \
		--glob '!run_loop_feedback.py' \
		--glob '!run_loop_paths.py' \
		--glob '!run_loop_resume.py' \
		--glob '!run_loop_rounds.py' \
		--glob '!run_loop_state.py'; then \
		echo "[check] lower-level modules must not import alpha.app orchestration modules" >&2; \
		exit 1; \
	fi

ruff-check:
	@if $(PYTHON) -m ruff --version >/dev/null 2>&1; then \
		$(PYTHON) -m ruff check .; \
	else \
		echo "[check] ruff not installed; run: $(PYTHON) -m pip install -r requirements.txt" >&2; \
		exit 1; \
	fi

check: test help-check whitespace-check scan-secrets repo-boundary-check compat-import-check arch-boundary-check ruff-check

clean-runtime:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m alpha clean
