from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MarkdownSection:
    title: str
    content: str


def read_markdown_sections(path: Path) -> list[MarkdownSection]:
    if not path.exists():
        return []

    lines = path.read_text(encoding="utf-8").splitlines()
    preamble: list[str] = []
    sections: list[MarkdownSection] = []
    current_title: str | None = None
    current_lines: list[str] = []

    for line in lines:
        if line.startswith("## "):
            if current_title is not None:
                sections.append(MarkdownSection(current_title, "\n".join(current_lines).strip()))
            elif preamble:
                sections.append(MarkdownSection("Overview", "\n".join(preamble).strip()))
            current_title = line[3:].strip()
            current_lines = [line]
        elif current_title is None:
            preamble.append(line)
        else:
            current_lines.append(line)

    if current_title is not None:
        sections.append(MarkdownSection(current_title, "\n".join(current_lines).strip()))
    elif preamble:
        sections.append(MarkdownSection("Overview", "\n".join(preamble).strip()))

    return [section for section in sections if section.content]
