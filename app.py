import web, re, time, os
import recaptcha.client.captcha as recaptcha
import db, forms, auth
from dispatcher import *
from diff import *
from view import *
from utils import *
from urllib import quote

class index(page):
    def GET(self):
        timestamp, spinner, spinfield = auth.spinner('front page')
        partner = web.input(partner='').partner
        render('front', vars=locals())

    def POST(self):
        i = auth.unspuninput('front page', 'content', 'scroll_pos', 'caret_pos',
          secret_url='', public_url='', partner='')
        db.new_site(**i)
        if i.public_url:
            web.seeother('/')
        else:
            web.seeother('/%s/' % jt.site.secret_url)

class feedback(page):
    def GET(self):
        render('feedback')

    def POST(self):
        i = web.input()
        frommail = i.email or 'unknown@jottit.com'
        body = i.content
        sendmail(frommail, 'Jottit Feedback <feedback@jottit.com>', "Feedback on Jottit", body)
        render('feedback_thanks')

class test(page):
    def GET(self):
        i = web.input()
        if i.get('crash'): crash
        import dispatcher, threading
        import os
        print web.ctx.environ
        print len(threading.enumerate()), ":", threading.enumerate()
        print
        print len(dispatcher._jt)
        print
        for x in dispatcher._jt.values():
            if not x: continue
            print time.time() - x.starttime, x.thepath,
            if 'site' not in x: print '...'
            elif not x.site: print 'None'
            else: print x.site.url

class sites(page):
    def GET(self):
        sites_sent = web.cookies(sites_sent=None).sites_sent
        web.setcookie('sites_sent', '', expires=-1)
        render('sites', vars=locals())

    def POST(self):
        i = web.input('email')
        f = forms.find_sites()
        sites = list(db.get_sites(i.email))
        if not f.validates() or not len(sites):
            f.fill(email=i.email)
            return render('sites', vars=locals())

        sites_list = ''
        for s in sites:
            site_url = s.url
            last_modified = datestr(s.updated, dom=False)
            if s.title:
                sites_list += '\n'+s.title

            sites_list += """
%(site_url)s
Last modified %(last_modified)s
""" % locals()
        sendmail('"Jottit.com" <feedback@jottit.com>', i.email, "Your Jottit sites", """\
Hi there. I believe you asked me to send you a list of your Jottit sites.
%(sites_list)s
Happy jotting!

 - Jottit
""" % locals())
        web.setcookie('sites_sent', "We've sent a list of your sites. Go check your email!")
        web.seeother('sites')

class about(page):
    def GET(self):
        render('about')

class help(page):
    def GET(self):
        render('help')

