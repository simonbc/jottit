import os, re, web

def markdown(text):
    i, o = os.popen2("php markdown/php-markdown")
    i.write(text); i.close()
    return o.read()
