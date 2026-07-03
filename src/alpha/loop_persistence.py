"""Compatibility alias for :mod:`alpha.app.loop_persistence`."""

from __future__ import annotations

import sys

from .app import loop_persistence as _module

sys.modules[__name__] = _module
