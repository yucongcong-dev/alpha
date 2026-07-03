"""Compatibility alias for :mod:`alpha.app.bootstrap`."""

from __future__ import annotations

import sys

from .app import bootstrap as _module

sys.modules[__name__] = _module
