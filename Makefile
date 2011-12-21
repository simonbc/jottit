all: ajs_minify unite minify_js minify_css

ajs_minify: 
	python ajs_minify.py -o javascripts/AJS-min.js javascripts/AJS.js

unite:
	python unite.py

minify_js:
	cat static/js-generated.js | python jsmin.py > static/js-min.js
	mv static/js-min.js static/js-generated.js

minify_css:
	python cssmin.py

clean:
	rm -f static/*.css static/*.js javascripts/AJS-min.js
