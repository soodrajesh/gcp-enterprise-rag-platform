"""Heading-aware chunking.

Splits Markdown on headings first so every chunk carries its section path as
context, then packs paragraphs up to a character budget with a small overlap.
Character budget (not tokens) keeps this dependency-free; ~4 chars/token means
900 chars is roughly 225 tokens, well inside the embedding model's limit.
"""

import re
from dataclasses import dataclass

HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)$")


@dataclass(frozen=True)
class Chunk:
    index: int
    heading: str
    text: str


def _sections(text: str) -> list[tuple[str, str]]:
    stack: list[tuple[int, str]] = []
    sections: list[tuple[str, list[str]]] = [("", [])]
    for line in text.splitlines():
        m = HEADING_RE.match(line)
        if m:
            level, title = len(m.group(1)), m.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            sections.append((" > ".join(t for _, t in stack), []))
        else:
            sections[-1][1].append(line)
    return [(h, "\n".join(body).strip()) for h, body in sections if "\n".join(body).strip()]


def _pack(paragraphs: list[str], budget: int, overlap: int) -> list[str]:
    out: list[str] = []
    current = ""
    for para in paragraphs:
        while len(para) > budget:  # hard-split pathological paragraphs on whitespace
            cut = para.rfind(" ", 0, budget)
            cut = cut if cut > budget // 2 else budget
            piece, para = para[:cut], para[cut:].lstrip()
            if current:
                out.append(current)
                current = ""
            out.append(piece)
        if current and len(current) + len(para) + 2 > budget:
            out.append(current)
            tail = current[-overlap:] if overlap else ""
            current = (tail + "\n\n" + para).strip() if tail else para
        else:
            current = f"{current}\n\n{para}".strip() if current else para
    if current:
        out.append(current)
    return out


def chunk_markdown(text: str, budget: int = 900, overlap: int = 120) -> list[Chunk]:
    chunks: list[Chunk] = []
    for heading, body in _sections(text):
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        for piece in _pack(paragraphs, budget, overlap):
            chunks.append(Chunk(index=len(chunks), heading=heading, text=piece))
    return chunks
