"""Compatibility alias for :mod:`alpha.app.loop_future_support`."""

from __future__ import annotations

import sys

from .app import loop_future_support as _module

sys.modules[__name__] = _module
