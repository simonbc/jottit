import web, re
from dispatcher import jt, modes
from urllib import quote, unquote

def site_url(site=None):
    host = web.ctx.host.split(':')[0]
    if host.endswith('new.jottit.com'):
        domain = 'new.jottit.com:8090'
    elif host.endswith('lh.jottit.com'):
        domain = 'lh.jottit.com:8080'
    elif host.endswith('jottit'):
        domain = 'jottit:8080'
    elif host.endswith('jottit.herokuapp.com'):
        domain = 'jottit.herokuapp.com'
    else:
        domain = 'jottit.com'
    if web.ctx.env.get('HTTPS'): https = 's'
    else: https = ''
    site = site or jt.site
    if site.public_url:
        return 'http%s://%s.%s/' % (https, site.public_url, domain)
    else:
        return 'http%s://%s/%s/' % (https, domain, site.secret_url)

def page_title(page):
    if not page:
        return 'Home'

    title = re.sub(r'^('+'|'.join(modes.keys())+')_/(.*)$', r'\1/\2', page)
    title = title.replace('_', ' ')
    return title

def page_url(name):
    name = name.lower()
    name = name.replace(' ', '_')
    name = quote(name)
    return jt.site.url+name

def sendmail(frommail, to, subject, body):
    if not jt.testing:
        web.sendmail(frommail, to, subject, body)