class page(mode):
    def GET_view(self, page_name=''):
        i = web.input(r='')
        page = db.get_page(page_name)
        if not page:
            web.ctx.status = '404 Not Found'
            return render('notfound', vars=locals())

        if page.deleted and not i.r:
            return render('deleted', vars=locals())

        if i.r:
            revision = db.get_revision(page.id, i.r)
            revisions = list(db.get_revisions(page.id))
            latest = revisions[0]
        else:
            latest = revision = db.get_revision(page.id)

        if not revision:
            return web.badrequest()

        success = web.cookies(success=None).success
        web.setcookie('success', '', expires=-1)

        render('view_page', vars=locals())

    def GET_edit(self, page_name=''):
        page = db.get_page(page_name)
        timestamp, spinner, spinfield = auth.spinner(page_name)
        if page:
            revision = db.get_revision(page.id)
	    draft = db.get_draft(page.id)
            content = (draft and draft.content) or revision.content
        render('edit_page', vars=locals())

    def POST_edit(self, page_name=''):
        i = web.input('spinner', recaptcha=False)
        spinner, recaptcha_p = i.spinner, i.recaptcha
        error_to_use = None
        if recaptcha_p:
            c = recaptcha.submit(i.recaptcha_challenge_field, i.recaptcha_response_field, os.environ['RECAPTCHA_PRIVKEY'], web.ctx.ip)
            if not c.is_valid: error_to_use = c.error_code
        i = auth.unspuninput(page_name, 'content', 'scroll_pos', 'caret_pos',
          'current_revision', save=False, delete=False)
        page = db.get_page(page_name)
        content = re.sub(r'(\r\n|\r)', '\n', i.content)
        if (jt.site.security=='open' and not auth.logged_in()) and (not recaptcha_p or error_to_use):
            captcha = recaptcha.displayhtml(os.environ['RECAPTCHA_PUBKEY'], use_ssl=True, error=error_to_use)
            timestamp, spinner, spinfield = auth.spinner(page_name)
            return render('captcha', vars=locals())
        if not page:
            db.new_page(page_name, content, i.scroll_pos, i.caret_pos)
            page = db.get_page(page_name)

        revision = db.get_revision(page.id)
        if i.current_revision and revision.revision != int(i.current_revision) and not page.deleted and revision.content != content:
            timestamp, spinner, spinfield = auth.spinner(page_name)
            orig = db.get_revision(page.id, i.current_revision)
            diff = better_diff(orig.content, content)
            return render('edit_conflict', vars=locals())

        if i.delete and page_name:
            db.delete_page(page.id)
            return web.seeother(page.url)

        db.update_page(page.id, content, i.scroll_pos, i.caret_pos)
        if page.deleted:
            db.undelete_page(page.id, page_name)

        web.seeother(page.url)

    def GET_delete(self, page_name=''):
        if page_name == '': return web.badrequest()
        page = db.get_page(page_name)
        render('delete_page', vars=locals())

    def POST_delete(self, page_name=''):
        if page_name == '': return web.badrequest()
        page = db.get_page(page_name)
        db.delete_page(page.id)
        return web.seeother(page.url)

    def POST_cancel(self, page_name=''):
        i = web.input('scroll_pos', 'caret_pos')
        page = db.get_page(page_name)
        if page:
            db.update_caret_pos(page.id, i.scroll_pos, i.caret_pos)
            db.delete_draft(page.id)

    def GET_create(self, page_name=''):
        i = web.input('name')
        web.seeother('%s?m=edit' % i.name)

    def POST_current_revision(self, page_name=''):
        page = db.get_page(page_name)
        if page:
            revision = db.get_revision(page.id)
            serialize_json(revision=revision.revision)

    def POST_create(self, page_name=''):
        i = web.input('content', 'scroll_pos', 'caret_pos')
        page = db.get_page(page_name)
        if page:
            if page.deleted:
                db.undelete_page(page.id, page_name)
            db.update_page(page.id, i.content, i.scroll_pos, i.caret_pos)
        else:
            db.new_page(page_name, i.content, i.scroll_pos, i.caret_pos)
            page = db.get_page(page_name)
        web.seeother(page.url)

    def GET_history(self, page_name=''):
        page = db.get_page(page_name)
        max_revision = db.get_max_revisions(page.id)
        if not (page and max_revision):
            return web.seeother(jt.site.url+page_name)

        try: start = int(web.input(start=0).start)
        except: start = 0
        revisions = list(db.get_revisions(page.id, start=max_revision-start))
        pagination_end = min(11+start/10, int(math.ceil((max_revision+10)/10.0)))
        pagination_start = (pagination_end < 21 and 1 or pagination_end-20)

        latest = db.get_revision(page.id)
        render('history', vars=locals())

    def GET_history_atom(self, page_name=''):
        page = db.get_page(page_name)
        if not page:
            return web.seeother(jt.site.url+page_name)

        revisions = list(db.get_revisions(page.id))[:10]
        names = []
        render_atom('history', vars=locals())

    def POST_revert(self, page_name=''):
        page = db.get_page(page_name)
        if not page:
            return web.badrequest()

        i = web.input('r')
        revert_to = db.get_revision(page.id, i.r)
        if not revert_to:
            return web.badrequest()

        if page.deleted:
            db.undelete_page(page.id, page_name)

        latest = db.get_revision(page.id)
        if latest.content != revert_to.content:
            db.update_page(page.id, revert_to.content)
        web.seeother(page.url)

    def GET_diff(self, page_name=''):
        page = db.get_page(page_name)
        if not page:
            return web.seeother('/')
        i = web.input(r=[])
        if len(i.r) == 0:
	    ia = db.get_num_revisions(page_name)
            ib = max(ia - 1, 1)
        elif len(i.r) == 1:
            ia = int(i.r[0])
            if ia == 1: ib = 1
            else: ib = ia - 1
        elif len(i.r) == 2:
            ia, ib = i.r
            try:
                ia, ib = int(ia), int(ib)
            except ValueError:
                return web.badrequest()
        else:
            return web.badrequest()

        if ia > ib:
            # get ordering right
            ib, ia = ia, ib
        a = db.get_revision(page.id, ia)
        b = db.get_revision(page.id, ib)
        if not a or not b:
            return web.badrequest()

        nextrev, prevrev = '', '' # jinja doesn't like None
        if ia > 1:
            prevrev = str(ia - 1)
        if db.get_revision(page.id, ib + 1):
            nextrev = str(ib + 1)

        diff = better_diff(a.content, b.content)
        revisions = list(db.get_revisions(page.id))
        render('diff', vars=locals())

    def POST_undelete(self, page_name=''):
        page = db.get_page(page_name)
        if not page:
            return web.badrequest()

        db.undelete_page(page.id, page_name)
        latest = db.get_revision(page.id)
        deleted_rev = db.get_revision(page.id, latest.revision-1)
        db.new_revision(page.id, latest.revision+1, deleted_rev.content, '<em>Delete undone.</em>')
        web.seeother(page.url)

    def POST_datestr(self, page_name=''):
        page = db.get_page(page_name)
        if not page:
            return web.badrequest()

        revision = db.get_revision(page.id)
        d = datestr(revision.created)
        serialize_json(datestr=d)

