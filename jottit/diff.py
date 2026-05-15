from __future__ import annotations

import difflib
import re
from html.parser import HTMLParser


class _HTMLTokenizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.out: list[str] = []

    def handle_data(self, data: str) -> None:
        normalized = re.sub(r"\s+", " ", data)
        self.out.extend(re.findall(r"[^\s]+", normalized))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_str = "".join(f' {name}="{value}"' for name, value in attrs if value is not None)
        self.out.append(f"<{tag}{attr_str}>")

    def handle_endtag(self, tag: str) -> None:
        self.out.append(f"</{tag}>")


def html2list(text: str) -> list[str]:
    """Tokenize HTML into words and tags, dropping whitespace runs."""
    tokenizer = _HTMLTokenizer()
    tokenizer.feed(text)
    tokenizer.close()
    return tokenizer.out


def better_diff(a: str, b: str) -> str:
    """Render an HTML diff of two strings using <ins>/<del> wrappers."""
    a_tokens = html2list(a)
    b_tokens = html2list(b)
    matcher = difflib.SequenceMatcher(None, a_tokens, b_tokens)
    parts: list[str] = []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            parts.extend(b_tokens[j1:j2])
        elif op == "delete":
            parts.append("<del>" + " ".join(a_tokens[i1:i2]) + "</del>")
        elif op == "insert":
            parts.append("<ins>" + " ".join(b_tokens[j1:j2]) + "</ins>")
        elif op == "replace":
            parts.append("<del>" + " ".join(a_tokens[i1:i2]) + "</del>")
            parts.append("<ins>" + " ".join(b_tokens[j1:j2]) + "</ins>")
    return " ".join(parts)
