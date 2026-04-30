#!/usr/bin/env python3

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


FINAL_PDF_NAME = "Decathlon_VOC_Analyzer.pdf"
INTERMEDIATE_TEX_NAME = "Decathlon_VOC_Analyzer_Nature_Template.tex"
INTERMEDIATE_OUT_NAME = "Decathlon_VOC_Analyzer_Nature_Template.out"
INTERMEDIATE_PDF_NAME = "Decathlon_VOC_Analyzer_Nature_Template.pdf"
MERGED_STAGE_DIR = "01_完整合并"
LATEX_STAGE_DIR = "02_latex"
PDF_STAGE_DIR = "03_pdf"
ENGLISH_SECTION_DIR = "英文逐章稿"
DEFAULT_FINAL_PDF_ZH = f"outputs/{FINAL_PDF_NAME}"
DEFAULT_FINAL_PDF_EN = "outputs/Decathlon_VOC_Analyzer_EN.pdf"
DEFAULT_INTERMEDIATE_DIR_ZH = "outputs/中间文件"
DEFAULT_INTERMEDIATE_DIR_EN = "outputs/中间文件_en"


def require_command(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(f"未找到必需命令: {name}")
    return path


def run_command(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def tex_uses_bibtex(tex_path: Path) -> bool:
    return "\\bibliography{" in tex_path.read_text(encoding="utf-8")


def compile_tex_to_pdf(tex_path: Path, output_dir: Path) -> Path:
    xelatex = require_command("xelatex")
    cmd = [
        xelatex,
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-output-directory",
        str(output_dir),
        str(tex_path),
    ]
    run_command(cmd, cwd=output_dir)

    if tex_uses_bibtex(tex_path):
        # BibTeX 只在 aux 中出现 \bibdata/\bibstyle 时才有意义。
        # 在某些环境下（例如编辑器自动触发 pdflatex 覆盖 aux/log），aux 可能会变成空文件，
        # 这会导致 bibtex 以非 0 退出码失败，但此时仍可继续生成（无参考文献的）PDF。
        aux_path = output_dir / f"{tex_path.stem}.aux"
        aux_text = aux_path.read_text(encoding="utf-8") if aux_path.exists() else ""
        if "\\bibdata{" in aux_text and "\\bibstyle{" in aux_text:
            bibtex = require_command("bibtex")
            try:
                run_command([bibtex, tex_path.stem], cwd=output_dir)
            except subprocess.CalledProcessError as exc:
                print(
                    f"注意：BibTeX 执行失败（将继续生成 PDF，不影响图片/正文导出）：{exc}",
                    file=sys.stderr,
                )
        else:
            print(
                "注意：未在 .aux 中检测到 BibTeX 元信息（\\bibdata/\\bibstyle），跳过 bibtex。",
                file=sys.stderr,
            )

    run_command(cmd, cwd=output_dir)
    run_command(cmd, cwd=output_dir)

    pdf_path = output_dir / tex_path.with_suffix(".pdf").name
    if not pdf_path.exists():
        raise RuntimeError(f"未生成预期 PDF: {pdf_path}")
    return pdf_path


def normalize_language(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"zh", "cn", "zh-cn", "chinese"}:
        return "zh"
    if normalized in {"en", "english"}:
        return "en"
    raise ValueError(f"不支持的语言参数: {value}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="一键执行：分章合并 -> LaTeX -> PDF。")
    parser.add_argument(
        "--final-pdf",
        default=None,
        help="最终 PDF 输出路径，相对路径默认写入脚本目录。",
    )
    parser.add_argument(
        "--intermediate-dir",
        default=None,
        help="中间文件目录，相对路径默认写入脚本目录。",
    )
    parser.add_argument(
        "--language",
        default="zh",
        help="导出语言，支持 zh 或 en；默认 zh。",
    )
    parser.add_argument(
        "--en",
        action="store_true",
        help="快捷参数：导出英文版（等价于 --language en）。",
    )
    return parser.parse_args()


def prepare_stage_dirs(intermediate_dir: Path) -> tuple[Path, Path, Path]:
    merged_dir = intermediate_dir / MERGED_STAGE_DIR
    latex_dir = intermediate_dir / LATEX_STAGE_DIR
    pdf_dir = intermediate_dir / PDF_STAGE_DIR

    merged_dir.mkdir(parents=True, exist_ok=True)
    latex_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    return merged_dir, latex_dir, pdf_dir


def relocate_file(source: Path, destination: Path) -> None:
    if not source.exists() or source.resolve() == destination.resolve():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        source.unlink()
    else:
        shutil.move(str(source), str(destination))


def normalize_legacy_outputs(
    paper_dir: Path,
    intermediate_dir: Path,
    merged_dir: Path,
    latex_dir: Path,
    pdf_dir: Path,
) -> None:
    stage_targets = {
        "Decathlon_VOC_Analyzer_Complete_Paper.md": merged_dir / "Decathlon_VOC_Analyzer_Complete_Paper.md",
        "Decathlon_VOC_Analyzer_Nature_Template.tex": latex_dir / "Decathlon_VOC_Analyzer_Nature_Template.tex",
        "Decathlon_VOC_Analyzer_Nature_Template.out": latex_dir / "Decathlon_VOC_Analyzer_Nature_Template.out",
        "Decathlon_VOC_Analyzer_Nature_Template.aux": latex_dir / "Decathlon_VOC_Analyzer_Nature_Template.aux",
        "Decathlon_VOC_Analyzer_Nature_Template.bbl": latex_dir / "Decathlon_VOC_Analyzer_Nature_Template.bbl",
        "Decathlon_VOC_Analyzer_Nature_Template.blg": latex_dir / "Decathlon_VOC_Analyzer_Nature_Template.blg",
        "Decathlon_VOC_Analyzer_Nature_Template.log": latex_dir / "Decathlon_VOC_Analyzer_Nature_Template.log",
        "missfont.log": latex_dir / "missfont.log",
        "Decathlon_VOC_Analyzer_Nature_Template.pdf": pdf_dir / "Decathlon_VOC_Analyzer_Nature_Template.pdf",
    }

    for name, destination in stage_targets.items():
        relocate_file(intermediate_dir / name, destination)

    for name, destination in stage_targets.items():
        relocate_file(paper_dir / name, destination)


def main() -> int:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    paper_dir = script_dir.parent
    python_executable = sys.executable

    try:
        language = normalize_language("en" if args.en else args.language)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if language == "en":
        section_dir = paper_dir / ENGLISH_SECTION_DIR
        default_final_pdf = DEFAULT_FINAL_PDF_EN
        default_intermediate_dir = DEFAULT_INTERMEDIATE_DIR_EN
    else:
        section_dir = paper_dir
        default_final_pdf = DEFAULT_FINAL_PDF_ZH
        default_intermediate_dir = DEFAULT_INTERMEDIATE_DIR_ZH

    intermediate_dir = Path(args.intermediate_dir or default_intermediate_dir)
    if not intermediate_dir.is_absolute():
        intermediate_dir = (script_dir / intermediate_dir).resolve()
    else:
        intermediate_dir = intermediate_dir.resolve()

    final_pdf = Path(args.final_pdf or default_final_pdf)
    if not final_pdf.is_absolute():
        final_pdf = (script_dir / final_pdf).resolve()
    else:
        final_pdf = final_pdf.resolve()

    final_pdf.parent.mkdir(parents=True, exist_ok=True)
    intermediate_dir.mkdir(parents=True, exist_ok=True)
    merged_dir, latex_dir, pdf_dir = prepare_stage_dirs(intermediate_dir)
    normalize_legacy_outputs(paper_dir, intermediate_dir, merged_dir, latex_dir, pdf_dir)

    build_script = script_dir / "build_complete_paper.py"
    latex_script = script_dir / "export_markdown_to_latex.py"

    staged_complete_markdown = merged_dir / "Decathlon_VOC_Analyzer_Complete_Paper.md"
    intermediate_tex = latex_dir / INTERMEDIATE_TEX_NAME
    staged_out = latex_dir / INTERMEDIATE_OUT_NAME
    staged_pdf = pdf_dir / INTERMEDIATE_PDF_NAME

    if not section_dir.exists():
        print(f"分章目录不存在: {section_dir}", file=sys.stderr)
        return 1

    try:
        run_command(
            [
                python_executable,
                str(build_script),
                "--section-dir",
                str(section_dir),
                "--output",
                str(staged_complete_markdown),
            ]
        )
        run_command(
            [
                python_executable,
                str(latex_script),
                "--input",
                str(staged_complete_markdown),
                "--resource-base",
                str(paper_dir),
                "--output",
                str(intermediate_tex),
            ]
        )
        intermediate_pdf = compile_tex_to_pdf(intermediate_tex, latex_dir)
        shutil.copy2(intermediate_pdf, staged_pdf)
        shutil.copy2(staged_pdf, final_pdf)
        normalize_legacy_outputs(paper_dir, intermediate_dir, merged_dir, latex_dir, pdf_dir)
    except Exception as exc:  # noqa: BLE001
        # XeLaTeX may still emit a (partial) PDF before failing (e.g., missing env Shaded).
        # To avoid confusing stale outputs, if that PDF exists, sync it to the usual locations.
        try:
            partial_pdf = latex_dir / INTERMEDIATE_PDF_NAME
            if partial_pdf.exists():
                shutil.copy2(partial_pdf, staged_pdf)
                shutil.copy2(staged_pdf, final_pdf)
                print(
                    f"注意：LaTeX 编译未完全成功，但已将当前生成的 PDF 同步到最终输出：{final_pdf}",
                    file=sys.stderr,
                )
        except Exception:  # noqa: BLE001
            pass
        print(f"Pipeline 执行失败: {exc}", file=sys.stderr)
        return 1

    print(f"导出语言: {language}")
    print(f"分章目录: {section_dir}")
    print(f"最终 PDF 已生成: {final_pdf}")
    print(f"中间文件目录: {intermediate_dir}")
    print(f"完整合并稿: {staged_complete_markdown}")
    print(f"LaTeX 文件: {intermediate_tex}")
    print(f"LaTeX 输出索引: {staged_out}")
    print(f"中间 PDF: {staged_pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())