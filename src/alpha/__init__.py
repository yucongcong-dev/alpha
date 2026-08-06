"""WorldQuant BRAIN Alpha command-line runner."""

from __future__ import annotations

import sys

if sys.version_info < (3, 10):
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    raise SystemExit(
        "alpha requires Python 3.10+ because the runtime models use dataclass(kw_only=True). "
        f"Current interpreter: {version}. Please switch to Python 3.10 or newer."
    )

__version__ = "1.0.0"
__author__ = "Alpha Generator Team"
