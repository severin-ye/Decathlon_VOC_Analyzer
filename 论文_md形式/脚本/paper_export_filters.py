#!/usr/bin/env python3

from __future__ import annotations

import re
from pathlib import Path


_PROMPT_BLOCK_START_RE = re.compile(
    r"^\s*AI\s*(?:绘图提示词|drawing\s+prompt)\s*[:：]",
    re.IGNORECASE,
)

_FIG_PLACEHOLDER_ZH_RE = re.compile(r"^\s*\[图\s*(\d+)\s*占位符\s*[:：].*\]\s*$")
_FIG_PLACEHOLDER_EN_RE = re.compile(
    r"^\s*\[Figure\s*(\d+)\s*placeholder\s*:\s*.*\]\s*$",
    re.IGNORECASE,
)


def _resolve_figure_relpath(fig_number: str, figure_dir: Path) -> str | None:
    """Return a markdown-friendly relative path like '图片/图1.png' if exists."""
    candidates: list[str] = []

    # Normalize figure number to handle both Chinese and English formats
    fig_number = fig_number.strip()

    for ext in (".png", ".jpg", ".jpeg", ".webp", ".pdf"):
        candidates.append(f"图{fig_number}{ext}")  # Chinese format
        candidates.append(f"Figure{fig_number}{ext}")  # English format
        candidates.append(f"fig{fig_number}{ext}")
        candidates.append(f"Fig{fig_number}{ext}")

    for name in candidates:
        p = figure_dir / name
        if p.exists():
            return f"{figure_dir.name}/{p.name}"
    return None


def filter_markdown_for_pdf_export(markdown_text: str, *, figure_dir: Path) -> str:
    """Filter markdown for PDF export.

    - Removes AI drawing prompt blocks (keeps them in source markdown).
    - Replaces figure placeholder lines with markdown image links if matching files exist.

    This function is intentionally conservative: it only targets known prompt prefixes and
    placeholder formats used in this repo.
    """

    lines = markdown_text.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    idx = 0

    while idx < len(lines):
        line = lines[idx]

        # 1) Strip drawing prompt blocks.
        if _PROMPT_BLOCK_START_RE.match(line):
            idx += 1
            # If the prompt is wrapped onto multiple lines, drop until a blank line.
            while idx < len(lines) and lines[idx].strip():
                idx += 1
            continue

        # 2) Replace figure placeholders with actual images (if available).
        m_zh = _FIG_PLACEHOLDER_ZH_RE.match(line)
        m_en = _FIG_PLACEHOLDER_EN_RE.match(line)
        match = m_zh or m_en
        if match:
            fig_number = match.group(1)
            relpath = _resolve_figure_relpath(fig_number, figure_dir)
            if relpath is not None:
                out.append(f"![]({relpath})")
                idx += 1
                continue

        out.append(line)
        idx += 1

    # Avoid introducing trailing whitespace changes.
    return "\n".join(out).rstrip() + "\n"
