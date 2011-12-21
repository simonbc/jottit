import difflib, string, re
import web

def isTag(x): return x[0] == "<" and x[-1] == ">"

def better_diff(a, b):
    out = []
    a, b = html2list(a), html2list(b)
    s = difflib.SequenceMatcher(None, a, b)
    for e in s.get_opcodes():
        if e[0] == "replace":
            out.append('<span class="delete">'+ web.htmlquote(''.join(a[e[1]:e[2]])) + "</span>")
            out.append('<span class="insert">'+ web.htmlquote(''.join(b[e[3]:e[4]])) + "</span>")
        elif e[0] == "delete":
            out.append('<span class="delete">'+ web.htmlquote(''.join(a[e[1]:e[2]])) + "</span>")
        elif e[0] == "insert":
            out.append('<span class="insert">'+ web.htmlquote(''.join(b[e[3]:e[4]])) + "</span>")
        elif e[0] == "equal":
                out.append(web.htmlquote(''.join(b[e[3]:e[4]])))
    out = ''.join(out)
    return re.sub(r'(\r\n|\n|\r)', '<br />\n', out)

def html2list(x, b=0):
    mode = 'char'
    cur = ''
    out = []
    x = re.sub(r'(\r\n|\r)', '\n', x)
    for c in x:
        if mode == 'tag':
            if c == '>':
                if b: cur += '&gt;'
                else: cur += c
                out.append(cur); cur = ''; mode = 'char'
            else: cur += c
        elif mode == 'char':
            if c == '<':
                out.append(cur)
                if b: cur = '&lt;'
                else: cur = c
                mode = 'tag'
            elif c in string.whitespace[:-1]+string.punctuation:
                out.append(cur); out.append(c); cur = ''
            elif c == ' ':
                out.append(cur); cur = c
            else:
                cur += c


    out.append(cur)
    return filter(lambda x: x is not '', out)
