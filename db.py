import web, random, difflib, time, re
import auth, utils
from diff import html2list
from dispatcher import jt

def get_sites(email):
    query = """SELECT   public_url,
                        secret_url,
                        title,
                        updated
               FROM     sites s
               WHERE    email = $email
               AND      deleted = false
               ORDER BY updated DESC"""
    sites = web.query(query, vars=locals())
    sites = list(sites)
    for s in sites:
        s.url = utils.site_url(s)

    out = web.utils.iterbetter(iter(sites))
    out.__len__ = len(sites)
    out.__list__ = sites
    return out

def new_site(content, scroll_pos, caret_pos, secret_url, public_url, partner):
    schemes = [('520000', 'fff', 'ffbfbf', 0, 214),
               ('523000', 'fff', 'ffe5bf', 25, 214),
               ('515200', 'fff', 'feffbf', 43, 214),
               ('2c5200', 'fff', 'e2ffbf', 62, 214),
               ('003452', 'fff', 'bfe8ff', 143, 214),
               ('001152', 'fff', 'bfcdff', 161, 214),
               ('4d0052', 'fff', 'fbbfff', 210, 214),
               ('520036', 'fff', 'ffbfe9', 227, 214),
               ('760000', 'fff', 'ffbfbf', 0, 196),
               ('764000', 'fff', 'ffe2bf', 23, 196),
               ('087600', 'fff', 'c4ffbf', 82, 196),
               ('004876', 'fff', 'bfe6ff', 144, 196),
               ('760043', 'fff', 'ffbfe3', 231, 196),
               ('92e600', '000', '3a5c00', 58, 140),
               ('d7ecff', '000', '003566', 148, 20),
               ('d8ffd7', '000', '026600', 84, 20),
               ('fcd7ff', '000', '5e0066', 209, 20),
               ('ffffd7', '000', '656600', 43, 20),
               ('ffd7d7', '000', '660000', 0, 20),
               ('d7fff9', '000', '006656', 121, 20),
               ('d7d7ff', '000', '000066', 170, 20)]

    def url_taken(url):
        return web.select('sites', where='public_url=$url or secret_url=$url', vars=locals())

    def create_url():
        def safe36(s):
            for c in '0o1li':
                if c in s:
                    return False
            return True
        s = '0'
        while not safe36(s):
            s = web.to36(random.randrange(50000, 60000000))
        return s

    if not secret_url:
        secret_url = create_url()
        while(url_taken(secret_url)):
            secret_url = create_url()

    header_color, title_color, subtitle_color, hue, brightness = schemes[random.randrange(0, len(schemes))]
    site_id = web.insert('sites', secret_url=secret_url, public_url=public_url, partner=partner)
    jt.site = web.select('sites', where='id=$site_id', vars=locals())[0]
    web.insert('designs', site_id=jt.site.id, title_font='Lucida_Grande', subtitle_font='Lucida_Grande', headings_font='Lucida_Grande', content_font='Lucida_Grande', header_color='#'+header_color, title_color='#'+title_color, subtitle_color='#'+subtitle_color, hue=hue, brightness=brightness)
    new_page('', content, scroll_pos, caret_pos)
    jt.site = get_site(id=site_id)

def get_site(**vars):
    try: web.query("COMMIT")
    except: pass
    web.query("SET statement_timeout = 6000")
    if vars is None: vars = {}
    vars = dict([(c, str(v)) for (c, v) in vars.items()])
    def pfix(s):
        if s == 'id': return 's.id'
        else: return s
    
    where_clause = ' AND '.join('%s = $%s' % (pfix(k), k) for k in vars.keys())

    query = """SELECT   s.*,
                        to_char(s.updated, 'YYYY-MM-DD"T"HH24:MI:SSZ') as atom_updated
               FROM     sites s
               WHERE    %s
               LIMIT 1
            """ % where_clause
    d = web.query(query, vars=vars)
    d = (d and d[0]) or None
    if d:
        d.url = utils.site_url(d)
    return d

