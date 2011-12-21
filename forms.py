import re
import db, auth
from form import *
from dispatcher import jt

signin = Form(
    Password("password", markwrong=False, size=25, tabindex=1, description='Password'),
    Checkbox("remember", tabindex=3),
    Hidden("return_to")
)

def signin_processor(f, i):
    pwd_d = auth.digest(i.password)
    if pwd_d != jt.site.password:
        f.password.error('Oops, wrong password. Try again.')

signin.processor = signin_processor

settings = Form(
    Hidden("orig_url"),
    Textbox("title", size=30, id='_title', tabindex=1),
    Textbox("subtitle", size=30, id='_subtitle', tabindex=2),
    Textbox("email", size=30, tabindex=5),
    Radio("security", ['private', 'public', 'open'])
)

def settings_processor(f, i):
    # hack
    if not hasattr(i, 'email') or not hasattr(i, 'security'):
        return

    if i.security and not i.email:
        f.email.error('<strong>Email:</strong> Please specify an email address, so you can recover your password')
    if i.security and i.security not in ['private', 'public', 'open']:
        f.security.error('<strong>Kind of site:</strong> Please specify what kind of site you want')

settings.processor = settings_processor

claim_site = Form(
    Password("password", size=20, tabindex=1),
    Textbox("email", size=20, tabindex=2),
    Radio("security", ['private', 'public', 'open'])
)

def claim_site_processor(f, i):
    if not i.password:
        f.password.error('<strong>Password:</strong> please specify a password')
    if not i.password.strip():
        f.password.error('<strong>Password:</strong> please specify a password that isn\'t all spaces')
    if not i.email:
        f.email.error('<strong>Email:</strong> please specify an email address')
    elif not re.match(r'^[^@\s]+@([^.@\s]+\.)+[a-z]{2,}$', i.email):
        f.email.error('<strong>Email:</strong> please specify a valid email address')
    if not i.security:
        f.security.error('<strong>Kind of site:</strong> please specify what kind of site you want')

claim_site.processor = claim_site_processor

change_public_url = Form(
    Textbox("public_url", size=16, tabindex=1, autocomplete='off'),
)

def change_public_url_processor(f, i):
    RESERVED = ['www', 'internal', 'new']
    url = i.public_url.strip().lower()
    if url and url != jt.site.public_url:
        exists = db.get_site(public_url=url)
        if exists or url in RESERVED or len(url) < 3:
            f.public_url.error('error')
    if url and not re.match(r'^[a-zA-Z0-9-]+$', url):
        f.public_url.error('error')


change_public_url.processor = change_public_url_processor

change_password = Form(
    Password('current_password', size=18, tabindex=1),
    Password('new_password', size=18, tabindex=2)
)

def change_password_processor(f, i):
    pwd_d = auth.digest(i.current_password)
    if not i.current_password:
        f.current_password.error('Please specify the current password')
    elif pwd_d != jt.site.password:
        f.current_password.error('Current password is not correct')
    if not i.new_password:
        f.new_password.error('Please specify a new password')
    elif not i.new_password.strip():
        f.new_password.error('Please specify a new password that isn\'t all spaces')

change_password.processor = change_password_processor


recover_password = Form(
    Password('new_password', size=18, tabindex=1),
    Hidden('d')
)

def recover_password_processor(f, i):
    if not i.new_password:
        f.new_password.error('Please specify a new password')
    elif not i.new_password.strip():
        f.new_password.error('Please specify a new password that isn\'t all spaces')

recover_password.processor = recover_password_processor

find_sites = Form(
    Textbox('email', siz=28, tabindex=1),
    Hidden('sites')
)

def find_sites_processor(f, i):
    if not i.email:
        f.email.error('Please specify an email address')
    elif not re.match(r'^[^@\s]+@([^.@\s]+\.)+[a-z]{2,}$', i.email):
        f.email.error('Please specify a valid email address')

find_sites.processor = find_sites_processor
