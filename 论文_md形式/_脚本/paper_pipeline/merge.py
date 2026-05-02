#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .markdown_parser import parse_markdown_manuscript


DEFAULT_OUTPUT = "_脚本/outputs/中间文件/01_完整合并/Decathlon_VOC_Analyzer_Complete_Paper.md"


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
    package_dir = Path(__file__).resolve().parent
    script_dir = package_dir.parent
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
        manuscript = parse_markdown_manuscript(
            section_dir,
            include_title_page=not args.no_title_page,
            section_set=args.section_set,
            fallback_dirs=fallback_dirs,
        )
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(manuscript.render(), encoding="utf-8")

    print(f"完整稿已生成: {output_path}")
    print(f"分章目录: {section_dir}")
    print(f"章节集合: {args.section_set} -> {manuscript.kind}")
    print(f"后备目录: {', '.join(str(path) for path in fallback_dirs)}")
    print(f"包含标题页: {not args.no_title_page}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