def update_site(title, subtitle, email, security):
    site_id = jt.site.id
    web.update('sites', where='id=$site_id', title=title, subtitle=subtitle, email=email,
            security=security, vars=locals())
    jt.site.update({'title': title, 'subtitle': subtitle, 'email': email, 'security': security})

def change_public_url(url):
    url = url.strip()
    site_id = jt.site.id
    web.update('sites', where='id=$site_id', public_url=url, vars=locals())
    jt.site.public_url = url
    jt.site.url = utils.site_url(jt.site)

def change_password(password):
    pwd_d = auth.digest(password)
    site_id = jt.site.id
    web.update('sites', where='id=$site_id', password=pwd_d, vars=locals())
    jt.site.password = pwd_d

def change_pwd_token():
    d = auth.digest(auth.isodate()+jt.site.password)
    site_id = jt.site.id
    web.update('sites', where='id=$site_id', change_pwd_token=d, vars=locals())
    return d

def recover_password(password):
    pwd_d = auth.digest(password)
    site_id = jt.site.id
    web.update('sites', where='id=$site_id', change_pwd_token=None, password=pwd_d, vars=locals())
    jt.site.password = pwd_d


def delete_site():
    site_id = jt.site.id
    web.update('sites', where='id=$site_id', deleted=True, public_url='', vars=locals())

def claim_site(password, email, security):
    pwd_d = auth.digest(password)
    site_id = jt.site.id
    web.update('sites', where='id=$site_id', password=pwd_d, email=email, security=security, vars=locals())

def get_design():
    site_id = jt.site.id
    d = web.select('designs', where='site_id=$site_id', limit=1, vars=locals())
    return (d and d[0]) or None

def update_design(title_font, subtitle_font, headings_font, content_font, header_color, title_color, subtitle_color, title_size, subtitle_size, headings_size, content_size, hue, brightness):
    epoch = int(time.time())
    site_id = jt.site.id
    design = get_design()
    web.update('designs', where='site_id=$site_id', title_font=title_font, subtitle_font=subtitle_font, headings_font=headings_font, content_font=content_font, header_color=header_color, title_color=title_color, subtitle_color=subtitle_color, title_size=title_size, subtitle_size=subtitle_size, headings_size=headings_size, content_size=content_size, hue=hue, brightness=brightness, vars=locals())


def page_sort(x, y):
    # put home at top
    if x.title == 'Home': return -1
    if y.title == 'Home': return 1

    x = x.title.lower()
    y = y.title.lower()
    for i in xrange(min(len(x), len(y))):
        xres = re.match(r'(\d+)', x[i:])
        yres = re.match(r'(\d+)', y[i:])
        if xres and yres:
            c = cmp(int(xres.groups()[0]), int(yres.groups()[0]))
            if c: return c
        if xres:
            return -1
        if yres:
            return 1
        c = cmp(x[i], y[i])
        if c: return c
    if len(x) < len(y):
        return -1
    return 0

def get_page_export():
    site_id = jt.site.id
    query = """
        SELECT p.name,
               (SELECT content FROM revisions WHERE page_id=p.id ORDER BY created DESC LIMIT 1) as content,
               to_char(MAX(r.created), 'YYYY-MM-DD"T"HH24:MI:SSZ') as atom_created
        FROM   pages p,
               revisions r
        WHERE  p.site_id = $site_id
        AND    p.id = r.page_id
        AND    p.deleted = false
        AND    r.revision > 0
        GROUP BY p.id, p.name
        LIMIT 30
    """
    pages = web.query(query, vars=locals())
    pages_list = []
    for p in pages:
        p.title = utils.page_title(p.name)
        p.url = utils.page_url(p.name)
        pages_list.append(p)
    pages_list.sort(page_sort)
    out = web.utils.iterbetter(iter(pages_list))
    out.__len__ = len(pages_list)
    out.__list__ = pages_list
    return out

