#!/usr/bin/env python3
"""
生成项目知识库文件（project_knowledge.md）。
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "project_knowledge.md"

INCLUDE_EXTENSIONS = {".py", ".vue", ".ts", ".tsx", ".js", ".md", ".json"}
INCLUDE_FILENAMES = {"README.md", "requirements.txt", "package.json"}
EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "dist",
    "build",
    "__pycache__",
    ".idea",
    ".vscode",
    ".pytest_cache",
}
MAX_FILE_CHARS = 1200
MAX_TOTAL_CHARS = 180000


def should_include(path: Path) -> bool:
    if path.name in INCLUDE_FILENAMES:
        return True
    return path.suffix.lower() in INCLUDE_EXTENSIONS


def iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.resolve() == OUTPUT.resolve():
            continue
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if should_include(path):
            yield path


def safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def extract_python_docstring(text: str) -> str:
    try:
        module = ast.parse(text)
    except Exception:
        return ""
    docstring = ast.get_docstring(module) or ""
    return docstring.strip()


def summarize_file(path: Path) -> str:
    relative = path.relative_to(ROOT)
    text = safe_read(path)
    if not text.strip():
        return f"### {relative}\n- 空文件或无法读取\n"

    lines = text.splitlines()
    snippet = "\n".join(lines[:40]).strip()
    if len(snippet) > MAX_FILE_CHARS:
        snippet = snippet[:MAX_FILE_CHARS] + "\n...[截断]"

    summary_lines = [
        f"### {relative}",
        f"- 行数: {len(lines)}",
        f"- 字符数: {len(text)}",
    ]

    if path.suffix == ".py":
        doc = extract_python_docstring(text)
        if doc:
            summary_lines.append(f"- 模块说明: {doc[:240]}")

    summary_lines.extend(
        [
            "- 片段:",
            "```",
            snippet if snippet else "[无可用片段]",
            "```",
            "",
        ]
    )
    return "\n".join(summary_lines)


def build_tree(paths: list[Path]) -> str:
    entries = [str(path.relative_to(ROOT)) for path in paths]
    return "\n".join(f"- {item}" for item in entries)


def main() -> None:
    files = list(iter_files(ROOT))
    sections = [
        "# Bilibili Analytics Project Knowledge",
        "",
        "本文件由 `scripts/generate_kb.py` 自动生成，用于 AI 助手系统提示词注入。",
        "",
        "## 文件清单",
        build_tree(files),
        "",
        "## 文件摘要",
        "",
    ]

    total_chars = sum(len(item) for item in sections)
    for file_path in files:
        section = summarize_file(file_path)
        if total_chars + len(section) > MAX_TOTAL_CHARS:
            sections.append("\n> 知识库已达长度上限，后续文件省略。\n")
            break
        sections.append(section)
        total_chars += len(section)

    OUTPUT.write_text("\n".join(sections), encoding="utf-8")
    print(f"Knowledge base generated: {OUTPUT}")


if __name__ == "__main__":
    main()
