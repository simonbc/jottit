from __future__ import annotations

from jottit.diff import better_diff, html2list


def test_html2list_splits_words_and_drops_whitespace_runs() -> None:
    assert html2list("hello   world") == ["hello", "world"]


def test_html2list_emits_start_and_end_tags() -> None:
    tokens = html2list("<p>hi</p>")
    assert tokens == ["<p>", "hi", "</p>"]


def test_html2list_preserves_tag_attributes() -> None:
    tokens = html2list('<a href="/x">go</a>')
    assert tokens == ['<a href="/x">', "go", "</a>"]


def test_better_diff_equal_passes_through() -> None:
    assert better_diff("hello world", "hello world") == "hello world"


def test_better_diff_marks_inserts() -> None:
    out = better_diff("hello", "hello world")
    assert "<ins>world</ins>" in out
    assert "hello" in out


def test_better_diff_marks_deletes() -> None:
    out = better_diff("hello world", "hello")
    assert "<del>world</del>" in out


def test_better_diff_marks_replacements() -> None:
    out = better_diff("hello world", "hello there")
    assert "<del>world</del>" in out
    assert "<ins>there</ins>" in out
