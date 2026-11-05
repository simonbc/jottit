from __future__ import annotations

import re
from html import unescape

import pytest
from flask.testing import FlaskClient

from jottit.render import format_content


@pytest.mark.parametrize(
    ("method", "path", "needle"),
    [
        ("GET", "/about", b"Jottit makes getting a website"),
        ("GET", "/help", b"feedback@jottit.pub"),
        ("GET", "/sites", b"find your site"),
        ("POST", "/sites", b"find your site"),
        ("GET", "/feedback", b"jottit:feedback"),
        ("POST", "/feedback", b"jottit:feedback"),
    ],
)
def test_root_routes_serve_stubs(
    client: FlaskClient, method: str, path: str, needle: bytes
) -> None:
    response = client.open(path, method=method)
    assert response.status_code == 200
    assert needle in response.data


def test_help_page_examples_render_as_described(client: FlaskClient) -> None:
    # The help page's formatting examples must match what the renderer does.
    html = client.get("/help").get_data(as_text=True)
    examples = [
        unescape(block) for block in re.findall(r"<pre><code>(.*?)</code></pre>", html, re.S)
    ]
    out = format_content("\n\n".join(examples), site_root="/")
    for expected in [
        "<h1>Heading</h1>",
        "<h2>Smaller heading</h2>",
        "<ul>\n<li>Eggs</li>",
        "<ol>\n<li>Buy groceries</li>",
        '<a href="/recipes" class="internal">Recipes</a>',
        '<a href="/grocery_list" class="internal">my list</a>',
        '<a href="/" class="internal">home</a>',
        '<a href="https://jottit.pub/" rel="noopener noreferrer">Jottit</a>',
    ]:
        assert expected in out
