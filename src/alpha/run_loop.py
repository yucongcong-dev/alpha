"""Compatibility alias for :mod:`alpha.app.run_loop`."""

from __future__ import annotations

import sys

from .app import run_loop as _module

sys.modules[__name__] = _module
