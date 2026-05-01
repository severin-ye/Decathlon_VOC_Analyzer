#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path


DEFAULT_OUTPUT = "_脚本/outputs/中间文件/01_完整合并/Decathlon_VOC_Analyzer_Complete_Paper.md"

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

SUMMARY_SECTION_FILES = [
    "title_page.md",
    "00_abstract.md",
    "01_introduction.md",
    "02_system_design_implementation.md",
    "03_conclusion.md",
]

OPTIONAL_SECTION_FILES = {
    "appendix.md",
    "11_references.md",
}


def read_section(file_name: str, search_dirs: list[Path], *, optional: bool = False) -> str | None:
    checked_paths: list[Path] = []
    for section_dir in search_dirs:
        path = section_dir / file_name
        checked_paths.append(path)
        if path.exists():
            return path.read_text(encoding="utf-8").rstrip()
    if optional:
        return None
    checked = "、".join(str(path) for path in checked_paths)
    raise FileNotFoundError(f"缺少分章文件: {file_name}（已检查: {checked}）")


def detect_section_files(section_dir: Path, section_set: str) -> list[str]:
    if section_set == "summary":
        return SUMMARY_SECTION_FILES
    if section_set == "full":
        return SECTION_FILES
    if (section_dir / "02_system_design_implementation.md").exists():
        return SUMMARY_SECTION_FILES
    return SECTION_FILES


def promote_summary_headings(section_text: str) -> str:
    lines = section_text.splitlines()
    promoted_primary = False
    for index, line in enumerate(lines):
        if not promoted_primary and line.startswith("## "):
            lines[index] = f"# {line[3:]}"
            promoted_primary = True
            continue
        if line.startswith("###"):
            lines[index] = line[1:]
    return "\n".join(lines)


def build_document(
    section_dir: Path,
    include_title_page: bool,
    section_set: str,
    fallback_dirs: list[Path],
) -> str:
    parts: list[str] = []
    section_files = detect_section_files(section_dir, section_set)
    is_summary = section_files == SUMMARY_SECTION_FILES
    search_dirs = [section_dir, *fallback_dirs]
    for file_name in section_files:
        if file_name == "title_page.md" and not include_title_page:
            continue
        section = read_section(
            file_name,
            search_dirs,
            optional=file_name in OPTIONAL_SECTION_FILES,
        )
        if section is not None:
            if is_summary and file_name != "title_page.md":
                section = promote_summary_headings(section)
            parts.append(section)
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
    parser.add_argument(
        "--section-set",
        choices=("auto", "full", "summary"),
        default="auto",
        help="章节集合：auto 自动识别，full 使用完整逐章稿，summary 使用缩略稿。",
    )
    parser.add_argument(
        "--fallback-dir",
        action="append",
        default=[],
        help="缺少标题页、附录或参考文献等共享文件时的后备目录；可重复传入。",
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

    fallback_dirs: list[Path] = []
    for fallback_dir_arg in args.fallback_dir:
        fallback_dir = Path(fallback_dir_arg)
        if not fallback_dir.is_absolute():
            fallback_dir = (paper_dir / fallback_dir).resolve()
        else:
            fallback_dir = fallback_dir.resolve()
        fallback_dirs.append(fallback_dir)
    if paper_dir not in fallback_dirs:
        fallback_dirs.append(paper_dir)

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = (paper_dir / output_path).resolve()
    else:
        output_path = output_path.resolve()

    try:
        merged = build_document(
            section_dir,
            include_title_page=not args.no_title_page,
            section_set=args.section_set,
            fallback_dirs=fallback_dirs,
        )
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(merged, encoding="utf-8")

    print(f"完整稿已生成: {output_path}")
    print(f"分章目录: {section_dir}")
    print(f"章节集合: {args.section_set}")
    print(f"后备目录: {', '.join(str(path) for path in fallback_dirs)}")
    print(f"包含标题页: {not args.no_title_page}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