def get_pages():
    site_id = jt.site.id
    pages = web.select('pages', where='site_id=$site_id AND deleted=false', vars=locals())
    pages_list = []
    for p in pages:
        p.title = utils.page_title(p.name)
        p.url = utils.page_url(p.name)
        pages_list.append(p)
    pages_list.sort(page_sort)
    out = web.utils.iterbetter(iter(pages_list))
    out.__len__ = len(pages_list)
    out.__list__ = pages_list
    return out

def hide_primer():
    site_id = jt.site.id
    web.update('sites', where="id=$site_id", show_primer="f", vars=locals())

def get_num_revisions(page_name):
    page_name = page_name.lower()
    site_id = jt.site.id
    query = """SELECT count(*)
               FROM   revisions r,
	              pages p,
		      sites s
               WHERE  s.id = $site_id
	       AND    p.site_id = s.id
	       AND    r.page_id = p.id
               AND    r.revision > 0
               AND    lower(p.name) = $page_name"""
    d = web.query(query, vars=locals())
    return d[0].count

def get_draft(page_id):
     query = """SELECT   content
                FROM     drafts
                WHERE    page_id = $page_id
                ORDER BY created DESC
                LIMIT    1"""
     d = web.query(query, vars=locals())
     return (d and d[0]) or None

def get_page(page_name):
    page_name = page_name.lower()
    try:
        page_name.decode('utf8')
    except UnicodeDecodeError:
        return None
    site_id = jt.site.id
    query1 = """SELECT   p.*
               FROM     pages p,
                        sites s
               WHERE    s.id = $site_id
               AND      p.site_id = s.id
               AND      lower(p.name) = $page_name
               LIMIT 1"""
    d1 = web.query(query1, vars=locals())
    d1 = (d1 and d1[0]) or None
    if d1:
        query2 = """SELECT r.content,
        r.revision,
        r.changes,
        r.ip,
        r.created as updated,
        to_char(r.created, 'YYYY-MM-DD"T"HH24:MI:SSZ') as atom_updated
        FROM revisions r
        WHERE      r.page_id = $page_id
        AND      r.revision > 0
        ORDER BY r.revision DESC
        LIMIT 1"""
        d = web.query(query2, vars=dict(page_id=d1.id))
        d = (d and d[0]) or None
        
        if d:
            d1.update(d)
            d1.title = utils.page_title(d1.name)
            d1.url = utils.page_url(d1.name)
    return d1

def _format_changes(text, max=40):
    s = ''.join(text).strip()
    if len(s) > max:
        s = unicode(s, 'utf8')
        s = s[:max]
        s = s.strip()
        s = s+'...'
        s = s.encode('utf8')

    if not s: return 'whitespace'

    return '"<span class="src">%s</span>"' % web.htmlquote(s)

def new_page(name, content, scroll_pos=0, caret_pos=0):
    site = jt.site
    scroll_pos, caret_pos = web.intget(scroll_pos, 0), web.intget(caret_pos, 0)
    page_id = web.insert('pages', site_id=site.id, name=name, scroll_pos=scroll_pos, caret_pos=caret_pos)
    changes = '<em>Created page</em>'
    new_revision(page_id, 1, content, changes)

def update_caret_pos(page_id, scroll_pos=0, caret_pos=0):
    scroll_pos, caret_pos = web.intget(scroll_pos, 0), web.intget(caret_pos, 0)
    web.update('pages', where='id=$page_id', scroll_pos=scroll_pos, caret_pos=caret_pos, vars=locals())

def update_page(page_id, content, scroll_pos=0, caret_pos=0):
    latest = get_revision(page_id)
    revision = latest.revision+1
    update_caret_pos(page_id, scroll_pos, caret_pos)
    delete_draft(page_id);

    if content != latest.content:
        a, b = html2list(latest.content), html2list(content)
        s = difflib.SequenceMatcher(None, a, b)
        changes = ''
        for e in s.get_opcodes():
            if e[0] == "equal":
                continue
	    elif e[0] == "replace":
                changes = 'Changed '+_format_changes(a[e[1]:e[2]], 20)+' to '+_format_changes(b[e[3]:e[4]], 20)
	    elif e[0] == "delete":
                changes = 'Removed '+_format_changes(a[e[1]:e[2]])
                break
	    elif e[0] == "insert":
                changes = 'Added '+_format_changes(b[e[3]:e[4]])
                break
        new_revision(page_id, revision, content, changes)

