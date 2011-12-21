import web, difflib
from diff import html2list

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

def compute_changes(content, prev_content):
    a, b = html2list(prev_content), html2list(content)
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
    return changes

def cleanup():
    pages = web.select('pages')
    for p in pages:
        page_id = p.id
        revisions = web.select('revisions', where='page_id=$page_id', order='revision', vars=locals())
        prev = None
        for r in revisions:
            if prev:
                changes = compute_changes(r.content, prev.content)
            else:
                changes = "Added "+_format_changes(r.content)
            
            if changes != r.changes:
                print r.id, changes
                web.update('revisions', where='id=$r.id', changes=changes, vars=locals())
            prev = r

if __name__ == '__main__':
    web.config.db_parameters = dict(dbn='postgres', user='jottit', pw='', db='jottit')
    web.load()
    cleanup()
