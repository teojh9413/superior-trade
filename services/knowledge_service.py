from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_./:-]*")


@dataclass(slots=True)
class KnowledgeSection:
    source_name: str
    heading_path: tuple[str, ...]
    content: str
    score: int = 0

    @property
    def heading_path_display(self) -> str:
        return " > ".join(self.heading_path) if self.heading_path else "(root)"

    @property
    def searchable_text(self) -> str:
        heading_text = " ".join(self.heading_path)
        return f"{self.source_name} {heading_text} {self.content}".lower()


class KnowledgeService:
    def __init__(self, knowledge_dir: Path) -> None:
        self.knowledge_dir = knowledge_dir
        self._sections: list[KnowledgeSection] = []

    def load(self) -> None:
        self._sections = []
        for path in sorted(self.knowledge_dir.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            self._sections.extend(split_markdown_sections(path.name, text))

    def reload(self) -> None:
        self.load()

    def list_sources(self) -> list[str]:
        return sorted({section.source_name for section in self._sections})

    def search(self, query: str, top_k: int = 3) -> list[KnowledgeSection]:
        tokens = tokenize(query)
        if not tokens:
            return self._sections[:top_k]

        scored: list[KnowledgeSection] = []
        for section in self._sections:
            score = score_section(section, tokens)
            if score > 0:
                scored.append(
                    KnowledgeSection(
                        source_name=section.source_name,
                        heading_path=section.heading_path,
                        content=section.content,
                        score=score,
                    )
                )

        scored.sort(key=lambda item: (-item.score, item.source_name, item.heading_path_display))
        return scored[:top_k]

    def build_context_block(self, query: str, top_k: int = 4, max_chars: int = 5000) -> str:
        sections = self.search(query, top_k=top_k)
        blocks: list[str] = []
        current_length = 0
        for section in sections:
            content = compact_whitespace(section.content)
            prefix = f"[SOURCE: {section.source_name} | HEADING: {section.heading_path_display}]\n"
            remaining = max_chars - current_length - len(prefix)
            if remaining <= 0 and blocks:
                break
            if remaining > 0:
                content = content[:remaining].rstrip()
            block = f"{prefix}{content}".strip()
            if current_length + len(block) > max_chars and blocks:
                break
            blocks.append(block)
            current_length += len(block)
        return "\n\n".join(blocks)


def split_markdown_sections(source_name: str, text: str) -> list[KnowledgeSection]:
    sections: list[KnowledgeSection] = []
    heading_stack: list[str] = []
    buffer: list[str] = []

    def flush_buffer() -> None:
        content = "\n".join(buffer).strip()
        if heading_stack or content:
            sections.append(
                KnowledgeSection(
                    source_name=source_name,
                    heading_path=tuple(heading_stack),
                    content=content,
                )
            )
        buffer.clear()

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("#"):
            flush_buffer()
            level = len(line) - len(line.lstrip("#"))
            title = line[level:].strip().strip("*").strip()
            heading_stack[:] = heading_stack[: level - 1]
            heading_stack.append(title)
            continue
        buffer.append(line)

    flush_buffer()
    return [section for section in sections if section.content or section.heading_path]


def tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_RE.finditer(text)]


def score_section(section: KnowledgeSection, tokens: list[str]) -> int:
    haystack = section.searchable_text
    score = 0
    for token in tokens:
        score += haystack.count(token)
        if token in section.source_name.lower():
            score += 1
        if section.heading_path and token in " ".join(section.heading_path).lower():
            score += 3
    if section.source_name.upper() == "SKILL.MD":
        score += 2
    return score


def compact_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
