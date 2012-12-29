import db, auth, utils
import web, markdown2
import re, datetime, random, string, math, os
from jinja import Environment, FileSystemLoader
from jinja.filters import simplefilter
from sanitize import HTML as sanitize
from dispatcher import modes, jt
from urllib import quote

env = Environment(loader=FileSystemLoader('templates'), auto_escape=True, friendly_traceback=False)
env_atom = Environment(loader=FileSystemLoader('feeds'), auto_escape=True, friendly_traceback=False)

# Jinja monkeypatch: done for 1.1

def finish_var(value, ctx):
    self = env
    if value is None:
        return ''
    elif value is self.undefined_singleton:
        return str(value)
    elif getattr(value, 'jinja_no_finalization', False):
        return value
    if self.default_filters:
        value = self.apply_filters(value, ctx, self.default_filters)
    if isinstance(value, str):
        value = value.decode('utf8')
    return value

env.finish_var = finish_var
env_atom.finish_var = finish_var

class Markup(str):
    def __html__(self):
        return self

def format(text):
    return wikify(text)

def render(filename, page_title=None, vars={}):
    web.header('Content-Type', 'text/html; charset=utf-8')
    tmpl = env.get_template('%s.html' % filename)
    vars['csstime'] = os.stat("static/css-generated.css")[8]
    vars['jstime'] = os.stat("static/js-generated.js")[8]
    if jt.site:
        vars['pages'] = list(db.get_pages())
        vars['logged_in'] = auth.logged_in()
        vars['design'] = db.get_design()
    print tmpl.render(vars)

def render_atom(filename, vars={}, status=None):
    if status: web.ctx.status = status
    web.header('Content-Type', 'application/atom+xml')
    tmpl = env_atom.get_template('%s.atom' % filename)
    print tmpl.render(vars)

wikilink_re = web.re_compile(r'(?<!\\)\[\[(.*?)(?:\|(.*?))?\]\]')
def wikify(text):

    def mangle_wikilink(match):
        link, anchor = match.groups()
        anchor = anchor or link
        link = utils.page_url(link)
        if link == 'home':
            link = ''

        return '<a href="%s" class="internal">%s</a>' % (link, anchor)

    tsl = text.strip().lower()
    if tsl.startswith('<html') and tsl.endswith('</html>'):
        # don't bother converting; it's all HTML
        return text

    text = markdown2.markdown(text.decode('utf8'), extras=['markdown-in-html']).encode('utf8')

    #@@ needs to not replace in <pre> and so on
    #@@ probably should convert url spaces to _s and stuff like that

    text = wikilink_re.sub(mangle_wikilink, text)

    return text

def serialize_json(**vars):
    _escapes = {'\n': '\\n', '\r': '\\r', '"':'\\"', "'":"\\'", ":":"\:"}
    def encode(value):
        old = value
        if type(value) == list:
            s = []
            for x in value:
                s.append(encode(x))
            value = '[%s]' % ', '.join(s)
        elif type(value) == web.utils.Storage:
            s = []
            for (k,v) in value.items():
                s.append(k + ': ' + encode(v))
            value = '{%s}' % ', '.join(s)
        elif type(value) == bool:
            value = (value and 'true') or 'false'
        else:
            value = str(value)
            value = value.replace('\\', '\\\\')
            for (k, v) in _escapes.items():
                value = value.replace(k, v)
            value = '"' + value + '"'

        return str(value)

    print '{%s}' % ", ".join(['%s: %s' % (k, encode(v)) for (k, v) in vars.items()])

def datestr(then, now=None, dom=True):
    def agohence(n, what, divisor=None):
        if divisor: n = n // divisor
        if abs(n) != 1: what += 's'
        count = str(abs(n))

        if not dom:
            return '%s %s ago' % (count, what)

        out = '<span id="count">' + count + '</span> '
        out += '<span id="unit">' + what
        out += '</span> ago'
        return out

    oneday = 24 * 60 * 60

    if not now: now = datetime.datetime.utcnow()
    delta = now - then
    deltaseconds = int(delta.days * oneday + delta.seconds + delta.microseconds * 1e-06)
    deltadays = abs(deltaseconds) // oneday
    if deltaseconds < 0: deltadays *= -1 # fix for oddity of floor

    if deltadays:
        if abs(deltadays) < 4:
            return agohence(deltadays, 'day')

        out = then.strftime('%B %e') # e.g. 'June 13'
        if then.year != now.year or deltadays < 0:
            out += ', %s' % then.year
        return out

    if int(deltaseconds):
        if abs(deltaseconds) > (60 * 60):
            return agohence(deltaseconds, 'hour', 60 * 60)
        elif abs(deltaseconds) > 60:
            return agohence(deltaseconds, 'minute', 60)
        else:
            return agohence(deltaseconds, 'second')

    if dom:
        return '<span id="count">0</span> <span id="unit">seconds</span> ago'
    else:
        return '0 seconds ago'


def font_family(font):
    families = {
        'Arial_Black': '"Arial Black", sans-serif',
        'Courier': '"Courier New", courier, monospace, sans-serif',
        'Georgia': 'georgia, "Times New Roman", times, serif',
        'Helvetica': 'helvetica, arial,  sans-serif',
        'Lucida_Grande': '"Lucida Grande", verdana, sans-serif',
        'Times': '"Times New Roman", times, serif',
        'Verdana': 'verdana, sans-serif'
    }

    if not families.has_key(font):
        font = 'Lucida_Grande'

    return families[font]

def rot13(s):
    table = string.maketrans(
      'nopqrstuvwxyzabcdefghijklmNOPQRSTUVWXYZABCDEFGHIJKLM',
      'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ')
    return s.translate(table)

def urlfilt(page_url):
    if page_url == '/':
        return lambda x: x[0] != '/'
    else:
        return lambda x: True

env_globals = dict(
    getattr = getattr,
    len = len,
    int = int,
    str = str,
    range = range,
    web = web,
    jt = jt,
    math = math,
    datestr = datestr,
    auth = auth,
    format = format,
    sanitize = sanitize,
    quote = quote,
    font_family = font_family,
    rot13 = rot13,
    urlfilt = urlfilt,
    realfilt = filter,
    Markup = Markup,
    page_title = utils.page_title,
    page_url = utils.page_url,
    site_url = utils.site_url
)

env.globals = env_atom.globals = env_globals
