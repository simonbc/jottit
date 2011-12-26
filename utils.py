import web, re, sys, traceback
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
    if web.ctx.env.get('HTTPS') or web.ctx.env.get('HTTP_X_FORWARDED_PROTO')=='https':
        https = 's'
    else:
        https = ''
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

import os
if os.environ.get('SENDGRID_USERNAME'):
    web.config.smtp_server = 'smtp.sendgrid.net'
    web.config.smtp_port = 587
    web.config.smtp_username = os.environ['SENDGRID_USERNAME']
    web.config.smtp_password = os.environ['SENDGRID_PASSWORD']
    web.config.smtp_starttls = True

import sendmail as sendmailmod
def sendmail(frommail, to, subject, body):
    if not jt.testing:
        sendmailmod.sendmail(frommail, to, subject, body)

def emailerrors(email_address, olderror):
    """
    Wraps the old `internalerror` handler (pass as `olderror`) to 
    additionally email all errors to `email_address`, to aid in 
    debugging production websites.
    
    Emails contain a normal text traceback as well as an
    attachment containing the nice `debugerror` page.
    """
    def emailerrors_internal():
        olderror()
        tb = sys.exc_info()
        error_name = tb[0]
        error_value = tb[1]
        tb_txt = ''.join(traceback.format_exception(*tb))
        path = web.ctx.path
        request = web.ctx.method+' '+web.ctx.home+web.ctx.fullpath
        eaddr = email_address
        text = ("""\
------here----
Content-Type: text/plain
Content-Disposition: inline

%(request)s

%(tb_txt)s

------here----
Content-Type: text/html; name="bug.html"
Content-Disposition: attachment; filename="bug.html"

""" % locals()) + str(web.djangoerror())
        sendmail(
          "your buggy site <%s>" % eaddr,
          "the bugfixer <%s>" % eaddr,
          "bug: %(error_name)s: %(error_value)s (%(path)s)" % locals(),
          text, 
          headers={'Content-Type': 'multipart/mixed; boundary="----here----"'})
    
    return emailerrors_internal
