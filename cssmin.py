import os, re

delims = "\({};:,"
minifyCSSRe = {
    "comments": re.compile("\/\*.*?\*\/", re.DOTALL),
    "adjacentWhitespace": re.compile("\s+", re.MULTILINE),
    "leadingWhitespace": re.compile("\s([%s])" % delims),
    "trailingWhitespace": re.compile("([%s])\s" % delims)
}

def minify(css):
    """Remove unnecessary bloat from the given CSS, and return the result."""

    # First remove comments.  This will work for multiline comments as well
    # as inline.
    r = minifyCSSRe["comments"]
    while r.search(css):
        css = r.sub("", css)

    # Next replace all adjacent whitespace with a single space.  This will also
    # remove tabs and newlines.
    r = minifyCSSRe["adjacentWhitespace"]
    css = r.sub(" ", css)

    # Finally, remove whitespace adjacent to delimiters.
    for r in minifyCSSRe["leadingWhitespace"],minifyCSSRe["trailingWhitespace"]:
        while True:
            m = r.search(css)
            if not m:
                break
            css = r.sub(m.group(1), css, 1)

    return css

if __name__ == '__main__':
    files = filter(lambda f: f.endswith('.css'),os.listdir('static'))
    cwd = os.getcwd()
    for f in files:
        css = open(cwd+'/static/'+f, "r").read()
        css_min = minify(css);
        open(cwd+'/static/'+f, "w").write(css_min)
