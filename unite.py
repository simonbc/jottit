import os

def unite(files, output_file):
  full_text = []
  for f in files:
    full_text.extend([l.lstrip() for l in open(f, "r").readlines()])
  open(output_file, "w").write("".join(full_text))

#Get full path
cwd = os.getcwd()
css = filter(lambda f: f.endswith('.css'),os.listdir('stylesheets'))
js = ['AJS-min.js', 'app.js', 'yahoo-dom-event.js', 'dragdrop.js',
        'slider.js', 'color.js', 'formatDate.js', 'showdown.js']
full_path_css = ["%s/stylesheets/%s" % (cwd, fp) for fp in css]
full_path_js = ["%s/javascripts/%s" % (cwd, fp) for fp in js]

#Minify and store
unite(full_path_css, "%s/static/css-generated.css" % cwd)
unite(full_path_js, "%s/static/js-generated.js" % cwd)
