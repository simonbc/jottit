import web, db


def cleanup():
    sites = db.get_site()
    for s in sites:
        site_id = s.id
        updated = s.updated
        print site_id, updated
        #web.update('site', where='id=$site_id', updated=updated, vars=locals())
        
        
if __name__ == '__main__':
    web.config.db_parameters = dict(dbn='postgres', user='jottit', pw='', db='jottit')
    web.load()
    cleanup()
