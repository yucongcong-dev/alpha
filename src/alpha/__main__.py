"""
Alpha 测试系统命令行入口模块

支持通过 `python -m alpha` 或安装后的 `alpha` 命令运行 Alpha 测试系统。

Usage:
    python -m alpha [OPTIONS]

Example:
    python -m alpha --dataset-id model51 --region USA --universe TOP3000
"""

from __future__ import annotations

import sys


def _python_version_supported() -> bool:
    return sys.version_info >= (3, 10)


def _run_supported_cli() -> int:
    """Import the Python 3.10+ application only after the version guard passes."""
    import coloredlogs

    from .main import run_cli_entry

    coloredlogs.install(
        level="INFO",
        fmt="[%(asctime)s] %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )
    return run_cli_entry()


def main() -> int:
    """Console-script and ``python -m alpha`` entrypoint."""
    if not _python_version_supported():
        print(
            "Alpha requires Python 3.10 or newer; "
            f"current interpreter is {sys.version.split()[0]}.",
            file=sys.stderr,
        )
        return 2
    return _run_supported_cli()


if __name__ == "__main__":
    raise SystemExit(main())
