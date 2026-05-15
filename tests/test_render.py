from __future__ import annotations

from jottit.render import format_content

# ---- markdown ----


def test_format_content_renders_bold() -> None:
    out = format_content("**hi**", site_root="/")
    assert "<strong>hi</strong>" in out


def test_format_content_renders_headings() -> None:
    out = format_content("# Title", site_root="/")
    assert "<h1>Title</h1>" in out


def test_format_content_strips_dangerous_tags() -> None:
    out = format_content("<script>alert(1)</script>hello", site_root="/")
    assert "<script>" not in out
    assert "hello" in out


def test_format_content_keeps_safe_html() -> None:
    out = format_content("<p>hi <em>there</em></p>", site_root="/")
    assert "<em>there</em>" in out


# ---- wikilinks ----


def test_wikilink_simple() -> None:
    out = format_content("[[FooBar]]", site_root="/")
    assert '<a href="/foobar" class="internal">FooBar</a>' in out


def test_wikilink_with_anchor() -> None:
    out = format_content("[[About Us|our team]]", site_root="/")
    assert '<a href="/about_us" class="internal">our team</a>' in out


def test_wikilink_home_points_to_site_root() -> None:
    out = format_content("[[home]]", site_root="/abc12/")
    assert '<a href="/abc12/" class="internal">home</a>' in out


def test_wikilink_with_secret_url_site_root() -> None:
    out = format_content("[[Notes]]", site_root="/abc12/")
    assert 'href="/abc12/notes"' in out


# ---- full-HTML passthrough ----


def test_full_html_passthrough_bypasses_markdown_and_sanitize() -> None:
    raw = "<html><body><script>x</script></body></html>"
    out = format_content(raw, site_root="/")
    assert out == raw
