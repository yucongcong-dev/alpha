"""Validate the Python interpreter used by development commands."""

from __future__ import annotations

import platform
import sys

MIN_VERSION = (3, 10)


def main() -> int:
    if sys.version_info >= MIN_VERSION:
        return 0
    required = ".".join(str(part) for part in MIN_VERSION)
    current = platform.python_version()
    executable = sys.executable
    print(
        f"alpha requires Python {required}+; current interpreter is {current} "
        f"at {executable}. On macOS, install/use python3.10. On Windows, use py -3.10 "
        "or set PYTHON to a Python 3.10+ interpreter.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
