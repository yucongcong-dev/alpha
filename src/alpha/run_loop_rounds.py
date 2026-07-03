"""Compatibility alias for :mod:`alpha.app.run_loop_rounds`."""

from __future__ import annotations

import sys

from .app import run_loop_rounds as _module

sys.modules[__name__] = _module
