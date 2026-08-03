"""Run the local alpha package without requiring an editable installation."""

from __future__ import annotations

from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

runpy.run_module("alpha", run_name="__main__")