class draft(mode):
    def POST_save(self):
        i = web.input('page_name', 'content')
        page = db.get_page(i.page_name)
        if page:
            db.new_draft(page.id, i.content)

    def POST_delete(self):
        i = web.input('page_name')
        page = db.get_page(i.page_name)
        if page:
            db.delete_draft(page.id)

    def POST_recover_live_version(self):
        i = web.input('page_name')
        page = db.get_page(i.page_name)
        if page:
            rev = db.get_revision(page.id)
            db.delete_draft(page.id)
            serialize_json(content=rev.content)

class site(mode):
    def POST_hide_primer(self):
        db.hide_primer()

    def GET_claim(self):
        if jt.site.password:
            return web.seeother(jt.site.url)

	f = forms.claim_site()
        render('claim_site', vars=locals())

    def POST_claim(self):
        if jt.site.password:
            return web.seeother(jt.site.url)

        i = web.input(password='')
        f = forms.claim_site()
        f.fill(password=i.password)
        render('claim_site', vars=locals())

    def POST_do_claim(self):
        if jt.site.password:
            return web.seeother(jt.site.url)

        i = web.input('password', 'email', 'security')
        f = forms.claim_site()
        if not f.validates():
            return render('claim_site', vars=locals())

        db.claim_site(i.password, i.email, i.security)
        auth.signin(i.password)
        web.setcookie('success', "Congratulations! You've claimed your site.")
        site_url = web.rstrips(web.lstrips(web.lstrips(jt.site.url, 'http://'), 'https://'), '/')
        sendmail('The Jottit Team <feedback@jottit.com>', i.email, "You claimed " + site_url, """\
Thanks for claiming your site at Jottit.com! It's at:

https://%(site_url)s
recover password: https://%(site_url)s/site/forgot-password

Let us know if you have any thoughts or problems -- just
reply to this email (or email feedback@jottit.com).

 - Simon and Aaron, Jottit
""" % dict(
  email=i.email,
  site_url=site_url,
  password=i.password))
        return web.seeother(jt.site.url)

    def GET_signin(self):
        if not jt.site.password:
            return web.seeother(jt.site.url)

        i = web.input(return_to='')
        return_to = quote(i.return_to)
        f = forms.signin()
        f.fill(secret_url=jt.site.secret_url, return_to=return_to)
        password_sent = web.cookies().has_key('password_sent')
        web.setcookie('password_sent', '', expires=-1)
        web.header('Pragma', 'no-cache')
        render('signin', vars=locals())

    def POST_signin(self):
        if not jt.site.password:
            return web.seeother(jt.site.url)

        i = web.input('password', 'return_to', remember=False)
        f = forms.signin()
        if not f.validates():
            f.fill(remember=i.remember, return_to=i.return_to)
            return render('signin', vars=locals())

        auth.signin(i.password, i.remember)
        return web.seeother(jt.site.url+i.return_to)

    def POST_signout(self):
        auth.signout()
        i = web.input(return_to='')
        return web.seeother(jt.site.url+i.return_to)

    def GET_forgot_password(self):
        if not jt.site.password:
            return web.seeother(jt.site.url)
        render('forgot_password', vars=locals())

    def POST_forgot_password(self):
        if not jt.site.password:
            return web.seeother(jt.site.url)
        toemail = jt.site.email
        d = db.change_pwd_token()
        change_url = jt.site.url+'site/change-password?d='+d
        forgot_url = jt.site.url+'site/forgot-password'
        sendmail('"Jottit.com" <feedback@jottit.com>', toemail, "Password to your Jottit site", """\
Hi there. I believe you asked me to let you change the password to your Jottit site. If it wasn't you, don't worry, I haven't changed anything.

Visit this page to change it:

%(change_url)s

For security reasons it will only work once. To change it again, visit

%(forgot_url)s

Happy jotting!

 - Jottit
""" % locals())
        web.setcookie('password_sent', '')
        web.seeother('signin')

    def GET_change_password(self):
        i = web.input('d')
        if i.d != jt.site.change_pwd_token or not jt.site.change_pwd_token:
            return web.seeother(jt.site.url)

        f = forms.recover_password()
        f.fill(d=i.d)
        render('recover_password', vars=locals())

    def POST_change_password(self):
        i = web.input('d', new_password='')
        if i.d != jt.site.change_pwd_token:
            return web.badrequest()

        f = forms.recover_password()
        if not f.validates():
            return render('recover_password', vars=locals())

        db.recover_password(i.new_password)
        auth.signin(i.new_password)
        web.seeother(jt.site.url)

    def GET_changes(self):
        i = web.input(limit=None)
        changes = db.get_changes()
        changes = list(changes)

        try: start = int(web.input(start=0).start)
        except: start = 0
        pagination_end = min(11+start/10, int(math.ceil((len(changes)+10)/10.0)))
        pagination_start = (pagination_end < 21 and 1 or pagination_end-20)

        render('changes', vars=locals())

    def GET_changes_atom(self):
        changes = list(db.get_changes())[:20]
        names = []
        render_atom('changes', vars=locals())

