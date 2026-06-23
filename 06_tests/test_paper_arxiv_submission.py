from pathlib import Path
import sys
import zipfile


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "论文_md形式" / "_脚本"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from paper_pipeline.arxiv import SubmissionInputs, build_arxiv_submission_package


def test_build_arxiv_submission_package_rewrites_paths_and_generates_metadata(
    tmp_path: Path,
) -> None:
    tex_path = tmp_path / "Decathlon_VOC_Analyzer_Nature_Template.tex"
    tex_path.write_text(
        """\\documentclass[11pt]{article}

% ===== 基本宏包：尽量保持简单 =====
\\usepackage[margin=1in]{geometry}
\\usepackage{graphicx}
\\usepackage{xurl}
\\usepackage{hyperref}
\\usepackage[numbers,sort&compress]{natbib}
\\usepackage{setspace}
\\usepackage{fontspec}
\\usepackage{xeCJK}

\\title{\\textbf{Example Title}}

\\author{{\\small
\\textbf{Alice Smith}\\textsuperscript{1*†}
}}

\\date{} % Nature 系列投稿一般不需要显示日期

\\begin{document}
\\maketitle

\\begin{abstract}
Example abstract.
\\end{abstract}

\\begin{figure}[H]
\\centering
\\includegraphics[width=0.92\\textwidth]{/tmp/project/论文_md形式/图片/图1.png}
\\caption{Example figure.}
\\end{figure}

\\bibliographystyle{unsrtnat}
\\bibliography{ref}

\\end{document}
""",
        encoding="utf-8",
    )

    bbl_path = tmp_path / "Decathlon_VOC_Analyzer_Nature_Template.bbl"
    bbl_path.write_text("% precompiled bibliography\n", encoding="utf-8")

    bib_path = tmp_path / "ref.bib"
    bib_path.write_text("@article{example, title={Example}}\n", encoding="utf-8")

    preview_pdf = tmp_path / "Decathlon_VOC_Analyzer_Nature_Template.pdf"
    preview_pdf.write_bytes(b"%PDF-1.4\n")

    log_path = tmp_path / "Decathlon_VOC_Analyzer_Nature_Template.log"
    log_path.write_text(
        "Output written on Decathlon_VOC_Analyzer_Nature_Template.pdf (12 pages, 34567 bytes).\n",
        encoding="utf-8",
    )

    figure_path = tmp_path / "图1.png"
    figure_path.write_bytes(b"fake png bytes")

    title_page = tmp_path / "title_page.md"
    title_page.write_text(
        """# Example Title

Alice Smith
Example Institute
alice@example.com
""",
        encoding="utf-8",
    )

    abstract_path = tmp_path / "00_abstract.md"
    abstract_path.write_text(
        """# Abstract

Example abstract.
""",
        encoding="utf-8",
    )

    output_dir = tmp_path / "arxiv_submission"

    build_arxiv_submission_package(
        SubmissionInputs(
            tex_path=tex_path,
            bbl_path=bbl_path,
            bib_path=bib_path,
            preview_pdf_path=preview_pdf,
            compile_log_path=log_path,
            title_page_path=title_page,
            abstract_markdown_path=abstract_path,
            figure_paths=[figure_path],
            output_dir=output_dir,
            manuscript_name="decathlon_voc_analyzer",
        )
    )

    packaged_tex = output_dir / "decathlon_voc_analyzer.tex"
    assert packaged_tex.exists()

    packaged_tex_text = packaged_tex.read_text(encoding="utf-8")
    assert "figures/fig1.png" in packaged_tex_text
    assert "/tmp/project/" not in packaged_tex_text
    assert "\\input{full_en_manuscript.bbl}" in packaged_tex_text
    assert "fontspec" not in packaged_tex_text
    assert "xeCJK" not in packaged_tex_text
    assert "\\textdagger" in packaged_tex_text

    assert (output_dir / "figures" / "fig1.png").exists()
    assert (output_dir / "full_en_manuscript.bbl").exists()
    assert (output_dir / "ref.bib").exists()
    assert (output_dir / "decathlon_voc_analyzer.pdf").exists()

    metadata_text = (output_dir / "arxiv_submission_metadata.txt").read_text(encoding="utf-8")
    assert "【Title】\nExample Title" in metadata_text
    assert "【Author(s)】\nAlice Smith" in metadata_text
    assert "【Abstract】\nExample abstract." in metadata_text
    assert "12 pages" in metadata_text
    assert "1 figure" in metadata_text

    archive_path = output_dir / "decathlon_voc_analyzer_arxiv.zip"
    assert archive_path.exists()
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())

    assert "decathlon_voc_analyzer.tex" in names
    assert "full_en_manuscript.bbl" in names
    assert "ref.bib" in names
    assert "figures/fig1.png" in names
    assert "arxiv_submission_metadata.txt" not in names
    assert "ARXIV_SUBMISSION_GUIDE.md" not in names