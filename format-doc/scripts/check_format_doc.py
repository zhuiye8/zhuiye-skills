#!/usr/bin/env python3
"""
Validate three-tier format-doc invariants for a repository.

Checks:
1. Source files contain header tags:
   - @input
   - @output
   - @position
   - @doc-sync or @auto-doc
2. Folders containing source files have INDEX.md that matches real files.
3. ARCHITECTURE.md exists (unless disabled) and INDEX.md links are valid.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

DEFAULT_EXTENSIONS = {
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".py",
    ".go",
    ".java",
}

DEFAULT_IGNORED_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    "node_modules",
    "dist",
    "build",
    "target",
    "coverage",
    "vendor",
    ".next",
    "out",
    "__pycache__",
    ".mvn",
    ".gradle",
}

REQUIRED_HEADER_TAGS = ("@input", "@output", "@position")
SYNC_TAGS = ("@doc-sync", "@auto-doc")
DEFAULT_INDEX_FILE = "INDEX.md"
DEFAULT_ARCHITECTURE_FILE = "ARCHITECTURE.md"


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate documentation format consistency for format-doc.",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root path (default: current directory)",
    )
    parser.add_argument(
        "--mode",
        choices=("all", "changed", "staged"),
        default="all",
        help="File selection mode (default: all)",
    )
    parser.add_argument(
        "--index-file",
        default=DEFAULT_INDEX_FILE,
        help=f"Folder index file name (default: {DEFAULT_INDEX_FILE})",
    )
    parser.add_argument(
        "--architecture-file",
        default=DEFAULT_ARCHITECTURE_FILE,
        help=f"Architecture file name (default: {DEFAULT_ARCHITECTURE_FILE})",
    )
    parser.add_argument(
        "--max-header-lines",
        type=int,
        default=80,
        help="Lines to scan from file start for header tags (default: 80)",
    )
    parser.add_argument(
        "--ext",
        action="append",
        default=[],
        help="Additional source extension like .rb or .php (repeatable)",
    )
    parser.add_argument(
        "--ignore-dir",
        action="append",
        default=[],
        help="Additional directory name to ignore (repeatable)",
    )
    parser.add_argument(
        "--skip-index",
        action="store_true",
        help="Skip INDEX.md checks",
    )
    parser.add_argument(
        "--skip-architecture",
        action="store_true",
        help="Skip ARCHITECTURE.md checks",
    )
    parser.add_argument(
        "--allow-missing-architecture",
        action="store_true",
        help="Allow ARCHITECTURE.md to be missing (only when architecture checks are enabled)",
    )
    parser.add_argument(
        "--strict-architecture-coverage",
        action="store_true",
        help="Require every discovered INDEX.md to be linked from ARCHITECTURE.md",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print additional details",
    )
    return parser.parse_args()


def normalize_extensions(extra_ext: Iterable[str]) -> set[str]:
    extensions = set(DEFAULT_EXTENSIONS)
    for ext in extra_ext:
        item = ext.strip().lower()
        if not item:
            continue
        if not item.startswith("."):
            item = f".{item}"
        extensions.add(item)
    return extensions


def collect_source_files(
    root: Path,
    extensions: set[str],
    ignored_dirs: set[str],
) -> list[Path]:
    source_files: list[Path] = []
    for current_dir, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in ignored_dirs]
        base = Path(current_dir)
        for filename in filenames:
            path = base / filename
            if path.suffix.lower() in extensions:
                source_files.append(path)
    return source_files


def run_git_command(root: Path, args: list[str]) -> list[Path] | None:
    command = ["git", "-C", str(root), *args]
    try:
        output = subprocess.check_output(
            command,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    results: list[Path] = []
    for line in output.splitlines():
        item = line.strip()
        if not item:
            continue
        results.append(root / item)
    return results


def collect_target_files(
    root: Path,
    mode: str,
    extensions: set[str],
    ignored_dirs: set[str],
    report: ValidationReport,
) -> list[Path]:
    if mode == "all":
        return collect_source_files(root, extensions, ignored_dirs)

    if mode == "changed":
        changed = run_git_command(root, ["diff", "--name-only", "--diff-filter=ACMRTUXB", "HEAD"])
        untracked = run_git_command(root, ["ls-files", "--others", "--exclude-standard"])
        if changed is None or untracked is None:
            report.warn("Git unavailable for --mode changed, fallback to --mode all.")
            return collect_source_files(root, extensions, ignored_dirs)
        candidates = [*changed, *untracked]
    else:
        staged = run_git_command(root, ["diff", "--cached", "--name-only", "--diff-filter=ACMRTUXB"])
        if staged is None:
            report.warn("Git unavailable for --mode staged, fallback to --mode all.")
            return collect_source_files(root, extensions, ignored_dirs)
        candidates = staged

    results: list[Path] = []
    for path in candidates:
        if not path.exists():
            continue
        if path.suffix.lower() not in extensions:
            continue
        if any(part in ignored_dirs for part in path.relative_to(root).parts):
            continue
        results.append(path)
    return results


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def validate_file_headers(
    source_files: list[Path],
    max_header_lines: int,
    report: ValidationReport,
) -> None:
    for path in source_files:
        try:
            content = read_text(path)
        except OSError as exc:
            report.error(f"{path}: failed to read file ({exc})")
            continue

        snippet = "\n".join(content.splitlines()[:max_header_lines]).lower()
        missing = [tag for tag in REQUIRED_HEADER_TAGS if tag not in snippet]
        sync_present = any(tag in snippet for tag in SYNC_TAGS)

        if missing or not sync_present:
            missing_fields = ", ".join(missing) if missing else "(none)"
            sync_state = "missing @doc-sync/@auto-doc" if not sync_present else "ok"
            report.error(
                f"{path}: header tags invalid; missing [{missing_fields}], sync-tag [{sync_state}]"
            )


def parse_index_entries(index_file: Path) -> set[str]:
    content = read_text(index_file)
    results: set[str] = set()
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        columns = [part.strip() for part in stripped.strip("|").split("|")]
        if not columns:
            continue
        first = columns[0].strip("` ").strip()
        lower = first.lower()
        if not first:
            continue
        if lower in {"file", "---", "------"}:
            continue
        if set(first) <= {"-", ":"}:
            continue
        results.add(Path(first).name)
    return results


def group_files_by_folder(source_files: list[Path]) -> dict[Path, set[str]]:
    mapping: dict[Path, set[str]] = {}
    for file_path in source_files:
        mapping.setdefault(file_path.parent, set()).add(file_path.name)
    return mapping


def validate_index_files(
    files_by_folder: dict[Path, set[str]],
    index_file_name: str,
    extensions: set[str],
    report: ValidationReport,
) -> set[Path]:
    discovered_index_files: set[Path] = set()
    for folder, expected_files in files_by_folder.items():
        index_file = folder / index_file_name
        if not index_file.exists():
            report.error(f"{index_file}: missing index file for folder with source files")
            continue

        discovered_index_files.add(index_file.resolve())
        try:
            indexed_files = parse_index_entries(index_file)
        except OSError as exc:
            report.error(f"{index_file}: failed to read ({exc})")
            continue

        missing_entries = sorted(expected_files - indexed_files)
        if missing_entries:
            report.error(
                f"{index_file}: missing entries for files: {', '.join(missing_entries)}"
            )

        stale_candidates = {
            name for name in indexed_files if Path(name).suffix.lower() in extensions
        }
        stale_entries = sorted(stale_candidates - expected_files)
        if stale_entries:
            report.error(
                f"{index_file}: stale entries not found in folder: {', '.join(stale_entries)}"
            )

    return discovered_index_files


def find_index_links_in_architecture(architecture_file: Path) -> set[Path]:
    content = read_text(architecture_file)
    links = set()
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", content):
        clean = target.split("#", 1)[0].strip()
        if not clean or "://" in clean:
            continue
        if not clean.endswith("INDEX.md"):
            continue
        links.add((architecture_file.parent / clean).resolve())
    return links


def validate_architecture_file(
    root: Path,
    architecture_file_name: str,
    discovered_index_files: set[Path],
    strict_coverage: bool,
    allow_missing_architecture: bool,
    report: ValidationReport,
) -> None:
    architecture_file = root / architecture_file_name
    if not architecture_file.exists():
        if allow_missing_architecture:
            report.warn(f"{architecture_file}: missing but allowed by flag")
            return
        report.error(f"{architecture_file}: missing architecture file")
        return

    try:
        linked_index_files = find_index_links_in_architecture(architecture_file)
    except OSError as exc:
        report.error(f"{architecture_file}: failed to read ({exc})")
        return

    if discovered_index_files and not linked_index_files:
        report.error(f"{architecture_file}: no INDEX.md links found")
        return

    for linked in sorted(linked_index_files):
        if not linked.exists():
            rel = linked.relative_to(root) if linked.is_relative_to(root) else linked
            report.error(f"{architecture_file}: broken INDEX.md link target: {rel}")

    if strict_coverage:
        missing_links = sorted(discovered_index_files - linked_index_files)
        for path in missing_links:
            rel = path.relative_to(root) if path.is_relative_to(root) else path
            report.error(
                f"{architecture_file}: missing link for discovered index file: {rel}"
            )


def print_report(
    source_files: list[Path],
    files_by_folder: dict[Path, set[str]],
    report: ValidationReport,
    verbose: bool,
) -> None:
    print(
        f"Scanned {len(source_files)} source file(s) across {len(files_by_folder)} folder(s)."
    )

    if verbose and source_files:
        for path in sorted(source_files):
            print(f"  FILE {path}")

    for warning in report.warnings:
        print(f"WARN: {warning}")

    if not report.errors:
        print("OK: format-doc checks passed.")
        return

    print(f"FAIL: {len(report.errors)} issue(s) found.")
    for error in report.errors:
        print(f"ERROR: {error}")


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()

    if not root.exists() or not root.is_dir():
        print(f"Invalid root path: {root}")
        return 2

    extensions = normalize_extensions(args.ext)
    ignored_dirs = set(DEFAULT_IGNORED_DIRS)
    ignored_dirs.update(item.strip() for item in args.ignore_dir if item.strip())

    report = ValidationReport()
    source_files = collect_target_files(root, args.mode, extensions, ignored_dirs, report)
    source_files = sorted({path.resolve() for path in source_files})

    validate_file_headers(source_files, args.max_header_lines, report)
    files_by_folder = group_files_by_folder(source_files)

    discovered_index_files: set[Path] = set()
    if not args.skip_index:
        discovered_index_files = validate_index_files(
            files_by_folder,
            args.index_file,
            extensions,
            report,
        )

    if not args.skip_architecture:
        validate_architecture_file(
            root,
            args.architecture_file,
            discovered_index_files,
            args.strict_architecture_coverage,
            args.allow_missing_architecture,
            report,
        )

    print_report(source_files, files_by_folder, report, args.verbose)
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())