class admin(mode):
    def GET_settings(self):
        site = jt.site
        f = forms.settings()
        f.fill(title=site.title, subtitle=site.subtitle, public_url=site.public_url, email=site.email, security=site.security)

        page_title = 'Settings'
        render('settings', vars=locals())

    def POST_settings(self):
        i = web.input('title', 'subtitle', email='', security='')
        f = forms.settings()
        if f.validates():
            db.update_site(i.title, i.subtitle, i.email, i.security)
        return web.seeother(jt.site.url)

    def POST_url_available(self):
        RESERVED = ['www', 'internal', 'new', 'signin']
        i = web.input('url')
        exists = (i.url in RESERVED) or db.get_site(public_url=i.url)
        serialize_json(available=(exists is None))

    def GET_delete(self):
        render('delete_site')

    def POST_delete(self):
        db.delete_site()
        web.seeother('http://jottit.com')

    def GET_design(self):
        site = jt.site
        render('design', vars=locals())

    def POST_design(self):
        i = web.input('title_font', 'subtitle_font', 'headings_font', 'content_font', 'header_color', 'title_color', 'subtitle_color', 'title_size', 'subtitle_size', 'headings_size', 'content_size', 'hue', 'brightness')
        db.update_design(i.title_font, i.subtitle_font, i.headings_font, i.content_font, i.header_color, i.title_color, i.subtitle_color, i.title_size, i.subtitle_size, i.headings_size, i.content_size, i.hue, i.brightness)

    def GET_change_site_address(self):
        f = forms.change_public_url()
        f.fill(public_url=jt.site.public_url)
        render('change_public_url', vars=locals())

    def POST_change_site_address(self):
        url = web.input('public_url').public_url.strip().lower()
        f = forms.change_public_url()
        if not f.validates():
            f = forms.change_public_url()
            f.fill(public_url=url)
            return render('change_public_url', vars=locals())

        if url == jt.site.public_url:
             return web.seeother('settings')
        db.change_public_url(url)
        auth.signout()
        web.seeother(jt.site.url+'admin/settings')

    def GET_change_password(self):
        f = forms.change_password()
        render('change_password', vars=locals())

    def POST_change_password(self):
        i = web.input('current_password', 'new_password')
        f = forms.change_password()
        if not f.validates():
            current = (not f.current_password.errors and i.current_password or '')
            new = (not f.new_password.errors and i.new_password or '')
            f.fill(current_password=current, new_password=new)
            return render('change_password', vars=locals())

        db.change_password(i.new_password)
        auth.signin(i.new_password)
        web.seeother('settings')

    def GET_export(self):
        return web.badrequest()
    def GET_export_ks9a8usijo(self):
        updated = time.strftime('%Y-%m-%dT%H:%M:%SZ')
        pages = db.get_page_export()
        web.ctx.headers = [('Content-Type', 'application/force-download')]
        web.ctx.headers = [('Content-Disposition', 'attachment; filename=%s' % 'export.xml')]
        render_atom('export', vars=locals())

def internalerror():
    web.ctx.status = "500 Internal Server Error"
    web.ctx.headers = [('Content-Type', 'text/html')]
    web.ctx.output = file('templates/internalerror.html').read()
web.webapi.internalerror = internalerror

def badrequest(msg=None):
    web.ctx.status = '400 Bad Request'
    web.ctx.headers = [('Content-Type', 'text/html')]
    web.ctx.output = msg or file('templates/badrequest.html').read()
web.badrequest = badrequest

def forbidden():
    web.ctx.status = '403 Forbidden'
    web.ctx.headers = [('Content-Type', 'text/html')]
web.forbidden = forbidden

urls =  (
    '/(.*)', 'disp',
)

class disp:
    GET = POST = lambda self, path: dispatch(path)

if __name__ == "__main__":
    #web.webapi.internalerror = emailerrors('feedback@jottit.com', web.webapi.internalerror)
    #web.webapi.internalerror = web.debugerror
    tmpdb = dburl2dict(os.environ['DATABASE_URL'])
    tmpdb.update(dict(maxcached=20, maxconnections=80, blocking=True))
    web.config.db_parameters = tmpdb
    web.run(urls, globals())
