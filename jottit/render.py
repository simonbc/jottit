from __future__ import annotations

import re

import mistune
import nh3

from jottit.urls import page_slug

# Backreference avoids matching escaped brackets: `\[[not a link]]`.
_WIKILINK_RE = re.compile(r"(?<!\\)\[\[(.*?)(?:\|(.*?))?\]\]")

# `escape=False` lets users embed raw HTML in markdown (the original used
# markdown2's `markdown-in-html` extra). nh3 cleans the output before it
# reaches the browser, so unsafe tags don't survive.
_markdown = mistune.create_markdown(escape=False)

# The editor inserts uploaded images as `/site/uploads/<name>`, which is
# right for subdomain sites. The same page is also served under its secret
# URL (and in feeds, against an absolute root), so re-root the src there.
# Runs on nh3 output, where `<` and `>` in text and attribute values are
# entity-escaped, so this only matches a real <img> tag's src.
_UPLOAD_SRC_RE = re.compile(r'(<img\b[^>]*?\ssrc=")/site/uploads/')


def _wikify(html: str, *, site_root: str) -> str:
    def mangle(match: re.Match[str]) -> str:
        link = match.group(1)
        anchor = match.group(2) or link
        href = site_root if link.strip().lower() == "home" else site_root + page_slug(link)
        return f'<a href="{href}" class="internal">{anchor}</a>'

    return _WIKILINK_RE.sub(mangle, html)


def format_content(text: str, *, site_root: str) -> str:
    """Render page content (markdown + embedded HTML + wikilinks) as safe HTML.

    `site_root` is the URL prefix that page names hang off (e.g. `/` for a
    subdomain site, `/abc12/` for one accessed via its secret URL). Uploaded
    image srcs are re-rooted against it too.

    Wikilinks (`[[name]]` or `[[name|anchor]]`) run after sanitization so the
    `class="internal"` marker we add isn't stripped. `[[home]]` is a special
    case that links to the site root.
    """
    stripped = text.strip().lower()
    if stripped.startswith("<html") and stripped.endswith("</html>"):
        # Legacy passthrough: a page that's wholly HTML bypasses markdown
        # rendering entirely. Inherited from the 2007 codebase — Jottit
        # treats this as "the user knows what they're doing".
        return text

    html = _markdown(text)
    assert isinstance(html, str)  # default HTML renderer always returns str
    html = _UPLOAD_SRC_RE.sub(lambda m: f"{m.group(1)}{site_root}site/uploads/", nh3.clean(html))
    return _wikify(html, site_root=site_root)
