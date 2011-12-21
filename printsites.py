import sys
import web
import db

web.config.db_parameters = dict(dbn='postgres', user='jottit', pw='', db='jottit')
web.load()
web.ctx.host = 'jottit.com'
web.ctx.env = web.storage()

for site in db.get_sites(sys.argv[1]):
    print site.url

