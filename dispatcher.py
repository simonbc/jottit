import web, threading
from blocked_sites import blocked_sites

_jt = {threading.currentThread(): web.Storage()}
jt = web.utils.threadeddict(_jt)

modes = {}
pages = {}

import re, mimetypes, time
import db, view, auth, utils


class metamode (type):
    def __init__(cls, *a, **kw):
        type.__init__(cls, *a, **kw)
        modes[cls.__name__] = cls

class mode:
    __metaclass__ = metamode

class metapage (type):
    def __init__(cls, *a, **kw):
        type.__init__(cls, *a, **kw)
        pages[cls.__name__] = cls

class page:
    __metaclass__ = metapage

del modes['mode']
del pages['page']

def dispatch(path):
    _jt[threading.currentThread()] = web.Storage()
    web.header('Strict-Transport-Security', 'max-age=16070400; includeSubDomains')
    if web.ctx.env.get('HTTP_X_FORWARDED_FOR'):
        web.ctx.ip = web.ctx.env['HTTP_X_FORWARDED_FOR'].split(',')[0]
    
    try:
        jt.starttime = time.time()
        jt.thepath = web.ctx.home + web.ctx.fullpath
        if not web.ctx.host:
            del _jt[threading.currentThread()]
            return web.badrequest()

        host = web.lstrips(web.ctx.host.split(':')[0], 'www.').lower() # remove port
        if host in blocked_sites: return web.seeother('http://education.apwg.org/r/en/')
        TESTING_SITES = ['lh.jottit.com', 'jottit']
        jt.testing = (host in TESTING_SITES)

        # static files
        if jt.testing:
            res = re.match(r'^(static|javascripts|stylesheets)/([^?]+)(?:\?.*)?', path)
        else:
            res = re.match(r'^(static)/([^?]+)(?:\?.*)?', path)
        if res:
            dir, file = res.groups()
            out = _get_static_resource(dir, file)
            del _jt[threading.currentThread()]
            return out
        elif path == 'favicon.ico':
            out = _get_static_resource('static', 'favicon.ico')
            del _jt[threading.currentThread()]
            return out

        jt.site = None
        if (host in ['jottit.com', 'new.jottit.com', 'jottit.herokuapp.com'] + TESTING_SITES):
            if '/' not in path:
                if not path: path = 'index'
                try:
                    func = pages[path]()
                except KeyError:
                    # it might be secret_url with a
                    # missing '/' at the end
                    del _jt[threading.currentThread()]
                    return web.seeother(path+'/')

                webmeth = web.ctx.method
                if webmeth == "HEAD" and not hasattr(func, webmeth):
                    webmeth = "GET"
                out = getattr(func, webmeth)()
            else:
                out = dispatch_secret(path)
            del _jt[threading.currentThread()]
            return out

        res = re.match(r'([^\.]+)\.jottit.com', host)
        res = res or re.match(r'([^\.]+)\.lh\.jottit\.com', host)
        res = res or re.match(r'([^\.]+)\.jottit\.herokuapp\.com', host)
        if res:
            url = res.groups()[0]
            out = dispatch_public(url, path)
            del _jt[threading.currentThread()]
            return out

        del _jt[threading.currentThread()]
        return web.badrequest()
    finally:
        if threading.currentThread() in _jt:
            del _jt[threading.currentThread()]

def dispatch_public(url, path):
    jt.access = 'public'

    # modes
    res = re.match(r'^('+'|'.join(modes.keys())+')/([^/]*)$', path)
    if res:
        mode, method = res.groups()
        jt.site = db.get_site(public_url=url)
        if not jt.site or jt.site.deleted:
            return no_site(url)

        return dispatch_mode(mode, method)

    # pages
    jt.site = db.get_site(public_url=url)
    if not jt.site or jt.site.deleted:
        return no_site(url)

    page = path
    if page != page.replace(' ', '_'):
        return web.seeother(utils.page_url(page)+web.ctx.query)

    return dispatch_page(page)

def dispatch_secret(path):
    jt.access = 'secret'

    # modes
    res = re.match(r'^([^/]+)/('+'|'.join(modes.keys())+')/([^/]*)$', path)
    if res:
        url, mode, method = res.groups()
        jt.site = db.get_site(secret_url=url)
        if not jt.site or jt.site.deleted:
            return no_site(url)

        if jt.site.public_url:
            return web.seeother(utils.site_url()+mode+'/'+method)

        return dispatch_mode(mode, method)

    # pages
    res = re.match(r'^([^/]+)/(.*)', path)
    if res:
        url, page = res.groups()
        # make all secret urls lowercase
        if not url.islower():
            return web.seeother('/%s/%s' % (url.lower(), page))

        jt.site = db.get_site(secret_url=url)
        if not jt.site or jt.site.deleted:
            return no_site(url)

        if page != page.replace(' ', '_'):
            return web.seeother(utils.page_url(page)+web.ctx.query)

        if jt.site.public_url:
            return web.seeother(utils.site_url()+page)

        return dispatch_page(page)

    return web.notfound()

def dispatch_mode(mode, method):
    m = re.sub(r'[\-\.]', '_', method)
    jt.update({'mode': mode, 'method': m})

    if not auth.auth(m):
        return auth.signin_required()

    mode = modes[mode]()
    m = (m and '_'+m) or ''
    webmeth = web.ctx.method

    if webmeth == "HEAD" and not hasattr(mode, webmeth + method):
        webmeth = "GET"

    m = webmeth + m

    if not hasattr(mode, m):
        return web.seeother('%s%s_/%s' % (jt.site.url, type(mode).__name__, method))

    return getattr(mode, m)()

def dispatch_page(page):
    if page == 'home': page = ''

    m = web.input().get('m', 'view')
    m = re.sub(r'[\-\.]', '_', m)
    jt.update({'mode': 'page', 'method': m})
    if not auth.auth(m):
        return auth.signin_required()

    mode = modes['page']()
    m = web.ctx.method+'_'+m
    if not hasattr(mode, m):
        return web.badrequest()

    if page:
        return getattr(mode, m)(page)
    else:
        return getattr(mode, m)()

def no_site(url):
    if not jt.site:
        return site_not_found(url)
    else:
        return site_deleted()

def site_not_found(url):
    def is_safe(url):
        import string
        SAFE = string.digits+string.letters+'_~-'

        for c in url:
            if c not in SAFE:
                 return False
        return True

    if len(url) < 3 or not is_safe(url):
        return web.seeother('http://jottit.com')

    if web.ctx.method == 'POST' and web.ctx.path == '/':
        mode = pages['index']()
        return getattr(mode, 'POST')()

    timestamp, spinner, spinfield = auth.spinner('front page')
    public_url = secret_url = ''
    if jt.access == 'public':
        public_url = url
    else:
        secret_url = url

    web.ctx.status = '404 Not Found'
    return view.render('site_not_found', vars=locals())

def site_deleted():
    web.ctx.status = '404 Gone' # lighttpd doesn't like 410s
    return view.render('site_deleted', vars=locals())

def _mime_type(filename):
    return mimetypes.guess_type(filename)[0] or 'application/octet-stream'

def _get_static_resource(dir, file):
    try:
        web.header('Content-type', _mime_type(file))
        f = open(dir+'/'+file, 'rb')
        web.ctx.output = f.read()
        f.close()
    except IOError:
        web.notfound()

