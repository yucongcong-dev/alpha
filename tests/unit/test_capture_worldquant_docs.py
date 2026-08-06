"""Tests for the WorldQuant documentation snapshot utility."""

from __future__ import annotations

import importlib.util
from io import BytesIO
import json
from pathlib import Path

import pytest


def _load_capture_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "capture_worldquant_docs.py"
    spec = importlib.util.spec_from_file_location("capture_worldquant_docs", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


capture = _load_capture_module()


def _page(page_id: str, index: int) -> dict[str, object]:
    return {
        "id": page_id,
        "tutorial": "tutorial-one",
        "tutorial_title": "Tutorial One",
        "title": page_id.replace("-", " ").title(),
        "url": f"https://platform.example/{page_id}",
        "index": index,
        "file": f"{index:02d}-{page_id}.md",
    }


def _catalog(*page_ids: str) -> dict[str, object]:
    pages = [_page(page_id, index) for index, page_id in enumerate(page_ids, start=1)]
    return {
        "source": "test catalog",
        "tutorials": [
            {
                "id": "tutorial-one",
                "pages": [{"id": page["id"], "title": page["title"]} for page in pages],
            }
        ],
        "pages": pages,
    }


def _write_catalog(path: Path, *page_ids: str) -> Path:
    path.write_text(json.dumps(_catalog(*page_ids)), encoding="utf-8")
    return path


def _fake_fetch(url: str) -> object:
    if url.endswith("/operators"):
        return [
            {
                "name": "rank",
                "category": "Cross Sectional",
                "definition": "rank(x)",
                "description": "Ranks values",
                "level": "ALL",
                "scope": ["REGULAR"],
                "documentation": "/learn/operators/rank",
            }
        ]
    page_id = url.rsplit("/", 1)[-1]
    return {
        "title": f"Live {page_id}",
        "lastModified": "2026-08-06T00:00:00Z",
        "duration": "PT1M",
        "content": [{"type": "TEXT", "value": "<p>Hello</p>"}],
    }


@pytest.mark.parametrize("value", ["2026-8-6", "../2026-08-06", "2026-08-06/../../x"])
def test_parse_capture_date_rejects_non_canonical_or_unsafe_values(value: str) -> None:
    with pytest.raises(Exception, match="YYYY-MM-DD"):
        capture.parse_capture_date(value)


def test_safe_snapshot_target_stays_below_resolved_output_root(tmp_path: Path) -> None:
    target = capture.safe_snapshot_target(tmp_path, "worldquant_official", "2026-08-06")

    assert target.parent == tmp_path.resolve()
    assert target.name == "worldquant_official_2026-08-06"


def test_html_to_markdown_preserves_ordered_and_unordered_lists() -> None:
    markdown = capture.html_to_markdown(
        "<ol><li>First</li><li>Second</li></ol><ul><li>Other</li></ul>"
    )

    assert "1. First" in markdown
    assert "2. Second" in markdown
    assert "- Other" in markdown


def test_fetch_json_retries_transient_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter([OSError("temporary"), BytesIO(b'{"ok": true}')])
    delays: list[float] = []

    def _urlopen(*_args, **_kwargs):
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(capture, "urlopen", _urlopen)
    monkeypatch.setattr(capture.time, "sleep", delays.append)

    assert capture.fetch_json("https://example.invalid", backoff_seconds=0.25) == {"ok": True}
    assert delays == [0.25]


def test_catalog_validation_rejects_missing_fields_and_unsafe_file_names(
    tmp_path: Path,
) -> None:
    missing_pages = {"tutorials": []}
    with pytest.raises(RuntimeError, match="pages must be a list"):
        capture.validate_catalog_manifest(missing_pages, tmp_path / "catalog.json")

    catalog = _catalog("page-one")
    catalog["pages"][0]["file"] = "../outside.md"  # type: ignore[index]
    with pytest.raises(RuntimeError, match="directory components"):
        capture.validate_catalog_manifest(catalog, tmp_path / "catalog.json")


@pytest.mark.parametrize(
    "payload, message",
    [
        ([], "must be an object"),
        ({"content": {}}, "content must be a list"),
        ({"content": ["text"]}, "content\\[1\\] must be an object"),
    ],
)
def test_page_payload_validation_rejects_invalid_schema(payload: object, message: str) -> None:
    with pytest.raises(RuntimeError, match=message):
        capture.validate_page_payload(payload, "page-one")


def test_compare_catalogs_reports_additions_and_removals() -> None:
    difference = capture.compare_catalogs(_catalog("old", "shared"), _catalog("shared", "new"))

    assert difference == {
        "added_page_ids": ["new"],
        "removed_page_ids": ["old"],
    }


def test_non_force_refuses_existing_snapshot_before_fetching(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = _write_catalog(tmp_path / "baseline.json", "page-one")
    existing = tmp_path / "worldquant_official_2026-08-06"
    existing.mkdir()

    def _unexpected_fetch(_url: str) -> object:
        pytest.fail("network fetch must not start when an output target already exists")

    monkeypatch.setattr(capture, "fetch_json", _unexpected_fetch)

    with pytest.raises(RuntimeError, match="Refusing to overwrite"):
        capture.capture_snapshots(
            baseline_manifest=baseline,
            browser_fallback_root=tmp_path / "browser-fallback",
            operators_fallback=tmp_path / "operators-fallback.json",
            catalog_manifest=None,
            output_root=tmp_path,
            captured="2026-08-06",
            force=False,
        )


def test_force_failure_preserves_old_snapshots_and_cleans_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = _write_catalog(tmp_path / "baseline.json", "page-one")
    targets = [
        tmp_path / "worldquant_official_2026-08-06",
        tmp_path / "worldquant_operators_2026-08-06",
    ]
    for target in targets:
        target.mkdir()
        (target / "old.txt").write_text("old", encoding="utf-8")
    monkeypatch.setattr(capture, "fetch_json", _fake_fetch)
    monkeypatch.setattr(
        capture,
        "capture_operators",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("operator failure")),
    )

    with pytest.raises(RuntimeError, match="operator failure"):
        capture.capture_snapshots(
            baseline_manifest=baseline,
            browser_fallback_root=tmp_path / "browser-fallback",
            operators_fallback=tmp_path / "operators-fallback.json",
            catalog_manifest=None,
            output_root=tmp_path,
            captured="2026-08-06",
            force=True,
        )

    assert all((target / "old.txt").read_text(encoding="utf-8") == "old" for target in targets)
    assert not list(tmp_path.glob(".capture-worldquant-*"))


def test_successful_capture_replaces_pair_and_records_honest_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = _write_catalog(tmp_path / "baseline.json", "old-page")
    catalog = _write_catalog(tmp_path / "catalog.json", "new-page")
    targets = [
        tmp_path / "worldquant_official_2026-08-06",
        tmp_path / "worldquant_operators_2026-08-06",
    ]
    for target in targets:
        target.mkdir()
        (target / "old.txt").write_text("old", encoding="utf-8")
    monkeypatch.setattr(capture, "fetch_json", _fake_fetch)

    docs_dir, operators_dir = capture.capture_snapshots(
        baseline_manifest=baseline,
        browser_fallback_root=tmp_path / "browser-fallback",
        operators_fallback=tmp_path / "operators-fallback.json",
        catalog_manifest=catalog,
        output_root=tmp_path,
        captured="2026-08-06",
        force=True,
    )

    manifest = json.loads((docs_dir / "manifest.json").read_text(encoding="utf-8"))
    assert not (docs_dir / "old.txt").exists()
    assert not (operators_dir / "old.txt").exists()
    assert manifest["capture_mode"] == "refresh_known_pages"
    assert manifest["catalog_source"] == {"kind": "catalog_manifest", "file": "catalog.json"}
    assert manifest["added_page_ids"] == ["new-page"]
    assert manifest["removed_page_ids"] == ["old-page"]
    assert manifest["api_captured_count"] == 1
    assert "browser_verified_url" not in manifest
    assert "browser_verified_count" not in manifest
    assert not list(tmp_path.glob(".*.backup-*"))
    assert not list(tmp_path.glob(".capture-worldquant-*"))
