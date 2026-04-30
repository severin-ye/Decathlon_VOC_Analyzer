#!/usr/bin/env python3

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from weasyprint import CSS, HTML

from paper_export_filters import filter_markdown_for_pdf_export


DEFAULT_INPUT = "脚本/outputs/中间文件/01_完整合并/Decathlon_VOC_Analyzer_Complete_Paper.md"
DEFAULT_OUTPUT = "outputs/Decathlon_VOC_Analyzer.pdf"


def build_css() -> str:
    return """
    @page {
        size: A4;
        margin: 20mm 16mm 20mm 16mm;
    }

    body {
        font-family: "Noto Serif CJK SC", "Source Han Serif SC", "Songti SC", "SimSun", serif;
        font-size: 11pt;
        line-height: 1.65;
        color: #111;
    }

    h1, h2, h3, h4 {
        font-family: "Noto Sans CJK SC", "Source Han Sans SC", "Microsoft YaHei", sans-serif;
        color: #111;
        line-height: 1.3;
        page-break-after: avoid;
    }

    h1 {
        font-size: 22pt;
        margin: 0 0 12pt 0;
        text-align: center;
    }

    h2 {
        font-size: 16pt;
        margin-top: 22pt;
        border-bottom: 1px solid #bbb;
        padding-bottom: 4pt;
    }

    h3 {
        font-size: 13pt;
        margin-top: 18pt;
    }

    p, li {
        orphans: 3;
        widows: 3;
    }

    p {
        margin: 0 0 8pt 0;
        text-align: justify;
    }

    ul, ol {
        margin: 0 0 8pt 1.4em;
        padding: 0;
    }

    li {
        margin: 0 0 4pt 0;
    }

    blockquote {
        margin: 10pt 0;
        padding: 0 12pt;
        border-left: 3px solid #bbb;
        color: #444;
    }

    code, pre {
        font-family: "Noto Sans Mono CJK SC", "Source Code Pro", monospace;
        font-size: 9pt;
    }

    pre {
        white-space: pre-wrap;
        word-break: break-word;
        border: 1px solid #ddd;
        padding: 10pt;
        background: #fafafa;
    }

    table {
        width: 100%;
        border-collapse: collapse;
        margin: 12pt 0;
        font-size: 9.5pt;
        table-layout: fixed;
    }

    th, td {
        border: 1px solid #cfcfcf;
        padding: 6pt 7pt;
        vertical-align: top;
        word-wrap: break-word;
    }

    th {
        background: #f3f3f3;
        font-weight: 700;
    }

    img {
        display: block;
        max-width: 100%;
        height: auto;
        margin: 12pt auto;
    }

    hr {
        border: none;
        border-top: 1px solid #ccc;
        margin: 18pt 0;
    }

    a {
        color: #111;
        text-decoration: none;
    }

    .title, .author {
        text-align: center;
    }
    """


def require_command(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(f"未找到必需命令: {name}")
    return path


def run_pandoc(input_path: Path, output_html: Path, resource_base: Path) -> None:
    pandoc = require_command("pandoc")
    markdown_text = input_path.read_text(encoding="utf-8")
    figure_dir = (resource_base / "图片").resolve()
    filtered_text = filter_markdown_for_pdf_export(markdown_text, figure_dir=figure_dir)

    output_html.parent.mkdir(parents=True, exist_ok=True)
    filtered_markdown = output_html.parent / "paper.filtered.md"
    filtered_markdown.write_text(filtered_text, encoding="utf-8")
    cmd = [
        pandoc,
        str(filtered_markdown),
        "--from",
        "markdown+raw_html",
        "--to",
        "html5",
        "--standalone",
        "--embed-resources",
        "--metadata",
        "title=Decathlon VOC Analyzer",
        "--output",
        str(output_html),
    ]
    subprocess.run(cmd, check=True, cwd=resource_base)


def render_pdf(html_path: Path, pdf_path: Path) -> None:
    HTML(filename=str(html_path), base_url=str(html_path.parent)).write_pdf(
        str(pdf_path),
        stylesheets=[CSS(string=build_css())],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="将 Markdown 论文导出为 PDF。")
    parser.add_argument(
        "--input",
        default=DEFAULT_INPUT,
        help="输入 Markdown 文件名或路径，默认使用中间文件/01_完整合并 下的 Decathlon_VOC_Analyzer_Complete_Paper.md",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help="输出 PDF 文件名或路径，默认写入 脚本/outputs/Decathlon_VOC_Analyzer.pdf",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    paper_dir = script_dir.parent
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.is_absolute():
        input_path = (paper_dir / input_path).resolve()
    else:
        input_path = input_path.resolve()

    if not output_path.is_absolute():
        output_path = (script_dir / output_path).resolve()
    else:
        output_path = output_path.resolve()

    resource_base = paper_dir if input_path.parent.name == "01_完整合并" else input_path.parent

    if not input_path.exists():
        print(f"输入文件不存在: {input_path}", file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with tempfile.TemporaryDirectory(prefix="decathlon_voc_pdf_") as temp_dir:
            html_path = Path(temp_dir) / "paper.html"
            run_pandoc(input_path, html_path, resource_base)
            render_pdf(html_path, output_path)
    except Exception as exc:  # noqa: BLE001
        print(f"导出失败: {exc}", file=sys.stderr)
        return 1

    print(f"PDF 已生成: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())