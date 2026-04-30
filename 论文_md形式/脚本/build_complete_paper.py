#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path


DEFAULT_OUTPUT = "脚本/outputs/中间文件/01_完整合并/Decathlon_VOC_Analyzer_Complete_Paper.md"

SECTION_FILES = [
    "title_page.md",
    "00_abstract.md",
    "01_introduction.md",
    "02_background.md",
    "03_related_work.md",
    "04_methodology.md",
    "05_experimental_setup.md",
    "06_experiments.md",
    "07_discussion.md",
    "08_conclusion.md",
    "09_limitations.md",
    "10_acknowledgments.md",
    "appendix.md",
    "11_references.md",
]


def read_section(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"缺少分章文件: {path}")
    return path.read_text(encoding="utf-8").rstrip()


def build_document(section_dir: Path, include_title_page: bool) -> str:
    parts: list[str] = []
    for file_name in SECTION_FILES:
        if file_name == "title_page.md" and not include_title_page:
            continue
        parts.append(read_section(section_dir / file_name))
    return "\n\n".join(parts).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按分章 Markdown 合并生成论文完整稿。")
    parser.add_argument(
        "--section-dir",
        default=None,
        help="分章文件所在目录，默认使用脚本上一级目录。",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help="输出完整稿路径；相对路径默认写入论文_md形式目录。",
    )
    parser.add_argument(
        "--no-title-page",
        action="store_true",
        help="不包含标题页。",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    paper_dir = script_dir.parent

    if args.section_dir is None:
        section_dir = paper_dir
    else:
        section_dir = Path(args.section_dir)
        if not section_dir.is_absolute():
            section_dir = (paper_dir / section_dir).resolve()
        else:
            section_dir = section_dir.resolve()

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = (paper_dir / output_path).resolve()
    else:
        output_path = output_path.resolve()

    try:
        merged = build_document(section_dir, include_title_page=not args.no_title_page)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(merged, encoding="utf-8")

    print(f"完整稿已生成: {output_path}")
    print(f"分章目录: {section_dir}")
    print(f"包含标题页: {not args.no_title_page}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
