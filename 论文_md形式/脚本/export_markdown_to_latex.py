#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_INPUT = "Decathlon_VOC_Analyzer_Complete_Paper.md"
DEFAULT_OUTPUT = "outputs/中间文件/02_latex/Decathlon_VOC_Analyzer_Nature_Template.tex"

TOP_HEADING_RE = re.compile(r"^#\s+(.*)$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
IMAGE_RE = re.compile(r"^!\[(.*?)\]\((.*?)\)\s*$")
ITALIC_RE = re.compile(r"^\*(.+)\*\s*$")
META_BOLD_RE = re.compile(r"^\*\*(.+?)\*\*\s*$")
REFERENCE_RE = re.compile(r"^\[(\d+)\]\s+(.*)$")
REFERENCE_NUMBER_ONLY_RE = re.compile(r"^\[(\d+)\]$")
ANCHOR_RE = re.compile(r"^<a\s+id=.*?></a>\s*$")
ANCHOR_ID_RE = re.compile(r"^<a\s+id=(?:\"([^\"]+)\"|'([^']+)')\s*></a>\s*$")
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*(?:\s*:?-{3,}:?\s*)?\|?\s*$")
SUP_RE = re.compile(r"<sup>(.*?)</sup>", re.IGNORECASE)
SUP_PLACEHOLDER_RE = re.compile(r"CURAVIEWSUPSTART(.*?)CURAVIEWSUPEND")
HEADING_NUMBER_PREFIX_RE = re.compile(r"^\s*\d+(?:\.\d+)*[.)]?\s+")
SUBHEADING_NUMBER_PREFIX_RE = re.compile(r"^(#{2,6})\s+\d+(?:\.\d+)*[.)]?\s+(.*)$")
NUMERIC_CITATION_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")

ABSTRACT_HEADINGS = {"摘要", "abstract"}
INTRODUCTION_HEADINGS = {"引言", "introduction"}
REFERENCE_HEADINGS = {"参考文献", "references"}


@dataclass
class Section:
    heading: str
    body: str


@dataclass
class AuthorBlock:
    lines: list[str]


def load_citation_key_map(mapping_path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    pattern = re.compile(r"^\|\s*\[(\d+)\]\s*\|\s*`([^`]+)`\s*\|")

    for raw_line in mapping_path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(raw_line.strip())
        if match:
            mapping[match.group(1)] = match.group(2)
    return mapping


def replace_numeric_citations(markdown_text: str, citation_key_map: dict[str, str]) -> str:
    if not citation_key_map:
        return markdown_text

    def replacer(match: re.Match[str]) -> str:
        numbers = [item.strip() for item in match.group(1).split(",")]
        keys: list[str] = []
        for number in numbers:
            key = citation_key_map.get(number)
            if key is None:
                return match.group(0)
            keys.append(key)
        return rf"\citep{{{','.join(keys)}}}"

    converted_lines: list[str] = []
    for line in markdown_text.splitlines():
        stripped = line.strip()
        if REFERENCE_RE.match(stripped) or REFERENCE_NUMBER_ONLY_RE.match(stripped):
            converted_lines.append(line)
            continue
        converted_lines.append(NUMERIC_CITATION_RE.sub(replacer, line))
    return "\n".join(converted_lines)


def escape_latex(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "{": r"\{",
        "}": r"\}",
        "#": r"\#",
        "$": r"\$",
        "%": r"\%",
        "&": r"\&",
        "_": r"\_",
    }
    return "".join(replacements.get(char, char) for char in text)


def run_pandoc(markdown_text: str) -> str:
    try:
        result = subprocess.run(
            [
                "pandoc",
                "--from",
                "markdown+raw_html+raw_tex",
                "--to",
                "latex",
                "--no-highlight",
                "--wrap=none",
            ],
            input=markdown_text,
            text=True,
            capture_output=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("未找到 pandoc，请先安装 pandoc。") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        raise RuntimeError(f"pandoc 转换失败: {stderr}") from exc
    return result.stdout.strip()


def strip_caption_prefix(caption: str) -> str:
    cleaned = caption.strip()
    cleaned = re.sub(r"^\s*(?:图|表)\s*\d+(?:\.\d+)?\s*[\.:：]\s*", "", cleaned)
    cleaned = re.sub(r"^\s*(?:Figure|Fig\.)\s*\d+(?:\.\d+)?\s*[\.:：]\s*", "", cleaned)
    cleaned = re.sub(r"^\s*Table\s*\d+(?:\.\d+)?\s*[\.:：]\s*", "", cleaned)
    return cleaned.strip()


def strip_heading_number_prefix(heading: str) -> str:
    return HEADING_NUMBER_PREFIX_RE.sub("", heading.strip()).strip()


def normalize_section_heading(heading: str) -> str:
    return strip_heading_number_prefix(heading).strip().lower()


def strip_numbered_subheadings_for_export(markdown_text: str) -> str:
    out_lines: list[str] = []
    for line in markdown_text.splitlines():
        match = SUBHEADING_NUMBER_PREFIX_RE.match(line)
        if match:
            out_lines.append(f"{match.group(1)} {match.group(2)}")
        else:
            out_lines.append(line)
    return "\n".join(out_lines)


def normalize_caption(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def preprocess_markdown(text: str) -> str:
    text = text.replace("\r\n", "\n")
    text = text.replace("⭐", "（最佳）")
    text = text.replace("ρ", "$\\rho$")
    text = SUP_RE.sub(
        lambda match: f"CURAVIEWSUPSTART{match.group(1).strip()}CURAVIEWSUPEND",
        text,
    )
    return text


def restore_superscripts(latex_text: str) -> str:
    return SUP_PLACEHOLDER_RE.sub(
        lambda match: rf"\textsuperscript{{{match.group(1)}}}",
        latex_text,
    )


def strip_pandoc_heading_anchors(latex_text: str) -> str:
    pattern = re.compile(
        r"\\hypertarget\{[^}]+\}\{%\s*\\(subsection\*?|subsubsection\*?|paragraph\*?|subparagraph\*?)\{([^}]*)\}\\label\{[^}]+\}\}",
        re.S,
    )
    return pattern.sub(lambda match: rf"\{match.group(1)}{{{match.group(2)}}}", latex_text)


def _is_horizontal_rule(line: str) -> bool:
    stripped = line.strip()
    return stripped in {"---", "***", "___"}


def _looks_like_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.count("|") >= 2


def normalize_markdown_table_captions(markdown_text: str) -> str:
    lines = markdown_text.splitlines()
    output: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]

        if (
            _looks_like_table_row(line)
            and index + 1 < len(lines)
            and TABLE_SEPARATOR_RE.match(lines[index + 1].strip())
        ):
            table_lines = [line, lines[index + 1]]
            index += 2

            while index < len(lines) and _looks_like_table_row(lines[index]):
                table_lines.append(lines[index])
                index += 1

            lookahead = index
            skipped_blanks: list[str] = []
            while lookahead < len(lines) and not lines[lookahead].strip():
                skipped_blanks.append(lines[lookahead])
                lookahead += 1

            caption_line = None
            if lookahead < len(lines):
                italic_match = ITALIC_RE.match(lines[lookahead].strip())
                if italic_match:
                    caption_candidate = italic_match.group(1).strip()
                    stripped_caption = strip_caption_prefix(caption_candidate)
                    if stripped_caption != caption_candidate or caption_candidate.startswith(("Table", "表")):
                        caption_line = f": {stripped_caption}"

            output.extend(table_lines)
            if caption_line is not None:
                output.append(caption_line)
                index = lookahead + 1
            else:
                output.extend(skipped_blanks)
            continue

        output.append(line)
        index += 1

    return "\n".join(output)


def parse_author_blocks(lines: list[str]) -> list[AuthorBlock]:
    blocks: list[AuthorBlock] = []
    current: list[str] = []

    for raw in lines:
        line = raw.strip()
        if not line or _is_horizontal_rule(line):
            if current:
                blocks.append(AuthorBlock(current))
                current = []
            continue
        current.append(line)

    if current:
        blocks.append(AuthorBlock(current))

    # 过滤掉明显不是作者块的情况（比如仍旧是旧的 **author** 元信息）
    blocks = [b for b in blocks if len(b.lines) >= 3]
    return blocks


def parse_metadata(lines: list[str]) -> tuple[str, str, str, str, list[AuthorBlock], int]:
    title = ""
    author = ""
    affiliation = ""
    email = ""

    index = 0
    while index < len(lines):
        line = lines[index].strip()
        title_match = TOP_HEADING_RE.match(line)
        if title_match:
            title = title_match.group(1).strip()
            index += 1
            break
        index += 1

    # 元信息区域：标题行之后，到下一段顶层标题（例如 # 摘要）之前
    meta_start = index
    meta_end = meta_start
    while meta_end < len(lines):
        if TOP_HEADING_RE.match(lines[meta_end].strip()):
            break
        meta_end += 1

    meta_region = [line.strip() for line in lines[meta_start:meta_end]]

    metadata_values: list[str] = []
    for line in meta_region:
        bold_match = META_BOLD_RE.match(line)
        if bold_match:
            metadata_values.append(bold_match.group(1).strip())

    if metadata_values:
        author = metadata_values[0]
    if len(metadata_values) > 1:
        affiliation = metadata_values[1]
    if len(metadata_values) > 2:
        email = metadata_values[2]

    # 新格式：在标题与下一段 # Heading 之间，按空行分组的多作者块
    author_blocks: list[AuthorBlock] = []
    if not metadata_values:
        author_blocks = parse_author_blocks(meta_region)

    # 后续章节解析应从下一段顶层标题开始
    return title, author, affiliation, email, author_blocks, meta_end


def build_author_block_latex(block: AuthorBlock) -> str:
    raw_lines = [x.strip() for x in block.lines if x.strip()]
    if not raw_lines:
        return ""

    formatted: list[str] = []
    for idx, value in enumerate(raw_lines):
        escaped = escape_latex(value)

        # 视觉层级：
        # - 第 1 行：姓名（加粗）
        # - 第 2/3 行：院系/学校（斜体）
        if idx == 0:
            formatted.append(rf"\textbf{{{escaped}}}")
            continue
        if idx in {1, 2}:
            formatted.append(rf"\textit{{{escaped}}}")
            continue

        # 约定：邮箱行包含 @，导出时用 \texttt{...}
        if "@" in value:
            # 在等宽字体里给长邮箱加断行点，避免顶出边界
            # - @ 前允许断行
            # - . 后允许断行
            # - _ 后允许断行（注意 _ 会被 escape 成 \\_）
            email = escaped
            email = email.replace("@", "\\allowbreak@")
            email = email.replace(".", ".\\allowbreak{}")
            email = email.replace("\\_", "\\_\\allowbreak{}")
            formatted.append(rf"{{\ttfamily\small {email}}}")
        else:
            formatted.append(escaped)

    return r" \\ ".join(formatted)


def build_author_tabular_latex(author_blocks: list[AuthorBlock], max_cols: int = 4) -> str:
    blocks = [b for b in author_blocks if b.lines]
    if not blocks:
        return "First Author"

    if len(blocks) == 1:
        cols = 1
    else:
        cols = min(max_cols, max(1, len(blocks) - 1))

    # 第一行保留给第一作者，其他作者从第二行开始排，满足当前论文署名布局需求。
    first_row_width = min(0.62, 0.88)
    col_width = 0.88 / cols
    first_row_width_latex = f"{first_row_width:.4f}\\textwidth"
    col_width_latex = f"{col_width:.4f}\\textwidth"

    rows: list[str] = []

    if len(blocks) == 1:
        first_cell = build_author_block_latex(blocks[0])
        rows.append(rf"\multicolumn{{1}}{{c}}{{\parbox[t]{{{first_row_width_latex}}}{{\centering {first_cell}}}}} \\")
    else:
        first_cell = build_author_block_latex(blocks[0])
        rows.append(rf"\multicolumn{{{cols}}}{{c}}{{\parbox[t]{{{first_row_width_latex}}}{{\centering {first_cell}}}}} \\")
        rows.append(rf"\multicolumn{{{cols}}}{{c}}{{}} \\")

    remaining_blocks = blocks[1:] if len(blocks) > 1 else []
    for start in range(0, len(remaining_blocks), cols):
        chunk = remaining_blocks[start : start + cols]
        cells: list[str] = []
        for block in chunk:
            cell_body = build_author_block_latex(block)
            cells.append(rf"\parbox[t]{{{col_width_latex}}}{{\centering {cell_body}}}")
        # 不足列数的行补空 cell，保持表格对齐
        while len(cells) < cols:
            cells.append(rf"\parbox[t]{{{col_width_latex}}}{{}}")
        rows.append(" & ".join(cells) + r" \\")

    col_spec = "@{}" + "c" * cols + "@{}"
    # 用 \small 让四列在页面上更协调，避免拥挤
    return "\n".join(
        [
            r"{\small",
            rf"\begin{{tabular}}{{{col_spec}}}",
            *rows,
            r"\end{tabular}",
            r"}",
        ]
    )


def parse_sections(lines: list[str], start_index: int) -> list[Section]:
    sections: list[Section] = []
    current_heading: str | None = None
    current_body: list[str] = []

    for raw_line in lines[start_index:]:
        line = raw_line.rstrip("\n")
        heading_match = TOP_HEADING_RE.match(line.strip())
        if heading_match:
            if current_heading is not None:
                sections.append(Section(current_heading, "\n".join(current_body).strip()))
            current_heading = heading_match.group(1).strip()
            current_body = []
            continue
        if current_heading is not None:
            current_body.append(line)

    if current_heading is not None:
        sections.append(Section(current_heading, "\n".join(current_body).strip()))
    return sections


def resolve_figure_path(raw_path: str, resource_base: Path) -> str:
    figure_path = Path(raw_path)
    if not figure_path.is_absolute():
        figure_path = (resource_base / figure_path).resolve()
    else:
        figure_path = figure_path.resolve()
    return figure_path.as_posix()


def build_inline_figure_latex(caption: str, path: str) -> str:
    lines = [r"\begin{figure}[H]", r"\centering"]
    lines.append(rf"\includegraphics[width=0.92\textwidth]{{{escape_latex(path)}}}")
    if caption:
        lines.append(rf"\caption{{{escape_latex(caption)}}}")
    lines.append(r"\end{figure}")
    return "\n".join(lines)


def build_inline_figure_latex_with_label(caption: str, path: str, label: str | None) -> str:
    lines = [r"\begin{figure}[H]", r"\centering"]
    lines.append(rf"\includegraphics[width=0.92\textwidth]{{{escape_latex(path)}}}")
    if caption:
        lines.append(rf"\caption{{{escape_latex(caption)}}}")
    if label:
        lines.append(rf"\label{{{escape_latex(label)}}}")
    lines.append(r"\end{figure}")
    return "\n".join(lines)


def inline_figures(markdown_text: str, resource_base: Path) -> str:
    output_lines: list[str] = []
    lines = markdown_text.splitlines()
    index = 0
    pending_label: str | None = None

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        anchor_id_match = ANCHOR_ID_RE.match(stripped)
        if anchor_id_match:
            pending_label = anchor_id_match.group(1) or anchor_id_match.group(2)
            index += 1
            continue
        if ANCHOR_RE.match(stripped):
            pending_label = None
            index += 1
            continue

        image_match = IMAGE_RE.match(stripped)
        if image_match:
            caption = strip_caption_prefix(image_match.group(1).strip())
            path = resolve_figure_path(image_match.group(2).strip(), resource_base)

            next_index = index + 1
            italic_caption = ""
            while next_index < len(lines) and not lines[next_index].strip():
                next_index += 1
            if next_index < len(lines):
                italic_match = ITALIC_RE.match(lines[next_index].strip())
                if italic_match:
                    italic_caption = italic_match.group(1).strip()
                    if not caption:
                        caption = italic_caption
                    index = next_index + 1
                else:
                    index += 1
            else:
                index += 1

            if italic_caption:
                stripped_italic = strip_caption_prefix(italic_caption)
                if not caption:
                    caption = stripped_italic
                elif normalize_caption(stripped_italic) != normalize_caption(caption):
                    caption = stripped_italic

            caption = strip_caption_prefix(caption)

            output_lines.append("")
            output_lines.append(build_inline_figure_latex_with_label(caption, path, pending_label))
            output_lines.append("")
            pending_label = None
            continue

        output_lines.append(line)
        index += 1

    return "\n".join(output_lines).strip()


def convert_body(markdown_text: str, resource_base: Path, citation_key_map: dict[str, str] | None = None) -> str:
    cleaned = preprocess_markdown(
        normalize_markdown_table_captions(
            strip_numbered_subheadings_for_export(
                replace_numeric_citations(
                    inline_figures(markdown_text, resource_base),
                    citation_key_map or {},
                )
            )
        )
    ).strip()
    if not cleaned:
        return ""
    latex = run_pandoc(cleaned)
    latex = strip_pandoc_heading_anchors(latex)
    latex = restore_superscripts(latex)
    return latex


def parse_references(reference_text: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    current_number: str | None = None
    current_lines: list[str] = []

    for raw_line in reference_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("# ") and normalize_section_heading(line[2:]) in REFERENCE_HEADINGS:
            continue

        match = REFERENCE_RE.match(line)
        if match:
            if current_number is not None:
                entries.append((current_number, " ".join(current_lines).strip()))
            current_number = match.group(1)
            current_lines = [match.group(2).strip()]
        elif current_number is not None:
            current_lines.append(line)

    if current_number is not None:
        entries.append((current_number, " ".join(current_lines).strip()))
    return entries


def build_bibliography(reference_text: str) -> str:
    items: list[str] = []
    for number, entry in parse_references(reference_text):
        entry_latex = run_pandoc(preprocess_markdown(entry))
        items.append(f"\\bibitem{{ref{number}}}\n{entry_latex}\n")
    return "\n".join(items).strip()


def build_section_block(
    section: Section,
    resource_base: Path,
    citation_key_map: dict[str, str] | None = None,
) -> str:
    latex_body = convert_body(section.body, resource_base, citation_key_map)

    heading_clean = strip_heading_number_prefix(section.heading)
    heading_key = normalize_section_heading(section.heading)

    if heading_key in ABSTRACT_HEADINGS:
        block = "\n".join(
            [
                "% =========================",
                "% Abstract",
                "% =========================",
                r"\begin{abstract}",
                latex_body,
                r"\end{abstract}",
            ]
        )
        return block

    if heading_key in INTRODUCTION_HEADINGS:
        block = "\n".join(
            [
                "% =========================",
                "% Introduction",
                "% =========================",
                rf"\section{{{escape_latex(heading_clean)}}}",
                latex_body,
            ]
        )
        return block

    block = "\n".join(
        [
            "% =========================",
            f"% {heading_clean}",
            "% =========================",
            rf"\section{{{escape_latex(heading_clean)}}}",
            latex_body,
        ]
    )
    return block


def build_document(
    title: str,
    author: str,
    affiliation: str,
    email: str,
    author_blocks: list[AuthorBlock],
    sections: list[Section],
    reference_text: str,
    resource_base: Path,
    bib_name: str | None = None,
    citation_key_map: dict[str, str] | None = None,
) -> str:
    section_blocks: list[str] = []
    resolved_reference_text = reference_text.strip()

    for section in sections:
        if normalize_section_heading(section.heading) in REFERENCE_HEADINGS:
            if not resolved_reference_text:
                resolved_reference_text = section.body.strip()
            continue
        block = build_section_block(section, resource_base, citation_key_map)
        section_blocks.append(block)

    bibliography = build_bibliography(resolved_reference_text) if not bib_name else ""

    title_line = title or "Your concise article title here"

    # 作者排版：
    # - 若检测到多作者块：用 tabular 强制同一行多列（避免 \and 自动换布局）
    # - 否则保持旧逻辑：单作者三行
    if author_blocks:
        author_latex = build_author_tabular_latex(author_blocks, max_cols=4)
    else:
        author_line = author or "First Author"
        affiliation_line = affiliation or "Department / Institution / City / Country"
        email_line = email or "author@email.com"
        author_latex = " \\ ".join(
            [
                escape_latex(author_line),
                rf"\textit{{{escape_latex(affiliation_line)}}}",
                escape_latex(email_line),
            ]
        )

    parts = [
        r"\documentclass[11pt]{article}",
        "",
        "% ===== 基本宏包：尽量保持简单 =====",
        r"\usepackage[margin=1in]{geometry}",
        r"\usepackage{graphicx}",
        r"\usepackage{float}",
        r"\usepackage{chngcntr}",
        r"\usepackage{booktabs}",
        r"\usepackage{multirow}",
        r"\usepackage{longtable}",
        r"\usepackage{array}",
        r"\usepackage{calc}",
        r"\usepackage{amsmath, amssymb}",
        r"\setlength{\LTcapwidth}{\textwidth}",
        r"\usepackage{xurl}",
        r"\usepackage{hyperref}",
        r"\usepackage[numbers,sort&compress]{natbib}",
        r"\usepackage{setspace}",
        r"\usepackage{fontspec}",
        r"\usepackage{xeCJK}",
        r"\providecommand{\tightlist}{\setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}",
        "",
        "% ===== 图表编号风格：全文连续编号，使用 Figure / Table =====",
        r"\renewcommand{\figurename}{Figure}",
        r"\renewcommand{\tablename}{Table}",
        "",
        "% ===== 字体与换行策略 =====",
        r"\defaultfontfeatures{Ligatures=TeX,Scale=MatchLowercase}",
        r"\IfFontExistsTF{Noto Serif}{\setmainfont{Noto Serif}}{\IfFontExistsTF{DejaVu Serif}{\setmainfont{DejaVu Serif}}{\setmainfont{Latin Modern Roman}}}",
        r"\IfFontExistsTF{Noto Sans}{\setsansfont{Noto Sans}}{\IfFontExistsTF{DejaVu Sans}{\setsansfont{DejaVu Sans}}{\setsansfont{Latin Modern Sans}}}",
        r"\IfFontExistsTF{Noto Sans Mono}{\setmonofont{Noto Sans Mono}}{\IfFontExistsTF{DejaVu Sans Mono}{\setmonofont{DejaVu Sans Mono}}{\setmonofont{Latin Modern Mono}}}",
        r"\IfFontExistsTF{Noto Serif CJK SC}{\setCJKmainfont[AutoFakeBold=3,AutoFakeSlant=.2]{Noto Serif CJK SC}}{\IfFontExistsTF{Source Han Serif SC}{\setCJKmainfont[AutoFakeBold=3,AutoFakeSlant=.2]{Source Han Serif SC}}{\IfFontExistsTF{AR PL UMing CN}{\setCJKmainfont[AutoFakeBold=3,AutoFakeSlant=.2]{AR PL UMing CN}}{\setCJKmainfont[AutoFakeBold=3,AutoFakeSlant=.2]{WenQuanYi Zen Hei}}}}",
        r"\IfFontExistsTF{Noto Sans CJK SC}{\setCJKsansfont[AutoFakeBold=3,AutoFakeSlant=.2]{Noto Sans CJK SC}}{\IfFontExistsTF{Source Han Sans SC}{\setCJKsansfont[AutoFakeBold=3,AutoFakeSlant=.2]{Source Han Sans SC}}{\IfFontExistsTF{Droid Sans Fallback}{\setCJKsansfont[AutoFakeBold=3,AutoFakeSlant=.2]{Droid Sans Fallback}}{\setCJKsansfont[AutoFakeBold=3,AutoFakeSlant=.2]{AR PL UMing CN}}}}",
        r"\IfFontExistsTF{Noto Sans Mono CJK SC}{\setCJKmonofont[AutoFakeBold=3]{Noto Sans Mono CJK SC}}{\IfFontExistsTF{Droid Sans Fallback}{\setCJKmonofont[AutoFakeBold=3]{Droid Sans Fallback}}{\setCJKmonofont[AutoFakeBold=3]{AR PL UMing CN}}}",
        r"\setlength{\emergencystretch}{6em}",
        r"\sloppy",
        "",
        "% 可选：让行距略宽一些，便于审稿阅读",
        r"\onehalfspacing",
        "",
        rf"\title{{\textbf{{{escape_latex(title_line)}}}}}",
        "",
        rf"\author{{{author_latex}}}",
        "",
        r"\date{} % Nature 系列投稿一般不需要显示日期",
        "",
        r"\begin{document}",
        r"\maketitle",
        "",
        "\n\n".join(section_blocks),
        "",
        "% =========================",
        "% References",
        "% =========================",
    ]

    if bib_name:
        parts.extend(
            [
                r"\bibliographystyle{unsrtnat}",
                rf"\bibliography{{{escape_latex(bib_name)}}}",
            ]
        )
    else:
        parts.extend(
            [
                r"\begin{thebibliography}{99}",
                r"\raggedright",
                bibliography,
                r"\end{thebibliography}",
            ]
        )

    parts.extend(["", r"\end{document}", ""])
    return "\n".join(parts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="将 Markdown 论文按 Nature 风格模板导出为 LaTeX。")
    parser.add_argument("--input", default=DEFAULT_INPUT, help="输入 Markdown 文件路径")
    parser.add_argument("--references", default=None, help="可选：单独指定参考文献 Markdown 文件路径")
    parser.add_argument("--bib", default=None, help="可选：指定 BibTeX 文件路径；若存在则优先使用")
    parser.add_argument("--citation-map", default=None, help="可选：指定编号引用到 BibTeX key 的映射文件")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="输出 tex 文件路径")
    parser.add_argument("--resource-base", default=None, help="图片等相对资源的解析基目录")
    parser.add_argument("--title", default=None, help="覆盖自动解析得到的标题")
    parser.add_argument("--author", default=None, help="覆盖自动解析得到的作者")
    parser.add_argument("--affiliation", default=None, help="覆盖自动解析得到的机构")
    parser.add_argument("--email", default=None, help="覆盖自动解析得到的邮箱")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    paper_dir = script_dir.parent

    input_path = Path(args.input)
    reference_path = Path(args.references) if args.references else None
    bib_path = Path(args.bib) if args.bib else None
    citation_map_path = Path(args.citation_map) if args.citation_map else None
    output_path = Path(args.output)
    resource_base = Path(args.resource_base) if args.resource_base else input_path.parent

    if not input_path.is_absolute():
        input_path = (paper_dir / input_path).resolve()
    if reference_path is not None and not reference_path.is_absolute():
        reference_path = (paper_dir / reference_path).resolve()
    if bib_path is not None and not bib_path.is_absolute():
        bib_path = (paper_dir / bib_path).resolve()
    if citation_map_path is not None and not citation_map_path.is_absolute():
        citation_map_path = (paper_dir / citation_map_path).resolve()
    if not output_path.is_absolute():
        output_path = (script_dir / output_path).resolve()
    if not resource_base.is_absolute():
        resource_base = (paper_dir / resource_base).resolve()
    else:
        resource_base = resource_base.resolve()

    default_bib_path = paper_dir / "ref.bib"
    if bib_path is None and default_bib_path.exists():
        bib_path = default_bib_path.resolve()

    default_citation_map_path = paper_dir / "citation_key_map.md"
    if citation_map_path is None and default_citation_map_path.exists():
        citation_map_path = default_citation_map_path.resolve()

    if not input_path.exists():
        print(f"输入文件不存在: {input_path}", file=sys.stderr)
        return 1
    if reference_path is not None and not reference_path.exists():
        print(f"参考文献文件不存在: {reference_path}", file=sys.stderr)
        return 1
    if bib_path is not None and not bib_path.exists():
        print(f"BibTeX 文件不存在: {bib_path}", file=sys.stderr)
        return 1
    if citation_map_path is not None and not citation_map_path.exists():
        print(f"引用映射文件不存在: {citation_map_path}", file=sys.stderr)
        return 1

    markdown_text = input_path.read_text(encoding="utf-8")
    reference_text = reference_path.read_text(encoding="utf-8") if reference_path is not None else ""
    citation_key_map = load_citation_key_map(citation_map_path) if citation_map_path is not None else {}
    lines = markdown_text.splitlines()

    title, author, affiliation, email, author_blocks, start_index = parse_metadata(lines)
    if args.title:
        title = args.title
    if args.author:
        author = args.author
        author_blocks = []
    if args.affiliation:
        affiliation = args.affiliation
        author_blocks = []
    if args.email:
        email = args.email
        author_blocks = []

    sections = parse_sections(lines, start_index)
    if not sections:
        print("未解析到任何章节，请检查输入 Markdown 格式。", file=sys.stderr)
        return 1

    document = build_document(
        title,
        author,
        affiliation,
        email,
        author_blocks,
        sections,
        reference_text,
        resource_base,
        bib_name=bib_path.stem if bib_path is not None else None,
        citation_key_map=citation_key_map,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if bib_path is not None:
        staged_bib_path = output_path.parent / bib_path.name
        if staged_bib_path.resolve() != bib_path.resolve():
            shutil.copy2(bib_path, staged_bib_path)
    output_path.write_text(document, encoding="utf-8")
    print(f"LaTeX 已生成: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())