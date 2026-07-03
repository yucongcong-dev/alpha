"""Compatibility alias for :mod:`alpha.app.bootstrap_cleanup`."""

from __future__ import annotations

import sys

from .app import bootstrap_cleanup as _module

sys.modules[__name__] = _module
