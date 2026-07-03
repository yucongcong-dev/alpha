"""Compatibility alias for :mod:`alpha.app.finalize`."""

from __future__ import annotations

import sys

from .app import finalize as _module

sys.modules[__name__] = _module
