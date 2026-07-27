"""Synchronize canonical workspace YAML files into packaged resources."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "config"
PACKAGED_DIR = ROOT / "src" / "alpha" / "resources" / "config"


def yaml_files(directory: Path) -> dict[str, Path]:
    """Return YAML files keyed by basename."""
    return {path.name: path for path in sorted(directory.glob("*.yaml"))}


def check_sync() -> list[str]:
    """Return every mismatch between canonical and packaged YAML files."""
    source_files = yaml_files(SOURCE_DIR)
    packaged_files = yaml_files(PACKAGED_DIR)
    errors = [
        f"missing packaged config: {name}"
        for name in sorted(source_files.keys() - packaged_files.keys())
    ]
    errors.extend(
        f"unexpected packaged config: {name}"
        for name in sorted(packaged_files.keys() - source_files.keys())
    )
    errors.extend(
        f"packaged config is out of sync: {name}"
        for name in sorted(source_files.keys() & packaged_files.keys())
        if source_files[name].read_bytes() != packaged_files[name].read_bytes()
    )
    return errors


def sync_config() -> int:
    """Replace packaged YAML mirrors with the canonical workspace files."""
    source_files = yaml_files(SOURCE_DIR)
    PACKAGED_DIR.mkdir(parents=True, exist_ok=True)

    for stale_path in yaml_files(PACKAGED_DIR).values():
        if stale_path.name not in source_files:
            stale_path.unlink()
    for source_path in source_files.values():
        shutil.copyfile(source_path, PACKAGED_DIR / source_path.name)

    print(f"[config-sync] synchronized {len(source_files)} YAML files")
    return 0


def main() -> int:
    """Synchronize or validate packaged configuration mirrors."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="validate without writing files")
    args = parser.parse_args()

    if not args.check:
        return sync_config()

    errors = check_sync()
    if errors:
        print("\n".join(errors))
        return 1
    print(f"[config-sync] validated {len(yaml_files(SOURCE_DIR))} YAML files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