def delete_page(page_id):
    latest = get_revision(page_id)
    content = ''
    changes = '<em>Page deleted.</em>'
    new_revision(page_id, latest.revision+1, content, changes)
    web.update('pages', where='id=$page_id', deleted=True, vars=locals())

def undelete_page(page_id, name):
    # we also update the name in case the user
    # deletes "foo" and re-creates it as "Foo",
    web.update('pages', where='id=$page_id', deleted=False, name=name, vars=locals())

def set_caret_pos(page_id, caret_pos, scroll_pos):
    scroll_pos, caret_pos = web.intget(scroll_pos, 0), web.intget(caret_pos, 0)
    web.update('pages', where='id=$page_id', caret_pos=caret_pos, scroll_pos=scroll_pos, vars=locals())

def get_revisions(page_id, start=None):
    query = """
        SELECT   r.*,
                 to_char(r.created, 'YYYY-MM-DD"T"HH24:MI:SSZ') as atom_created
        FROM     revisions r
        WHERE    r.page_id = $page_id
        AND      r.revision > 0
    """
    if start:
        query += "    AND r.revision < $start"
    query += """
        ORDER BY revision DESC
        LIMIT 20
    """
    return web.query(query, vars=locals())

def get_max_revisions(page_id):
    return web.query("select max(revision) as c from revisions where page_id = $page_id", vars=locals())[0].c

def get_revision(page_id, revision=None):
    if revision:
        try:
            revision = int(revision)
        except ValueError:
            return None
    if revision is not None:
        d = web.select('revisions', where='page_id=$page_id AND revision=$revision', limit=1, vars=locals())
    else:
        d = web.select('revisions', where='page_id=$page_id and revision > 0', order='revision DESC', limit=1, vars=locals())
    return (d and d[0]) or None

def new_revision(page_id, revision, content, changes):
    trimmed = content.strip()
    revision_id = web.insert('revisions', revision=revision, ip=web.ctx.ip, page_id=page_id, content=content, changes=changes)
    created = web.select('revisions', where='id=$revision_id', vars=locals())[0].created
    site_id = jt.site.id
    web.update('sites', where='id=$site_id', updated=created, vars=locals())


def delete_revision(page_id, revision):
    web.delete('revisions', where='page_id=$page_id AND revision=$revision', vars=locals())

def new_draft(page_id, content):
    exists = web.select('drafts', where='page_id=$page_id', vars=locals())
    if exists:
        web.update('drafts', where='page_id=$page_id', content=content, vars=locals())
    else:
        web.insert('drafts', page_id=page_id, content=content)

def delete_draft(page_id):
    web.delete('drafts', where='page_id=$page_id', vars=locals())

def get_draft(page_id):
    d = web.select('drafts', where='page_id=$page_id', limit=1, vars=locals())
    return (d and d[0]) or None

def get_changes():
    return [] # impossible query
    site_id = jt.site.id
    query = """
        SELECT   p.name,
                 p.deleted,
                 r.content,
                 r.revision,
                 r.changes,
                 r. created,
                 to_char(r.created, 'YYYY-MM-DD"T"HH24:MI:SSZ') as atom_created,
                 r.ip
        FROM     pages p,
                 revisions r
        WHERE    p.site_id = $site_id
        AND      p.id = r.page_id
        AND      r.revision > 0
        ORDER BY created DESC
        LIMIT 20
    """
    changes = web.query(query, vars=locals())

    changes_list = []
    for c in changes:
        c.title = utils.page_title(c.name)
        c.url = utils.page_url(c.name)
        changes_list.append(c)

    out = web.utils.iterbetter(iter(changes_list))
    out.__len__ = len(changes_list)
    out.__list__ = changes_list
    return out
