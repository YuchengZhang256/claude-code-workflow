#!/usr/bin/env python3
"""Minimal HTML → plain text stripper for the web-access skill.

Reads HTML from stdin, writes cleaned text (one block per line) to stdout.
Used as a fallback when `pandoc` is not available. Intentionally small: no
external dependencies, no markdown reconstruction — just text extraction
good enough for a downstream LLM to read.
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser

# Tags whose content we drop entirely.
SKIP_TAGS = frozenset({
    "script", "style", "noscript", "iframe", "svg",
    "nav", "footer", "header", "aside", "form",
    "head", "meta", "link",
})

# Block-level tags — insert a newline after their content so paragraphs
# stay separated in the output.
BLOCK_TAGS = frozenset({
    "p", "div", "section", "article", "li", "tr", "td", "th",
    "h1", "h2", "h3", "h4", "h5", "h6", "br", "hr", "blockquote",
    "pre",
})


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in SKIP_TAGS:
            self._skip_depth += 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_startendtag(self, tag: str, attrs) -> None:
        # Void tags like <br/> — treat as block breaks, not skip regions.
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data.strip():
            self.parts.append(data)


def main() -> int:
    try:
        raw = sys.stdin.read()
    except Exception:
        return 1

    parser = TextExtractor()
    try:
        parser.feed(raw)
        parser.close()
    except Exception:
        # html.parser is lenient but not infallible — swallow and emit whatever
        # was collected so far rather than failing the whole pipeline.
        pass

    text = "".join(parser.parts)
    # Collapse 3+ blank lines and trailing whitespace on each line.
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    sys.stdout.write(text.strip() + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
