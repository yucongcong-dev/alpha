"""Compatibility alias for :mod:`alpha.app.run_loop_feedback`."""

from __future__ import annotations

import sys

from .app import run_loop_feedback as _module

sys.modules[__name__] = _module
