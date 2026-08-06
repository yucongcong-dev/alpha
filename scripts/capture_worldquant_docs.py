#!/usr/bin/env python3
"""Refresh known WorldQuant BRAIN Learn documentation and operators locally."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import tempfile
import time
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

API_ROOT = "https://api.worldquantbrain.com"
PLATFORM_ROOT = "https://platform.worldquantbrain.com"
USER_AGENT = "alpha-doc-snapshot/1.0"
PAGE_ID_PATTERN = re.compile(r"[A-Za-z0-9._-]+")
SNAPSHOT_PREFIXES = ("worldquant_official", "worldquant_operators")


class MarkdownHTMLParser(HTMLParser):
    """Convert the limited HTML used by tutorial TEXT blocks to Markdown."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.links: list[str] = []
        self.list_stack: list[tuple[str, int]] = []
        self.in_pre = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag in {"p", "div"}:
            self._blank_line()
        elif tag == "br":
            self.parts.append("\n")
        elif tag in {"strong", "b"}:
            self.parts.append("**")
        elif tag in {"em", "i"}:
            self.parts.append("*")
        elif tag == "code" and not self.in_pre:
            self.parts.append("`")
        elif tag == "pre":
            self._blank_line()
            self.parts.append("```text\n")
            self.in_pre = True
        elif tag in {"ul", "ol"}:
            self.list_stack.append((tag, 0))
            self.parts.append("\n")
        elif tag == "li":
            list_type, item_number = self.list_stack[-1] if self.list_stack else ("ul", 0)
            item_number += 1
            if self.list_stack:
                self.list_stack[-1] = (list_type, item_number)
            marker = f"{item_number}. " if list_type == "ol" else "- "
            indent = "  " * max(len(self.list_stack) - 1, 0)
            self.parts.append(f"\n{indent}{marker}")
        elif tag == "a":
            self.parts.append("[")
            self.links.append(attributes.get("href") or "")
        elif tag == "img":
            src = attributes.get("src") or ""
            alt = attributes.get("alt") or "image"
            self.parts.append(f"\n\n![{alt}]({src})\n\n")
        elif re.fullmatch(r"h[1-6]", tag):
            self._blank_line()
            self.parts.append("#" * int(tag[1]) + " ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "div"}:
            self._blank_line()
        elif tag in {"strong", "b"}:
            self.parts.append("**")
        elif tag in {"em", "i"}:
            self.parts.append("*")
        elif tag == "code" and not self.in_pre:
            self.parts.append("`")
        elif tag == "pre":
            self.parts.append("\n```\n\n")
            self.in_pre = False
        elif tag in {"ul", "ol"}:
            if self.list_stack:
                self.list_stack.pop()
            self.parts.append("\n")
        elif tag == "a":
            href = self.links.pop() if self.links else ""
            self.parts.append(f"]({href})" if href else "]")
        elif re.fullmatch(r"h[1-6]", tag):
            self._blank_line()

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def _blank_line(self) -> None:
        current = "".join(self.parts)
        if not current.endswith("\n\n"):
            self.parts.append("\n\n" if not current.endswith("\n") else "\n")

    def markdown(self) -> str:
        text = unescape("".join(self.parts))
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def fetch_json(url: str, *, retries: int = 3, backoff_seconds: float = 0.5) -> Any:
    """Fetch JSON with bounded retries for transient network or decoding failures."""
    if retries < 1:
        raise ValueError("retries must be at least 1")

    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urlopen(request, timeout=45) as response:
                return json.load(response)
        except HTTPError:
            raise
        except (OSError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(backoff_seconds * (2**attempt))

    raise RuntimeError(
        f"Failed to fetch valid JSON from {url} after {retries} attempts"
    ) from last_error


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read valid JSON from {path}") from exc


def _mapping(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"{context} must be an object")
    return value


def _list(value: Any, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise RuntimeError(f"{context} must be a list")
    return value


def _required_string(value: dict[str, Any], key: str, context: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result.strip():
        raise RuntimeError(f"{context}.{key} must be a non-empty string")
    return result


def _safe_relative_file(value: Any, context: str, *, suffix: str | None = None) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"{context} must be a non-empty relative file name")
    path = Path(value)
    if path.is_absolute() or len(path.parts) != 1 or path.name != value:
        raise RuntimeError(f"{context} must not contain directory components")
    if suffix is not None and path.suffix != suffix:
        raise RuntimeError(f"{context} must end with {suffix}")
    return value


def validate_catalog_manifest(value: Any, source: Path) -> dict[str, Any]:
    """Validate the page catalog before using any values as paths or identifiers."""
    manifest = _mapping(value, f"catalog manifest {source}")
    pages = _list(manifest.get("pages"), f"catalog manifest {source}.pages")
    tutorials = _list(manifest.get("tutorials"), f"catalog manifest {source}.tutorials")
    seen_ids: set[str] = set()
    seen_files: set[str] = set()
    seen_indexes: set[int] = set()

    for position, raw_page in enumerate(pages, start=1):
        context = f"catalog manifest {source}.pages[{position}]"
        page = _mapping(raw_page, context)
        page_id = _required_string(page, "id", context)
        if PAGE_ID_PATTERN.fullmatch(page_id) is None:
            raise RuntimeError(f"{context}.id contains unsafe characters")
        for key in ("tutorial", "tutorial_title", "title", "url"):
            _required_string(page, key, context)
        file_name = _safe_relative_file(page.get("file"), f"{context}.file", suffix=".md")
        index = page.get("index")
        if not isinstance(index, int) or isinstance(index, bool) or index < 1:
            raise RuntimeError(f"{context}.index must be a positive integer")
        if page_id in seen_ids:
            raise RuntimeError(f"catalog manifest {source} contains duplicate page id {page_id}")
        if file_name in seen_files:
            raise RuntimeError(f"catalog manifest {source} contains duplicate file {file_name}")
        if index in seen_indexes:
            raise RuntimeError(f"catalog manifest {source} contains duplicate index {index}")
        seen_ids.add(page_id)
        seen_files.add(file_name)
        seen_indexes.add(index)

    for position, raw_tutorial in enumerate(tutorials, start=1):
        context = f"catalog manifest {source}.tutorials[{position}]"
        tutorial = _mapping(raw_tutorial, context)
        _required_string(tutorial, "id", context)
        tutorial_pages = _list(tutorial.get("pages"), f"{context}.pages")
        for page_position, raw_page in enumerate(tutorial_pages, start=1):
            tutorial_page = _mapping(raw_page, f"{context}.pages[{page_position}]")
            page_id = _required_string(tutorial_page, "id", f"{context}.pages[{page_position}]")
            if page_id not in seen_ids:
                raise RuntimeError(f"{context} references unknown page id {page_id}")

    return manifest


def validate_page_payload(value: Any, page_id: str) -> dict[str, Any]:
    payload = _mapping(value, f"tutorial page {page_id}")
    content = _list(payload.get("content"), f"tutorial page {page_id}.content")
    for position, block in enumerate(content, start=1):
        _mapping(block, f"tutorial page {page_id}.content[{position}]")
    for key in ("title", "lastModified", "duration"):
        if payload.get(key) is not None and not isinstance(payload[key], str):
            raise RuntimeError(f"tutorial page {page_id}.{key} must be a string or null")
    return payload


def validate_operator_payload(value: Any) -> list[dict[str, Any]]:
    operators = _list(value, "WorldQuant operators response")
    validated: list[dict[str, Any]] = []
    for position, raw_operator in enumerate(operators, start=1):
        context = f"WorldQuant operators response[{position}]"
        operator = dict(_mapping(raw_operator, context))
        for key in ("name", "category"):
            _required_string(operator, key, context)
        for key in ("definition", "description", "level", "documentation"):
            if operator.get(key) is not None and not isinstance(operator[key], str):
                raise RuntimeError(f"{context}.{key} must be a string or null")
        scope = operator.get("scope", [])
        if isinstance(scope, str):
            scope = [scope]
        if not isinstance(scope, list) or any(not isinstance(item, str) for item in scope):
            raise RuntimeError(f"{context}.scope must be a string list")
        operator["scope"] = scope
        validated.append(operator)
    return validated


def compare_catalogs(
    baseline: dict[str, Any],
    catalog: dict[str, Any],
) -> dict[str, list[str]]:
    baseline_ids = {str(page["id"]) for page in baseline["pages"]}
    catalog_ids = {str(page["id"]) for page in catalog["pages"]}
    return {
        "added_page_ids": sorted(catalog_ids - baseline_ids),
        "removed_page_ids": sorted(baseline_ids - catalog_ids),
    }


def html_to_markdown(value: str) -> str:
    parser = MarkdownHTMLParser()
    parser.feed(value)
    parser.close()
    return parser.markdown()


def render_content_block(block: dict[str, Any]) -> str:
    block_type = block.get("type", "UNKNOWN")
    value = block.get("value")

    if block_type == "TEXT" and isinstance(value, str):
        return html_to_markdown(value)

    if block_type == "IMAGE" and isinstance(value, dict):
        lines = ["### Image"]
        lines.extend(
            f"- **{key}**: {value[key]}"
            for key in ("title", "width", "height", "fileSize", "url")
            if key in value
        )
        return "\n".join(lines)

    if block_type == "SIMULATION_EXAMPLE" and isinstance(value, dict):
        lines = ["### Simulation Example"]
        settings = value.get("settings")
        if settings is not None:
            lines.extend(
                [
                    "",
                    "Settings:",
                    "```json",
                    json.dumps(settings, ensure_ascii=False, indent=2),
                    "```",
                ]
            )
        expression = value.get("regular") or value.get("expression")
        if expression:
            lines.extend(["", "Expression:", "```text", str(expression), "```"])
        return "\n".join(lines)

    return "\n".join(
        [
            f"### {str(block_type).replace('_', ' ').title()}",
            "",
            "```json",
            json.dumps(value, ensure_ascii=False, indent=2),
            "```",
        ]
    )


def render_page(
    page: dict[str, Any],
    metadata: dict[str, Any],
    captured: str,
) -> str:
    page_id = page["id"]
    official_url = page["url"]
    api_source = f"{API_ROOT}/tutorial-pages/{page_id}"
    title = metadata.get("title") or page["title"]
    capture_source = metadata.get("_capture_source", "official_api")
    source_label = (
        "WorldQuant BRAIN rendered Learn page via Chrome"
        if capture_source == "rendered_website"
        else "WorldQuant BRAIN Learn Documentation API"
    )

    header_metadata = {
        "id": page_id,
        "tutorial": page["tutorial"],
        "tutorial_title": page["tutorial_title"],
        "title": title,
        "url": official_url,
        "lastModified": metadata.get("lastModified"),
        "duration": metadata.get("duration"),
        "api_source": api_source,
        "capture_source": capture_source,
    }
    blocks = [render_content_block(block) for block in metadata["content"]]
    content = "\n\n".join(block for block in blocks if block)

    return "\n".join(
        [
            f"# {title}",
            "",
            f"Official URL: {official_url}",
            f"API Source: {api_source}",
            f"Captured: {captured}",
            f"Official source: {source_label}",
            f"Capture method: {capture_source}",
            f"Section: {page['tutorial_title']}",
            f"Last modified: {metadata.get('lastModified', 'unknown')}",
            "",
            "## Metadata",
            "```json",
            json.dumps(header_metadata, ensure_ascii=False, indent=2),
            "```",
            "",
            "## Content",
            "",
            content,
            "",
        ]
    )


def capture_documentation(
    baseline_manifest: Path,
    browser_fallback_root: Path,
    output_root: Path,
    captured: str,
    *,
    catalog_manifest: Path | None = None,
) -> Path:
    baseline = validate_catalog_manifest(load_json(baseline_manifest), baseline_manifest)
    catalog_path = catalog_manifest or baseline_manifest
    catalog = validate_catalog_manifest(load_json(catalog_path), catalog_path)
    catalog_diff = compare_catalogs(baseline, catalog)
    output_dir = output_root / f"worldquant_official_{captured}"
    raw_dir = output_dir / "_raw"
    raw_dir.mkdir(parents=True)

    captured_pages: list[dict[str, Any]] = []
    page_metadata: dict[str, dict[str, Any]] = {}
    api_captured_count = 0
    browser_captured_count = 0
    for page in catalog["pages"]:
        page_id = page["id"]
        try:
            payload = validate_page_payload(
                fetch_json(f"{API_ROOT}/tutorial-pages/{page_id}"),
                page_id,
            )
            payload["_capture_source"] = "official_api"
            api_captured_count += 1
        except HTTPError as error:
            fallback_file = browser_fallback_root / f"{page_id}.json"
            if error.code != 404 or not fallback_file.is_file():
                raise RuntimeError(
                    f"Failed to capture {page_id}: HTTP {error.code}; "
                    f"fallback not found at {fallback_file}"
                ) from error
            payload = validate_page_payload(load_json(fallback_file), page_id)
            payload["_capture_source"] = "rendered_website"
            browser_captured_count += 1
        page_metadata[page_id] = payload
        file_name = page["file"]
        raw_file = f"_raw/{page['index']:02d}-{page_id}.json"
        rendered_page = render_page(page, payload, captured)

        write_json(output_dir / raw_file, payload)
        (output_dir / file_name).write_text(rendered_page, encoding="utf-8")

        captured_pages.append(
            {
                **page,
                "title": payload.get("title") or page["title"],
                "lastModified": payload.get("lastModified"),
                "duration": payload.get("duration"),
                "api_source": f"{API_ROOT}/tutorial-pages/{page_id}",
                "raw_file": raw_file,
                "capture_source": payload["_capture_source"],
                "chars": len(rendered_page),
                "blocks": len(payload["content"]),
            }
        )

    tutorials = json.loads(json.dumps(catalog["tutorials"]))
    for tutorial in tutorials:
        for page in tutorial.get("pages", []):
            current = page_metadata.get(page["id"], {})
            page["title"] = current.get("title") or page.get("title")
            page["lastModified"] = current.get("lastModified")
            page["duration"] = current.get("duration")

    manifest = {
        "captured": captured,
        "source": "WorldQuant BRAIN Learn API and rendered official pages",
        "capture_mode": "refresh_known_pages",
        "catalog_source": {
            "kind": "baseline_manifest"
            if catalog_path == baseline_manifest
            else "catalog_manifest",
            "file": catalog_path.name,
        },
        "baseline_count": len(baseline["pages"]),
        "catalog_count": len(catalog["pages"]),
        "captured_count": len(captured_pages),
        "api_captured_count": api_captured_count,
        "browser_captured_count": browser_captured_count,
        **catalog_diff,
        "count": len(captured_pages),
        "tutorials": tutorials,
        "pages": captured_pages,
    }
    write_json(output_dir / "manifest.json", manifest)
    return output_dir


def operator_slug(category: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", category.lower()).strip("-") or "uncategorized"


def _operator_documentation_url(value: Any) -> str:
    documentation = str(value or "")
    if documentation.startswith(("https://", "http://")):
        return documentation
    return f"{PLATFORM_ROOT}{documentation}"


def capture_operators(
    output_root: Path,
    captured: str,
    operators_fallback: Path,
) -> Path:
    capture_source = "official_api"
    source_snapshot: str | None = None
    try:
        operators = validate_operator_payload(fetch_json(f"{API_ROOT}/operators"))
    except HTTPError as error:
        if error.code != 401 or not operators_fallback.is_file():
            raise RuntimeError(
                f"Failed to capture operators: HTTP {error.code}; "
                f"fallback not found at {operators_fallback}"
            ) from error
        operators = validate_operator_payload(load_json(operators_fallback))
        capture_source = "local_snapshot_fallback"
        source_snapshot = str(operators_fallback)

    output_dir = output_root / f"worldquant_operators_{captured}"
    output_dir.mkdir(parents=True)
    write_json(output_dir / "operators.json", operators)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for operator in operators:
        grouped[operator["category"]].append(operator)

    categories: list[dict[str, Any]] = []
    used_files: set[str] = set()
    for category in sorted(grouped):
        items = sorted(grouped[category], key=lambda item: item["name"])
        file_name = f"{operator_slug(category)}.md"
        if file_name in used_files:
            raise RuntimeError(f"Operator categories produce duplicate file name: {file_name}")
        used_files.add(file_name)
        categories.append({"category": category, "count": len(items), "file": file_name})
        lines = [
            f"# {category} Operators",
            "",
            f"Source: {API_ROOT}/operators",
            f"Captured: {captured}",
            "",
        ]
        for item in items:
            lines.extend(
                [
                    f"## `{item['name']}`",
                    "",
                    f"- **Definition**: `{item.get('definition') or ''}`",
                    f"- **Description**: {item.get('description') or ''}",
                    f"- **Level**: {item.get('level') or ''}",
                    f"- **Scope**: {', '.join(item['scope'])}",
                    f"- **Documentation**: {_operator_documentation_url(item.get('documentation'))}",
                    "",
                ]
            )
        (output_dir / file_name).write_text("\n".join(lines), encoding="utf-8")

    readme = [
        "# WorldQuant BRAIN Operators",
        "",
        f"Source: {API_ROOT}/operators",
        f"Captured: {captured}",
        "Official source: WorldQuant BRAIN Operators API",
        f"Capture method: {capture_source}",
        f"Fallback source: {source_snapshot or 'none'}",
        "",
        f"Total operators: {len(operators)}",
        "",
        "## Categories",
        "",
    ]
    readme.extend(
        f"- [{item['category']}]({item['file']}) - {item['count']} operators" for item in categories
    )
    readme.extend(["", "## Operator Index", ""])
    readme.extend(
        (f"- `{operator['name']}` - {operator['category']}; `{operator.get('definition') or ''}`")
        for operator in sorted(operators, key=lambda item: item["name"])
    )
    (output_dir / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    write_json(
        output_dir / "manifest.json",
        {
            "captured": captured,
            "source": f"{API_ROOT}/operators",
            "capture_source": capture_source,
            "source_snapshot": source_snapshot,
            "count": len(operators),
            "categories": categories,
        },
    )
    return output_dir


def parse_capture_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use canonical YYYY-MM-DD format") from exc
    if parsed.isoformat() != value:
        raise argparse.ArgumentTypeError("date must use canonical YYYY-MM-DD format")
    return value


def safe_snapshot_target(output_root: Path, prefix: str, captured: str) -> Path:
    if prefix not in SNAPSHOT_PREFIXES:
        raise ValueError(f"Unsupported snapshot prefix: {prefix}")
    parse_capture_date(captured)
    resolved_root = output_root.resolve()
    target = (resolved_root / f"{prefix}_{captured}").resolve()
    try:
        relative = target.relative_to(resolved_root)
    except ValueError as exc:
        raise RuntimeError(f"Snapshot target escapes output root: {target}") from exc
    if relative == Path("."):
        raise RuntimeError("Snapshot target must be below output root")
    return target


def validate_documentation_snapshot(output_dir: Path) -> None:
    manifest_path = output_dir / "manifest.json"
    manifest = _mapping(load_json(manifest_path), f"snapshot manifest {manifest_path}")
    pages = _list(manifest.get("pages"), f"snapshot manifest {manifest_path}.pages")
    count = manifest.get("count")
    if count != len(pages) or manifest.get("captured_count") != len(pages):
        raise RuntimeError(f"Documentation snapshot count mismatch in {manifest_path}")
    if manifest.get("api_captured_count", 0) + manifest.get(
        "browser_captured_count", 0
    ) != len(pages):
        raise RuntimeError(f"Documentation capture-source count mismatch in {manifest_path}")
    for position, raw_page in enumerate(pages, start=1):
        page = _mapping(raw_page, f"snapshot manifest {manifest_path}.pages[{position}]")
        file_name = _safe_relative_file(
            page.get("file"),
            f"snapshot manifest {manifest_path}.pages[{position}].file",
            suffix=".md",
        )
        raw_file = page.get("raw_file")
        raw_path = Path(raw_file) if isinstance(raw_file, str) else Path()
        if (
            not isinstance(raw_file, str)
            or raw_path.is_absolute()
            or raw_path.parts[:1] != ("_raw",)
            or len(raw_path.parts) != 2
            or raw_path.suffix != ".json"
            or ".." in raw_path.parts
        ):
            raise RuntimeError(f"Invalid raw file path in {manifest_path}: {raw_file}")
        if not (output_dir / file_name).is_file() or not (output_dir / raw_path).is_file():
            raise RuntimeError(f"Documentation snapshot is missing files for {file_name}")


def validate_operator_snapshot(output_dir: Path) -> None:
    manifest_path = output_dir / "manifest.json"
    manifest = _mapping(load_json(manifest_path), f"snapshot manifest {manifest_path}")
    categories = _list(manifest.get("categories"), f"snapshot manifest {manifest_path}.categories")
    operators = validate_operator_payload(load_json(output_dir / "operators.json"))
    if manifest.get("count") != len(operators):
        raise RuntimeError(f"Operator snapshot count mismatch in {manifest_path}")
    if not (output_dir / "README.md").is_file():
        raise RuntimeError(f"Operator snapshot is missing README.md in {output_dir}")
    for position, raw_category in enumerate(categories, start=1):
        category = _mapping(
            raw_category, f"snapshot manifest {manifest_path}.categories[{position}]"
        )
        file_name = _safe_relative_file(
            category.get("file"),
            f"snapshot manifest {manifest_path}.categories[{position}].file",
            suffix=".md",
        )
        if not (output_dir / file_name).is_file():
            raise RuntimeError(f"Operator snapshot is missing category file {file_name}")


def publish_snapshot_pair(
    staged_dirs: list[Path],
    targets: list[Path],
) -> None:
    """Publish both snapshots together and restore old targets if any rename fails."""
    backups: list[tuple[Path, Path]] = []
    published: list[Path] = []
    try:
        for target in targets:
            if target.exists():
                backup = target.parent / f".{target.name}.backup-{uuid4().hex}"
                target.rename(backup)
                backups.append((backup, target))
        for staged_dir, target in zip(staged_dirs, targets, strict=True):
            staged_dir.rename(target)
            published.append(target)
    except Exception:
        for target in reversed(published):
            if target.exists():
                shutil.rmtree(target)
        for backup, target in reversed(backups):
            if backup.exists():
                backup.rename(target)
        raise
    else:
        for backup, _target in backups:
            shutil.rmtree(backup)


def capture_snapshots(
    *,
    baseline_manifest: Path,
    browser_fallback_root: Path,
    operators_fallback: Path,
    catalog_manifest: Path | None,
    output_root: Path,
    captured: str,
    force: bool,
) -> tuple[Path, Path]:
    resolved_root = output_root.resolve()
    resolved_root.mkdir(parents=True, exist_ok=True)
    targets = [
        safe_snapshot_target(resolved_root, prefix, captured) for prefix in SNAPSHOT_PREFIXES
    ]
    existing = [target for target in targets if target.exists()]
    if existing and not force:
        raise RuntimeError(f"Refusing to overwrite existing snapshot: {existing[0]}")

    staging_root = Path(tempfile.mkdtemp(prefix=".capture-worldquant-", dir=resolved_root))
    try:
        docs_dir = capture_documentation(
            baseline_manifest,
            browser_fallback_root,
            staging_root,
            captured,
            catalog_manifest=catalog_manifest,
        )
        operators_dir = capture_operators(staging_root, captured, operators_fallback)
        validate_documentation_snapshot(docs_dir)
        validate_operator_snapshot(operators_dir)
        publish_snapshot_pair([docs_dir, operators_dir], targets)
    finally:
        if staging_root.exists():
            shutil.rmtree(staging_root)
    return targets[0], targets[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=parse_capture_date, default=date.today().isoformat())
    parser.add_argument(
        "--baseline-manifest",
        type=Path,
        default=Path("docs/source_snapshots/worldquant_official_2026-08-06/manifest.json"),
    )
    parser.add_argument(
        "--catalog-manifest",
        type=Path,
        help="Optional current page catalog; defaults to refreshing baseline-known pages only",
    )
    parser.add_argument(
        "--browser-fallback-root",
        type=Path,
        help="Rendered Chrome page payloads used when a tutorial API returns 404",
    )
    parser.add_argument(
        "--operators-fallback",
        type=Path,
        default=Path(
            "docs/source_snapshots/worldquant_operators_2026-08-06/operators.json"
        ),
        help="Known official operator snapshot used only when the current API returns 401",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("docs/source_snapshots"),
    )
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        docs_dir, operators_dir = capture_snapshots(
            baseline_manifest=args.baseline_manifest,
            browser_fallback_root=args.browser_fallback_root
            or args.output_root / f"worldquant_browser_fallback_{args.date}",
            operators_fallback=args.operators_fallback,
            catalog_manifest=args.catalog_manifest,
            output_root=args.output_root,
            captured=args.date,
            force=args.force,
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Documentation snapshot: {docs_dir}")
    print(f"Operators snapshot: {operators_dir}")


if __name__ == "__main__":
    main()
