import web, hmac

SECRET = "ofu889e4i5kfem"

def digest(*args):
    tmpargs = []
    for arg in args:
        if isinstance(arg, unicode): arg = str(arg)
        tmpargs.append(arg)
    args = tmpargs
    out = hmac.HMAC(SECRET, repr(args)).hexdigest()
    return out

def update():
    sites = web.select('sites')
    for s in sites:
        id = s.id
        pwd_d = digest(s.password)
        web.update('sites', where='id=$id', password=pwd_d, vars=locals())

if __name__ == '__main__':
    web.config.db_parameters = dict(dbn='postgres', user='jottit', pw='', db='jottit')
    web.load()
    update()
