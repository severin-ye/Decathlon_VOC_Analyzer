from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


FULL_SECTION_FILES = [
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

OPTIONAL_FALLBACK_FILES = {
    "title_page.md",
    *OPTIONAL_SECTION_FILES,
}


@dataclass(frozen=True)
class MarkdownSection:
    file_name: str
    text: str
    source_path: Path


@dataclass(frozen=True)
class MarkdownManuscript:
    kind: str
    sections: list[MarkdownSection]

    def render(self) -> str:
        return "\n\n".join(section.text for section in self.sections).rstrip() + "\n"


def detect_manuscript_kind(section_dir: Path, section_set: str) -> str:
    if section_set in {"summary", "full"}:
        return section_set
    if (section_dir / "02_system_design_implementation.md").exists():
        return "summary"
    if any((section_dir / file_name).exists() for file_name in FULL_SECTION_FILES):
        return "full"
    return "custom"


def expected_section_files(kind: str, section_dir: Path) -> list[str]:
    if kind == "summary":
        return SUMMARY_SECTION_FILES
    if kind == "full":
        return FULL_SECTION_FILES
    return sorted(path.name for path in section_dir.glob("*.md"))


def read_section(file_name: str, search_dirs: list[Path], *, optional: bool = False) -> MarkdownSection | None:
    checked_paths: list[Path] = []
    for search_dir in search_dirs:
        path = search_dir / file_name
        checked_paths.append(path)
        if path.exists():
            return MarkdownSection(
                file_name=file_name,
                text=path.read_text(encoding="utf-8").rstrip(),
                source_path=path,
            )
    if optional:
        return None
    checked = "、".join(str(path) for path in checked_paths)
    raise FileNotFoundError(f"缺少分章文件: {file_name}（已检查: {checked}）")


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


def parse_markdown_manuscript(
    section_dir: Path,
    *,
    include_title_page: bool,
    section_set: str,
    fallback_dirs: list[Path],
) -> MarkdownManuscript:
    kind = detect_manuscript_kind(section_dir, section_set)
    section_files = expected_section_files(kind, section_dir)
    search_dirs = [section_dir, *fallback_dirs]
    sections: list[MarkdownSection] = []

    for file_name in section_files:
        if file_name == "title_page.md" and not include_title_page:
            continue

        optional = file_name in OPTIONAL_FALLBACK_FILES
        section = read_section(file_name, search_dirs, optional=optional)
        if section is None:
            continue

        text = section.text
        if kind == "summary" and file_name != "title_page.md":
            text = promote_summary_headings(text)
        sections.append(MarkdownSection(file_name=file_name, text=text, source_path=section.source_path))

    if not sections:
        raise FileNotFoundError(f"未在目录中解析到 Markdown 分章: {section_dir}")

    return MarkdownManuscript(kind=kind, sections=sections)


def build_document(
    section_dir: Path,
    include_title_page: bool,
    section_set: str,
    fallback_dirs: list[Path],
) -> str:
    manuscript = parse_markdown_manuscript(
        section_dir,
        include_title_page=include_title_page,
        section_set=section_set,
        fallback_dirs=fallback_dirs,
    )
    return manuscript.render()
