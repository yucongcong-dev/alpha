"""Compatibility alias for :mod:`alpha.app.bootstrap_fields`."""

from __future__ import annotations

import sys

from .app import bootstrap_fields as _module

sys.modules[__name__] = _module
