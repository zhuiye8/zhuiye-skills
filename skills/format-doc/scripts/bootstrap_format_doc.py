#!/usr/bin/env python3
"""
Bootstrap three-tier documentation for repositories that have little or no docs.

This script creates/updates:
1. Root ARCHITECTURE.md
2. Folder-level INDEX.md files
3. File-level headers with @input/@output/@position/@doc-sync
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
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

ROLE_KEYWORDS = [
    ("controller", "Controller"),
    ("service", "Service"),
    ("repository", "Repository"),
    ("repo", "Repository"),
    ("dao", "Repository"),
    ("handler", "Handler"),
    ("model", "Model"),
    ("entity", "Model"),
    ("dto", "Model"),
    ("vo", "Model"),
    ("schema", "Schema"),
    ("config", "Config"),
    ("util", "Utility"),
    ("helper", "Utility"),
    ("api", "API"),
    ("view", "UI"),
    ("component", "UI"),
]


@dataclass
class Stats:
    files_scanned: int = 0
    folders_scanned: int = 0
    headers_added: int = 0
    index_created: int = 0
    index_updated: int = 0
    architecture_created: int = 0
    architecture_updated: int = 0
    skipped_existing_index: int = 0
    skipped_existing_architecture: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap format-doc files for a repository.",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root path (default: current directory)",
    )
    parser.add_argument(
        "--language",
        choices=("auto", "zh", "en"),
        default="auto",
        help="Doc language mode (default: auto)",
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
        help="Lines to scan from file start for existing header tags (default: 80)",
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
        "--preserve-existing-index",
        action="store_true",
        help="Do not overwrite existing INDEX.md files",
    )
    parser.add_argument(
        "--preserve-existing-architecture",
        action="store_true",
        help="Do not overwrite existing ARCHITECTURE.md",
    )
    parser.add_argument(
        "--skip-headers",
        action="store_true",
        help="Skip file header bootstrap",
    )
    parser.add_argument(
        "--skip-index",
        action="store_true",
        help="Skip INDEX.md bootstrap",
    )
    parser.add_argument(
        "--skip-architecture",
        action="store_true",
        help="Skip ARCHITECTURE.md bootstrap",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing files",
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


def contains_cjk(text: str) -> bool:
    return re.search(r"[\u4e00-\u9fff]", text) is not None


def detect_language(root: Path, architecture_file: str, index_file: str) -> str:
    candidates = [root / architecture_file]
    for path in root.rglob(index_file):
        candidates.append(path)
        if len(candidates) >= 20:
            break

    for path in candidates:
        if not path.exists() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if contains_cjk(text):
            return "zh"
    return "zh"


def collect_source_files(
    root: Path,
    extensions: set[str],
    ignored_dirs: set[str],
) -> list[Path]:
    source_files: list[Path] = []
    for current_dir, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            name for name in dirnames if name not in ignored_dirs and not name.startswith(".")
        ]
        base = Path(current_dir)
        for filename in filenames:
            path = base / filename
            if path.suffix.lower() in extensions:
                source_files.append(path.resolve())
    return sorted(source_files)


def group_files_by_folder(source_files: list[Path]) -> dict[Path, list[Path]]:
    mapping: dict[Path, list[Path]] = {}
    for path in source_files:
        mapping.setdefault(path.parent, []).append(path)
    for files in mapping.values():
        files.sort(key=lambda x: x.name.lower())
    return mapping


def has_complete_header(content: str, max_header_lines: int) -> bool:
    snippet = "\n".join(content.splitlines()[:max_header_lines]).lower()
    if not all(tag in snippet for tag in REQUIRED_HEADER_TAGS):
        return False
    if not any(tag in snippet for tag in SYNC_TAGS):
        return False
    return True


def infer_role(path: Path) -> str:
    lowered = path.stem.lower()
    for keyword, role in ROLE_KEYWORDS:
        if keyword in lowered:
            return role
    return "Module"


def summarize_items(items: list[str], lang: str, max_items: int = 5) -> str:
    unique = []
    seen = set()
    for item in items:
        token = item.strip()
        if not token:
            continue
        if token in seen:
            continue
        seen.add(token)
        unique.append(token)

    if not unique:
        if lang == "zh":
            return "待补充（请根据实际代码更新）"
        return "To be completed (update from code as needed)."

    if len(unique) > max_items:
        head = ", ".join(unique[:max_items])
        return f"{head}, ..."
    return ", ".join(unique)


def infer_inputs(path: Path, content: str, lang: str) -> str:
    ext = path.suffix.lower()
    items: list[str] = []

    if ext in {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}:
        items.extend(re.findall(r"^\s*import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]", content, re.MULTILINE))
        items.extend(re.findall(r"require\(\s*['\"]([^'\"]+)['\"]\s*\)", content))
    elif ext == ".py":
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("import "):
                clause = stripped[len("import ") :]
                for token in clause.split(","):
                    mod = token.strip().split(" as ")[0].strip()
                    if mod:
                        items.append(mod)
            elif stripped.startswith("from "):
                match = re.match(r"from\s+([A-Za-z0-9_\.]+)\s+import\s+", stripped)
                if match:
                    items.append(match.group(1))
    elif ext == ".go":
        in_block = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("import ("):
                in_block = True
                continue
            if in_block:
                if stripped.startswith(")"):
                    in_block = False
                    continue
                hit = re.search(r"\"([^\"]+)\"", stripped)
                if hit:
                    items.append(hit.group(1))
            elif stripped.startswith("import "):
                hit = re.search(r"\"([^\"]+)\"", stripped)
                if hit:
                    items.append(hit.group(1))
    elif ext == ".java":
        items.extend(re.findall(r"^\s*import\s+([A-Za-z0-9_.*]+)\s*;", content, re.MULTILINE))

    return summarize_items(items, lang)


def infer_outputs(path: Path, content: str, lang: str) -> str:
    ext = path.suffix.lower()
    items: list[str] = []

    if ext in {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}:
        items.extend(
            re.findall(
                r"^\s*export\s+(?:async\s+)?(?:function|class|const|let|var|interface|type|enum)\s+([A-Za-z_][A-Za-z0-9_]*)",
                content,
                re.MULTILINE,
            )
        )
        if re.search(r"^\s*export\s+default\b", content, re.MULTILINE):
            items.append("default export")
        for clause in re.findall(r"^\s*export\s*\{([^}]*)\}", content, re.MULTILINE):
            for token in clause.split(","):
                name = token.strip().split(" as ")[0].strip()
                if name:
                    items.append(name)
    elif ext == ".py":
        all_match = re.search(r"__all__\s*=\s*\[(.*?)\]", content, re.DOTALL)
        if all_match:
            items.extend(re.findall(r"['\"]([A-Za-z0-9_]+)['\"]", all_match.group(1)))
        items.extend(re.findall(r"^def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", content, re.MULTILINE))
        items.extend(re.findall(r"^class\s+([A-Za-z_][A-Za-z0-9_]*)\b", content, re.MULTILINE))
    elif ext == ".go":
        items.extend(re.findall(r"^\s*(?:type|var|const)\s+([A-Z][A-Za-z0-9_]*)\b", content, re.MULTILINE))
        items.extend(re.findall(r"^\s*func\s+([A-Z][A-Za-z0-9_]*)\s*\(", content, re.MULTILINE))
        items.extend(re.findall(r"^\s*func\s+\([^)]*\)\s+([A-Z][A-Za-z0-9_]*)\s*\(", content, re.MULTILINE))
    elif ext == ".java":
        items.extend(
            re.findall(
                r"^\s*public\s+(?:final\s+|abstract\s+)?(?:class|interface|enum|record)\s+([A-Za-z_][A-Za-z0-9_]*)\b",
                content,
                re.MULTILINE,
            )
        )

    if not items:
        items.append(path.stem)

    return summarize_items(items, lang)


def infer_position(path: Path, root: Path, lang: str) -> str:
    role = infer_role(path)
    rel_parent = path.parent.relative_to(root).as_posix()
    if rel_parent == ".":
        rel_parent = "root"
    if lang == "zh":
        return f"位于 {rel_parent}，作为 {role} 层组件。"
    return f"Located in {rel_parent}, serving as a {role} layer component."


def build_header(path: Path, content: str, root: Path, lang: str) -> str:
    inputs = infer_inputs(path, content, lang)
    outputs = infer_outputs(path, content, lang)
    position = infer_position(path, root, lang)
    if lang == "zh":
        sync_note = "文件变更时同步更新本文件头与目录 INDEX.md。"
    else:
        sync_note = "Update this header and folder INDEX.md when this file changes."

    ext = path.suffix.lower()
    if ext == ".py":
        return (
            "\"\"\"\n"
            f"@input {inputs}\n"
            f"@output {outputs}\n"
            f"@position {position}\n"
            f"@doc-sync {sync_note}\n"
            "\"\"\""
        )
    if ext == ".go":
        return (
            f"// @input {inputs}\n"
            f"// @output {outputs}\n"
            f"// @position {position}\n"
            f"// @doc-sync {sync_note}"
        )

    return (
        "/**\n"
        f" * @input {inputs}\n"
        f" * @output {outputs}\n"
        f" * @position {position}\n"
        f" * @doc-sync {sync_note}\n"
        " */"
    )


def insert_header(path: Path, content: str, header: str) -> str:
    if path.suffix.lower() == ".py":
        lines = content.splitlines(keepends=True)
        index = 0
        if lines and lines[0].startswith("#!"):
            index = 1
        if index < len(lines) and re.match(r"#.*coding[:=]\s*[-\w.]+", lines[index]):
            index += 1
        prefix = "".join(lines[:index])
        suffix = "".join(lines[index:])
        spacer = "\n" if (prefix and not prefix.endswith("\n")) else ""
        return f"{prefix}{spacer}{header}\n\n{suffix}"

    return f"{header}\n\n{content}"


def write_if_changed(path: Path, new_content: str, dry_run: bool, verbose: bool) -> str:
    old_content = ""
    existed = path.exists()
    if existed:
        old_content = path.read_text(encoding="utf-8", errors="ignore")

    if old_content == new_content:
        return "unchanged"

    if dry_run:
        action = "update" if existed else "create"
        print(f"DRY-RUN {action}: {path}")
        return action

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new_content, encoding="utf-8")
    if verbose:
        action = "updated" if existed else "created"
        print(f"{action}: {path}")
    return "update" if existed else "create"


def build_folder_summary(folder: Path, file_count: int, root: Path, lang: str) -> str:
    rel = folder.relative_to(root).as_posix()
    if rel == ".":
        rel = "root"
    if lang == "zh":
        return f"该目录包含 {file_count} 个源码文件，负责 {rel} 相关实现。"
    return f"This folder contains {file_count} source files for {rel} related implementation."


def build_file_responsibility(path: Path, role: str, lang: str) -> str:
    name = path.stem
    if lang == "zh":
        return f"{role} 组件，处理 {name} 相关逻辑。"
    return f"{role} component for {name} related logic."


def render_index_file(
    folder: Path,
    files: list[Path],
    root: Path,
    lang: str,
) -> str:
    if folder == root:
        title = "Root"
    else:
        title = folder.name

    summary = build_folder_summary(folder, len(files), root, lang)
    lines = [
        "<!-- FORMAT-DOC: Update when files in this folder change -->",
        "",
        f"# {title}",
        "",
        summary,
        "",
        "## Files",
        "",
        "| File | Role | Responsibilities |",
        "|---|---|---|",
    ]

    for file_path in files:
        role = infer_role(file_path)
        responsibility = build_file_responsibility(file_path, role, lang)
        lines.append(f"| {file_path.name} | {role} | {responsibility} |")

    lines.append("")
    return "\n".join(lines)


def build_architecture_overview(module_count: int, lang: str) -> list[str]:
    if lang == "zh":
        return [
            "本项目采用模块化目录结构，文档作为代码派生结果持续维护。",
            f"当前识别到 {module_count} 个代码目录，每个目录由 INDEX.md 描述文件职责。",
            "跨目录依赖关系请结合源码导入与文件头 @input/@output 字段理解。",
        ]
    return [
        "This project uses a modular folder structure with docs maintained as code-derived artifacts.",
        f"Detected {module_count} code folders, each documented by an INDEX.md file.",
        "Cross-folder dependency flow should be read from imports and @input/@output headers.",
    ]


def build_module_desc(index_path: Path, root: Path, lang: str) -> str:
    rel = index_path.parent.relative_to(root).as_posix()
    if rel == ".":
        rel = "root"
    if lang == "zh":
        return f"{rel} 目录职责。"
    return f"Responsibilities for {rel}."


def render_architecture_file(index_paths: list[Path], root: Path, lang: str) -> str:
    overview = build_architecture_overview(len(index_paths), lang)
    lines = [
        "<!-- FORMAT-DOC: Update when project structure or architecture changes -->",
        "",
        "# Architecture",
        "",
    ]
    lines.extend(overview[:10])
    lines.extend(["", "## Modules", ""])

    if not index_paths:
        if lang == "zh":
            lines.append("- (暂无模块目录)")
        else:
            lines.append("- (no module folders found)")
    else:
        for path in sorted(index_paths, key=lambda p: p.relative_to(root).as_posix()):
            rel_link = path.relative_to(root).as_posix()
            module_name = path.parent.relative_to(root).as_posix()
            if module_name == ".":
                module_name = "root"
            desc = build_module_desc(path, root, lang)
            lines.append(f"- [{module_name}]({rel_link}) - {desc}")

    lines.append("")
    return "\n".join(lines)


def bootstrap_headers(
    source_files: list[Path],
    root: Path,
    lang: str,
    max_header_lines: int,
    dry_run: bool,
    verbose: bool,
    stats: Stats,
) -> None:
    for path in source_files:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            print(f"WARN: failed to read {path}: {exc}")
            continue

        if has_complete_header(content, max_header_lines):
            continue

        header = build_header(path, content, root, lang)
        new_content = insert_header(path, content, header)
        action = write_if_changed(path, new_content, dry_run, verbose)
        if action in {"create", "update"}:
            stats.headers_added += 1


def bootstrap_indexes(
    files_by_folder: dict[Path, list[Path]],
    root: Path,
    index_file_name: str,
    lang: str,
    preserve_existing_index: bool,
    dry_run: bool,
    verbose: bool,
    stats: Stats,
) -> list[Path]:
    index_paths: list[Path] = []
    for folder, files in sorted(files_by_folder.items(), key=lambda item: item[0].as_posix()):
        index_file = folder / index_file_name
        index_paths.append(index_file.resolve())

        if preserve_existing_index and index_file.exists():
            stats.skipped_existing_index += 1
            continue

        content = render_index_file(folder, files, root, lang)
        action = write_if_changed(index_file, content, dry_run, verbose)
        if action == "create":
            stats.index_created += 1
        elif action == "update":
            stats.index_updated += 1

    return index_paths


def bootstrap_architecture(
    root: Path,
    architecture_file_name: str,
    index_paths: list[Path],
    lang: str,
    preserve_existing_architecture: bool,
    dry_run: bool,
    verbose: bool,
    stats: Stats,
) -> None:
    architecture_file = root / architecture_file_name
    if preserve_existing_architecture and architecture_file.exists():
        stats.skipped_existing_architecture += 1
        return

    content = render_architecture_file(index_paths, root, lang)
    action = write_if_changed(architecture_file, content, dry_run, verbose)
    if action == "create":
        stats.architecture_created += 1
    elif action == "update":
        stats.architecture_updated += 1


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()

    if not root.exists() or not root.is_dir():
        print(f"Invalid root path: {root}")
        return 2

    language = args.language
    if language == "auto":
        language = detect_language(root, args.architecture_file, args.index_file)

    extensions = normalize_extensions(args.ext)
    ignored_dirs = set(DEFAULT_IGNORED_DIRS)
    ignored_dirs.update(item.strip() for item in args.ignore_dir if item.strip())

    source_files = collect_source_files(root, extensions, ignored_dirs)
    files_by_folder = group_files_by_folder(source_files)

    stats = Stats()
    stats.files_scanned = len(source_files)
    stats.folders_scanned = len(files_by_folder)

    print(
        f"Bootstrap start: root={root}, language={language}, files={stats.files_scanned}, folders={stats.folders_scanned}"
    )

    if not args.skip_headers:
        bootstrap_headers(
            source_files,
            root,
            language,
            args.max_header_lines,
            args.dry_run,
            args.verbose,
            stats,
        )

    index_paths: list[Path] = []
    if not args.skip_index:
        index_paths = bootstrap_indexes(
            files_by_folder,
            root,
            args.index_file,
            language,
            args.preserve_existing_index,
            args.dry_run,
            args.verbose,
            stats,
        )
    else:
        for folder in files_by_folder:
            index_paths.append((folder / args.index_file).resolve())

    if not args.skip_architecture:
        bootstrap_architecture(
            root,
            args.architecture_file,
            index_paths,
            language,
            args.preserve_existing_architecture,
            args.dry_run,
            args.verbose,
            stats,
        )

    print("Bootstrap summary:")
    print(f"  headers_added={stats.headers_added}")
    print(f"  index_created={stats.index_created}")
    print(f"  index_updated={stats.index_updated}")
    print(f"  architecture_created={stats.architecture_created}")
    print(f"  architecture_updated={stats.architecture_updated}")
    if stats.skipped_existing_index:
        print(f"  skipped_existing_index={stats.skipped_existing_index}")
    if stats.skipped_existing_architecture:
        print(f"  skipped_existing_architecture={stats.skipped_existing_architecture}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
