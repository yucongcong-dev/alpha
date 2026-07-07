.PHONY: test help-check whitespace-check scan-secrets repo-boundary-check removed-compat-file-check compat-import-check arch-boundary-check todo-check ruff-check check clean-runtime

PYTHON ?= python3.10
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
		echo "[check] root tmp_* files are not allowed; move them to tmp/ or templates/<dataset>/" >&2; \
		exit 1; \
	fi

removed-compat-file-check:
	@if find src/alpha -maxdepth 1 -type f \( \
		-name 'bootstrap*.py' -o \
		-name 'finalize.py' -o \
		-name 'loop_*.py' -o \
		-name 'run_loop*.py' \
	\) | rg -n .; then \
		echo "[check] root app compatibility files were removed; use src/alpha/app/* directly" >&2; \
		exit 1; \
	fi
	@if find src/alpha/app -maxdepth 1 -type f \( \
		-name 'loop_support.py' -o \
		-name 'run_loop_state.py' \
	\) | rg -n .; then \
		echo "[check] app aggregate compatibility files were removed; import concrete app modules" >&2; \
		exit 1; \
	fi

compat-import-check:
	@if rg -n "from alpha\.models\.base|from alpha\.(bootstrap|run_loop|finalize|loop_)|from alpha\.generators\.settings" tests; then \
		echo "[check] tests should import canonical modules instead of compatibility exports" >&2; \
		exit 1; \
	fi
	@if rg -n "from alpha\.(bootstrap|bootstrap_cleanup|bootstrap_fields|bootstrap_state|finalize|loop_|run_loop)|import alpha\.(bootstrap|bootstrap_cleanup|bootstrap_fields|bootstrap_state|finalize|loop_|run_loop)" src/alpha \
		--glob '!app/**'; then \
		echo "[check] internal code should import alpha.app modules instead of root compatibility exports" >&2; \
		exit 1; \
	fi
	@if rg -n "from \.\.generators\.settings|from \.generators\.settings|from alpha\.generators\.settings|import alpha\.generators\.settings" src/alpha \
		--glob '!generators/settings.py'; then \
		echo "[check] internal code should import generators.payload/fingerprint/variants instead of generators.settings" >&2; \
		exit 1; \
	fi

arch-boundary-check:
	@if rg -n "(from alpha\.app|import alpha\.app|from \.\.app|from \.app)" src/alpha \
		--glob '!app/**' \
		--glob '!main.py' \
		--glob '!__main__.py'; then \
		echo "[check] lower-level modules must not import alpha.app orchestration modules" >&2; \
		exit 1; \
	fi

todo-check:
	@if rg -n "TODO|FIXME|HACK" src tests; then \
		echo "[check] avoid stale TODO/FIXME/HACK comments; document follow-up work explicitly" >&2; \
		exit 1; \
	fi

ruff-check:
	@if $(PYTHON) -m ruff --version >/dev/null 2>&1; then \
		$(PYTHON) -m ruff check .; \
	else \
		echo "[check] ruff not installed; run: $(PYTHON) -m pip install -r requirements.txt" >&2; \
		exit 1; \
	fi

check: test help-check whitespace-check scan-secrets repo-boundary-check removed-compat-file-check compat-import-check arch-boundary-check todo-check ruff-check

clean-runtime:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m alpha clean
