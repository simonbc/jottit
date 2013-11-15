import web, time, datetime, hmac, urllib, itertools, random
import db, forms, view
from dispatcher import jt

SECRET = "83me802jd7o88fdf"

def auth(method):
    if not jt.site.password:
        # site not claimed
        return True

    if jt.mode == 'site' and method in ['signin', 'signout', 'forgot_password', 'change_password']:
        return True

    if jt.site.security == 'open':
        if jt.mode == 'admin':
           return logged_in()
        return True

    if jt.site.security == 'public':
        if jt.mode == 'page':
            if method == 'view' and not web.input(r=None).r:
                return True
            elif method in ['datestr', 'history_atom']:
                return True
        elif method == 'changes_atom': return True

    return logged_in()

def logged_in():
    if web.cookies().has_key(jt.site.secret_url+'_admin_session'):
        session = web.cookies()[jt.site.secret_url+'_admin_session']
        try:
            signin_time,d  = session.split(',')
            return digest(jt.site.id, jt.site.password, signin_time) == d
        except:
            return False
    return False

def signin_required():
    f = forms.signin()
    return_to = web.lstrips(web.ctx.fullpath, '/')
    if not jt.site.public_url:
        return_to = web.lstrips(return_to, jt.site.secret_url+'/')
    f.fill(secret_url=jt.site.secret_url, return_to=return_to)
    page_title = 'Please enter the site-wide password'
    return view.render('signin', vars=locals())

def signin(password, remember=False):
    pwd_d = digest(password)
    t = isodate()
    d = digest(jt.site.id, pwd_d, t)
    #d = digest(jt.site.id, jt.site.password, t)
    text = "%s,%s" % (t, d)
    expires = (remember and 3600*24*30) or ""
    web.setcookie(jt.site.secret_url+"_admin_session", text, expires=expires)

def signout():
    web.setcookie(jt.site.secret_url+"_admin_session", "", expires=-1)

def spinner(page_name, otimestamp=None):
    if otimestamp is None: timestamp = int(time.time())
    else: timestamp = int(otimestamp)

    myspinner = digest(timestamp, '.'.join(web.ctx.ip.split('.')[:2]), page_name)

    if otimestamp:
        return myspinner
    else:
        return timestamp, myspinner, genspinfield(myspinner)

def unspuninput(page_name, *args, **kwargs):
    myspinner = web.input('spinner').spinner
    spinfield = genspinfield(myspinner)
    mapping = dict((spinfield(x), x) for x in args + tuple(kwargs.keys()) + ('timestamp',))
    i = web.input(
      *[spinfield(x) for x in args],
      **dict((spinfield(k), v) for k, v in kwargs.iteritems()))

    for k in ['s', 't']:
        for n in itertools.count():
            fn = 'honeypot_%s%s' % (k, n)
            if spinfield(fn) not in i: break
            mapping[spinfield(fn)] = fn

    newi = web.storage((mapping[k], v) for k, v in i.iteritems() if k in mapping)

    try:
        #assert myspinner == spinner(page_name, newi.timestamp)
        # (not using because we got some odd errors)
        assert int(newi.timestamp) < time.time()
        # assert int(i.timestamp) > (time.time() - 3600)
        # (not using yet because it causes usability loss)
        del newi['timestamp']
        for k in newi.copy():
            assert not k.startswith('honeypot_s')
            if k.startswith('honeypot_t'):
                assert newi[k] == ""
                del newi[k]
    except AssertionError:
        web.badrequest()
        raise StopIteration

    return newi

def genspinfield(spinner): return lambda x: digest(x, spinner)

def digest(*args):
    tmpargs = []
    for arg in args:
        if isinstance(arg, unicode): arg = str(arg)
        tmpargs.append(arg)
    args = tmpargs
    out = hmac.HMAC(SECRET, repr(args)).hexdigest()
    return out

def isodate():
    return datetime.datetime(*time.gmtime()[:6]).isoformat()
