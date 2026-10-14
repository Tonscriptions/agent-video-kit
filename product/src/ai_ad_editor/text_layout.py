"""Local text layout shared by wrapping, karaoke and typewriter rendering."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any


def graphemes(text: str) -> list[tuple[int, int, str]]:
    """Keep combining marks, emoji modifiers and ZWJ sequences together.

    This deliberately bounded segmenter covers common advertising text. It is
    not a complete Unicode line-breaking or bidirectional shaping engine.
    """
    clusters: list[tuple[int, int, str]] = []
    for index, character in enumerate(text):
        code = ord(character)
        attaches = bool(clusters) and (
            unicodedata.category(character).startswith("M")
            or character == "\u200d"
            or clusters[-1][2].endswith("\u200d")
            or 0x1F3FB <= code <= 0x1F3FF
            or 0xFE00 <= code <= 0xFE0F
            or 0xE0100 <= code <= 0xE01EF
        )
        if attaches and character != "\n" and clusters[-1][2] != "\n":
            begin, _, value = clusters[-1]
            clusters[-1] = (begin, index + 1, value + character)
        else:
            clusters.append((index, index + 1, character))
    return clusters


def text_width(font: Any, text: str, font_size: int) -> float:
    if font is not None:
        try:
            if callable(getattr(font, "getlength", None)):
                return max(0.0, float(font.getlength(text)))
            box = font.getbbox(text)
            return max(0.0, float(box[2] - box[0]))
        except (ValueError, TypeError, OSError, AttributeError):
            pass
    units = sum(1.0 if ord(value[2][0]) > 0x2FF else 0.55 for value in graphemes(text))
    return units * max(1, font_size)


@dataclass(frozen=True)
class TextLine:
    text: str
    start: int
    end: int
    width: float


@dataclass(frozen=True)
class TextLayout:
    source: str
    lines: tuple[TextLine, ...]
    line_height: float
    line_spacing: float

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

    @property
    def width(self) -> float:
        return max((line.width for line in self.lines), default=0.0)

    @property
    def height(self) -> float:
        return self.line_height + max(0, len(self.lines) - 1) * (self.line_height + self.line_spacing)


def build_text_layout(text: str, style: dict[str, Any], font: Any, font_size: int) -> TextLayout:
    width = style.get("max_width", style.get("wrap_width"))
    max_width = float(width) if width is not None else float("inf")
    lines: list[TextLine] = []
    offset = 0
    for paragraph in text.split("\n"):
        clusters = graphemes(paragraph)
        if not clusters:
            lines.append(TextLine("", offset, offset, 0.0))
        cursor = 0
        while cursor < len(clusters):
            end = cursor
            while end < len(clusters):
                candidate = paragraph[clusters[cursor][0]:clusters[end][1]]
                if end > cursor and text_width(font, candidate, font_size) > max_width:
                    break
                end += 1
            # Prefer a word boundary, then fall back to a complete grapheme.
            if end < len(clusters):
                boundaries = [i for i in range(cursor + 1, end + 1) if clusters[i - 1][2].isspace()]
                if boundaries:
                    end = boundaries[-1]
            begin_char = clusters[cursor][0]
            end_char = clusters[end - 1][1]
            visible = paragraph[begin_char:end_char].rstrip()
            lines.append(TextLine(visible, offset + begin_char, offset + begin_char + len(visible), text_width(font, visible, font_size)))
            cursor = end
            while cursor < len(clusters) and clusters[cursor][2].isspace():
                cursor += 1
        offset += len(paragraph) + 1
    line_height = float(font_size)
    if font is not None:
        try:
            ascent, descent = font.getmetrics()
            line_height = float(ascent + descent)
        except (ValueError, TypeError, OSError, AttributeError):
            pass
    return TextLayout(text, tuple(lines), line_height, float(style.get("line_spacing", 0)))


def word_ranges(text: str, entries: list[dict[str, Any]]) -> list[tuple[dict[str, Any], int, int]]:
    """Resolve timed words to authored text; never invent spaces or positions."""
    resolved: list[tuple[dict[str, Any], int, int]] = []
    cursor = 0
    for entry in entries:
        word = str(entry.get("text", entry.get("word", "")))
        if not word:
            raise ValueError("word_timing text must not be empty")
        start = entry.get("start_char")
        if start is None:
            start = text.find(word, cursor)
        if isinstance(start, bool) or not isinstance(start, int) or start < cursor or text[start:start + len(word)] != word:
            raise ValueError("word_timing text/start_char does not match the source in order")
        cursor = start + len(word)
        resolved.append((entry, start, cursor))
    return resolved
