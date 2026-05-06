from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "论文_md形式" / "_脚本"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from paper_pipeline.latex import Section, build_document


def test_build_document_uses_twocolumn_and_avoids_longtable_for_tables() -> None:
    document = build_document(
        title="Test Paper",
        author="",
        affiliation="",
        email="",
        author_blocks=[],
        sections=[
            Section("摘要", "简短摘要。"),
            Section(
                "引言",
                "表 1 给出一个简单示例。\n\n"
                "| 列A | 列B |\n"
                "| --- | --- |\n"
                "| 值1 | 值2 |\n",
            ),
        ],
        reference_text="",
        resource_base=Path(__file__).resolve().parents[1],
    )

    assert "\\documentclass[11pt,twocolumn]{article}" in document
    assert "\\begin{longtable}" not in document
    assert "\\begin{table}[t]" in document
    assert "\\resizebox{\\columnwidth}{!}{%" in document
    assert "\\begin{table*}[t]" not in document
