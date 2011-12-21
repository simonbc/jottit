//AJS JavaScript library (minify'ed version)
//Copyright (c) 2006 Amir Salihefendic. All rights reserved.
//Copyright (c) 2005 Bob Ippolito. All rights reserved.
//License: http://www.opensource.org/licenses/mit-license.php
//Visit http://orangoo.com/AmiNation/AJS for full version.
AJS = {
BASE_URL: "",
drag_obj: null,
drag_elm: null,
_drop_zones: [],
_cur_pos: null,

preventDefault: function(e) {
if(AJS.isIe()) 
window.event.returnValue = false;
else {
e.preventDefault();
}
},
getScrollTop: function() {
//From: http://www.quirksmode.org/js/doctypes.html
var t;
if (document.documentElement && document.documentElement.scrollTop)
t = document.documentElement.scrollTop;
else if (document.body)
t = document.body.scrollTop;
return t;
},
getRequest: function(url, data, type) {
if(!type)
type = "POST";
var req = AJS.getXMLHttpRequest();
if(url.match(/^https?:\/\//) == null) {
if(AJS.BASE_URL != '') {
if(AJS.BASE_URL.lastIndexOf('/') != AJS.BASE_URL.length-1)
AJS.BASE_URL += '/';
url = AJS.BASE_URL + url;
}
}
req.open(type, url, true);
if(type == "POST")
req.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
return AJS._sendXMLHttpRequest(req);
},
nodeName: function(elm) {
return elm.nodeName.toLowerCase();
},
setStyle: function(/*elm1, elm2..., property, new_value*/) {
var args = AJS.forceArray(arguments);
var new_val = args.pop();
var property = args.pop();
AJS.map(args, function(elm) { 
elm.style[property] = AJS.getCssDim(new_val);
});
},
extend: function(members) {
var parent = new this('no_init');
for(k in members) {
var prev = parent[k];
var cur = members[k];
if (prev && prev != cur && typeof cur == 'function') {
cur = this._parentize(cur, prev);
}
parent[k] = cur;
}
return new AJS.Class(parent);
},
loadJSONDoc: function(url) {
var d = AJS.getRequest(url);
var eval_req = function(data, req) {
var text = req.responseText;
if(text == "Error")
d.errback(req);
else
return AJS.evalTxt(text);
};
d.addCallback(eval_req);
return d;
},
setHTML: function(elm, html) {
elm.innerHTML = html;
return elm;
},
evalTxt: function(txt) {
try {
return eval('('+ txt + ')');
}
catch(e) {
return eval(txt);
}
},
getWindowSize: function(doc) {
doc = doc || document;
var win_w, win_h;
if (self.innerHeight) {
win_w = self.innerWidth;
win_h = self.innerHeight;
} else if (doc.documentElement && doc.documentElement.clientHeight) {
win_w = doc.documentElement.clientWidth;
win_h = doc.documentElement.clientHeight;
} else if (doc.body) {
win_w = doc.body.clientWidth;
win_h = doc.body.clientHeight;
}
return {'w': win_w, 'h': win_h};
},
addClass: function(/*elm1, elm2..., className*/) {
var args = AJS.forceArray(arguments);
var cls = args.pop();
var add_class = function(o) {
if(!new RegExp("(^|\\s)" + cls + "(\\s|$)").test(o.className))
o.className += (o.className ? " " : "") + cls;
};
AJS.map(args, function(elm) { add_class(elm); });
},
exportToGlobalScope: function(scope) {
scope = scope || window;
for(e in AJS)
scope[e] = AJS[e];
},
hasClass: function(elm, cls) {
if(!elm.className)
return false;
return elm.className == cls || 
elm.className.search(new RegExp(" " + cls + "|^" + cls)) != -1
},
_sendXMLHttpRequest: function(req, data) {
var d = new AJSDeferred(req);
var onreadystatechange = function () {
if (req.readyState == 4) {
var status = '';
try {
status = req.status;
}
catch(e) {};
if(status == 200 || status == 304 || req.responseText == null) {
d.callback();
}
else {
if(d.errbacks.length == 0) {
if(AJS.ajaxErrorHandler)
AJS.ajaxErrorHandler(req.responseText, req);
}
else 
d.errback();
}
}
}
req.onreadystatechange = onreadystatechange;
return d;
},
_nodeWalk: function(elm, tag_name, class_name, fn_next_elm) {
var p = fn_next_elm(elm);
var checkFn;
if(tag_name && class_name) {
checkFn = function(p) {
return AJS.nodeName(p) == tag_name && AJS.hasClass(p, class_name);
}
}
else if(tag_name) {
checkFn = function(p) { return AJS.nodeName(p) == tag_name; }
}
else {
checkFn = function(p) { return AJS.hasClass(p, class_name); }
}
while(p) {
if(checkFn(p))
return p;
p = fn_next_elm(p);
}
return null;
},
callback: function () {
this.excCallbackSeq(this.req, this.callbacks);
},
isFunction: function(obj) {
return (typeof obj == 'function');
},
isSafari: function() {
return (navigator.userAgent.toLowerCase().indexOf("khtml") != -1);
},
_unloadListeners: function() {
if(AJS.listeners)
AJS.map(AJS.listeners, function(elm, type, fn) { AJS.REV(elm, type, fn) });
AJS.listeners = [];
},
join: function(delim, list) {
try {
return list.join(delim);
}
catch(e) {
var r = list[0] || '';
AJS.map(list, function(elm) {
r += delim + elm;
}, 1);
return r + '';
}
},
getParentBytc: function(elm, tag_name, class_name) {
return AJS._nodeWalk(elm, tag_name, class_name, function(m) { return m.parentNode; });
},
getIndex: function(elm, list/*optional*/, eval_fn) {
for(var i=0; i < list.length; i++)
if(eval_fn && eval_fn(list[i]) || elm == list[i])
return i;
return -1;
},
isIn: function(elm, list) {
var i = AJS.getIndex(elm, list);
if(i != -1)
return true;
else
return false;
},
isArray: function(obj) {
return obj instanceof Array;
},
appendChildNodes: function(elm/*, elms...*/) {
if(arguments.length >= 2) {
AJS.map(arguments, function(n) {
if(AJS.isString(n))
n = AJS.TN(n);
if(AJS.isDefined(n))
elm.appendChild(n);
}, 1);
}
return elm;
},
getElementsByTagAndClassName: function(tag_name, class_name, /*optional*/ parent, first_match) {
var class_elements = [];
if(!AJS.isDefined(parent))
parent = document;
if(!AJS.isDefined(tag_name))
tag_name = '*';
var els = parent.getElementsByTagName(tag_name);
var els_len = els.length;
var pattern = new RegExp("(^|\\s)" + class_name + "(\\s|$)");
for (i = 0, j = 0; i < els_len; i++) {
if ( pattern.test(els[i].className) || class_name == null ) {
class_elements[j] = els[i];
j++;
}
}
if(first_match)
return class_elements[0];
else
return class_elements;
},
isOpera: function() {
return (navigator.userAgent.toLowerCase().indexOf("opera") != -1);
},
isString: function(obj) {
return (typeof obj == 'string');
},
getXMLHttpRequest: function() {
var try_these = [
function () { return new XMLHttpRequest(); },
function () { return new ActiveXObject('Msxml2.XMLHTTP'); },
function () { return new ActiveXObject('Microsoft.XMLHTTP'); },
function () { return new ActiveXObject('Msxml2.XMLHTTP.4.0'); },
function () { throw "Browser does not support XMLHttpRequest"; }
];
for (var i = 0; i < try_these.length; i++) {
var func = try_these[i];
try {
return func();
} catch (e) {
}
}
},
hideElement: function(elm) {
var args = AJS.forceArray(arguments);
AJS.map(args, function(elm) { elm.style.display = 'none'});
},
callLater: function(fn, interval) {
var fn_no_send = function() {
fn();
};
window.setTimeout(fn_no_send, interval);
},
insertBefore: function(elm, reference_elm) {
reference_elm.parentNode.insertBefore(elm, reference_elm);
return elm;
},
filter: function(list, fn, /*optional*/ start_index, end_index) {
var r = [];
AJS.map(list, function(elm) {
if(fn(elm))
r.push(elm);
}, start_index, end_index);
return r;
},
createArray: function(v) {
if(AJS.isArray(v) && !AJS.isString(v))
return v;
else if(!v)
return [];
else
return [v];
},
isDict: function(o) {
var str_repr = String(o);
return str_repr.indexOf(" Object") != -1;
},
removeEventListener: function(elm, type, fn, /*optional*/cancle_bubble) {
var ajs_l_key = 'ajsl_'+type+fn;
if(!cancle_bubble)
cancle_bubble = false;
fn = elm[ajs_l_key] || fn;
if(elm['on' + type] == fn) {
elm['on' + type] = elm[ajs_l_key + 'old'];
}
if(elm.removeEventListener) {
elm.removeEventListener(type, fn, cancle_bubble);
if(AJS.isOpera())
elm.removeEventListener(type, fn, !cancle_bubble);
}
else if(elm.detachEvent)
elm.detachEvent("on" + type, fn);
},
setEventKey: function(e) {
e.key = e.keyCode ? e.keyCode : e.charCode;
if(window.event) {
e.ctrl = window.event.ctrlKey;
e.shift = window.event.shiftKey;
}
else {
e.ctrl = e.ctrlKey;
e.shift = e.shiftKey;
}
switch(e.key) {
case 63232:
e.key = 38;
break;
case 63233:
e.key = 40;
break;
case 63235:
e.key = 39;
break;
case 63234:
e.key = 37;
break;
}
},
_createDomShortcuts: function() {
var elms = [
"ul", "li", "td", "tr", "th",
"tbody", "table", "input", "span", "b",
"a", "div", "img", "button", "h1",
"h2", "h3", "h4", "h5", "h6", "br", "textarea", "form",
"p", "select", "option", "optgroup", "iframe", "script",
"center", "dl", "dt", "dd", "small",
"pre", 'i'
];
var extends_ajs = function(elm) {
AJS[elm.toUpperCase()] = function() {
return AJS.createDOM.apply(null, [elm, arguments]); 
};
}
AJS.map(elms, extends_ajs);
AJS.TN = function(text) { return document.createTextNode(text) };
},
addCallback: function(fn) {
this.callbacks.unshift(fn);
},
isElementHidden: function(elm) {
return ((elm.style.display == "none") || (elm.style.visibility == "hidden"));
},
isNumber: function(obj) {
return (typeof obj == 'number');
},
queryArguments: function(data) {
var post_data = [];
for(k in data)
post_data.push(k + "=" + AJS.urlencode(data[k]));
return post_data.join("&");
},
replaceChildNodes: function(elm/*, elms...*/) {
var child;
while ((child = elm.firstChild))
elm.removeChild(child);
if (arguments.length < 2)
return elm;
else
return AJS.appendChildNodes.apply(null, arguments);
return elm;
},
getCssDim: function(dim) {
if(AJS.isString(dim))
return dim;
else
return dim + "px";
},
isIe: function() {
return (navigator.userAgent.toLowerCase().indexOf("msie") != -1 && navigator.userAgent.toLowerCase().indexOf("opera") == -1);
},
removeClass: function(/*elm1, elm2..., className*/) {
var args = AJS.forceArray(arguments);
var cls = args.pop();
var rm_class = function(o) {
o.className = o.className.replace(new RegExp("\\s?" + cls, 'g'), "");
};
AJS.map(args, function(elm) { rm_class(elm); });
},
urlencode: function(str) {
return encodeURIComponent(str.toString());
},
map: function(list, fn,/*optional*/ start_index, end_index) {
var i = 0, l = list.length;
if(start_index)
i = start_index;
if(end_index)
l = end_index;
for(i; i < l; i++) {
var val = fn(list[i], i);
if(val != undefined)
return val;
}
},
addEventListener: function(elm, type, fn, /*optional*/listen_once, cancle_bubble) {
var ajs_l_key = 'ajsl_'+type+fn;
if(!cancle_bubble)
cancle_bubble = false;
AJS.listeners = AJS.$A(AJS.listeners);
//Fix keyCode
if(AJS.isIn(type, ['keypress', 'keydown', 'keyup', 'click'])) {
var old_fn_1 = fn;
fn = function(e) {
AJS.setEventKey(e);
return old_fn_1.apply(window, arguments);
}
}
//Hack since these does not work in all browsers
var is_special_type = AJS.isIn(type, ['submit', 'load', 'scroll', 'resize']);
var elms = AJS.$A(elm);
AJS.map(elms, function(elm_i) {
if(listen_once) {
var old_fn_2 = fn;
fn = function(e) {
AJS.REV(elm_i, type, fn);
return old_fn_2.apply(window, arguments);
}
}
if(is_special_type) {
var old_fn = elm_i['on' + type];
var wrap_fn = function() {
if(old_fn) {
fn(arguments);
return old_fn(arguments);
}
else
return fn(arguments);
};
elm_i[ajs_l_key] = wrap_fn;
elm_i[ajs_l_key+'old'] = old_fn;
elm['on' + type] = wrap_fn;
}
else {
elm_i[ajs_l_key] = fn;
if (elm_i.attachEvent)
elm_i.attachEvent("on" + type, fn);
else if(elm_i.addEventListener)
elm_i.addEventListener(type, fn, cancle_bubble);
AJS.listeners.push([elm_i, type, fn]);
}
});
},
forceArray: function(args) {
var r = [];
AJS.map(args, function(elm) {
r.push(elm);
});
return r;
},
getBody: function() {
return AJS.$bytc('body')[0]
},
getElement: function(id) {
if(AJS.isString(id) || AJS.isNumber(id))
return document.getElementById(id);
else
return id;
},
isObject: function(obj) {
return (typeof obj == 'object');
},
showElement: function(/*elms...*/) {
var args = AJS.forceArray(arguments);
AJS.map(args, function(elm) { elm.style.display = ''});
},
createDOM: function(name, attrs) {
var i=0, attr;
var elm = document.createElement(name);
var first_attr = attrs[0];
if(AJS.isDict(attrs[i])) {
for(k in first_attr) {
attr = first_attr[k];
if(k == 'style' || k == 's')
elm.style.cssText = attr;
else if(k == 'c' || k == 'class' || k == 'className')
elm.className = attr;
else {
elm.setAttribute(k, attr);
}
}
i++;
}
if(first_attr == null)
i = 1;
for(var j=i; j < attrs.length; j++) {
var attr = attrs[j];
if(attr) {
var type = typeof(attr);
if(type == 'string' || type == 'number')
attr = AJS.TN(attr);
elm.appendChild(attr);
}
}
return elm;
},
log: function(o) {
if(window.console)
console.log(o);
else {
var div = AJS.$('ajs_logger');
if(!div) {
div = AJS.DIV({id: 'ajs_logger', 'style': 'color: green; position: absolute; left: 0'});
div.style.top = AJS.getScrollTop() + 'px';
AJS.ACN(AJS.getBody(), div);
}
AJS.setHTML(div, ''+o);
}
},
isDefined: function(o) {
return (o != "undefined" && o != null)
}
}

AJS.$ = AJS.getElement;
AJS.$$ = AJS.getElements;
AJS.$f = AJS.getFormElement;
AJS.$p = AJS.partial;
AJS.$b = AJS.bind;
AJS.$A = AJS.createArray;
AJS.DI = AJS.documentInsert;
AJS.ACN = AJS.appendChildNodes;
AJS.RCN = AJS.replaceChildNodes;
AJS.AEV = AJS.addEventListener;
AJS.REV = AJS.removeEventListener;
AJS.$bytc = AJS.getElementsByTagAndClassName;
AJS.$AP = AJS.absolutePosition;
AJS.$FA = AJS.forceArray;

AJS.addEventListener(window, 'unload', AJS._unloadListeners);
AJS._createDomShortcuts();

AJS.Class = function(members) {
var fn = function() {
if(arguments[0] != 'no_init') {
return this.init.apply(this, arguments);
}
}
fn.prototype = members;
AJS.update(fn, AJS.Class.prototype);
return fn;
}
AJS.Class.prototype = {
extend: function(members) {
var parent = new this('no_init');
for(k in members) {
var prev = parent[k];
var cur = members[k];
if (prev && prev != cur && typeof cur == 'function') {
cur = this._parentize(cur, prev);
}
parent[k] = cur;
}
return new AJS.Class(parent);
},
implement: function(members) {
AJS.update(this.prototype, members);
},
_parentize: function(cur, prev) {
return function(){
this.parent = prev;
return cur.apply(this, arguments);
}
}
};//End class

AJSDeferred = function(req) {
this.callbacks = [];
this.errbacks = [];
this.req = req;
}
AJSDeferred.prototype = {
excCallbackSeq: function(req, list) {
var data = req.responseText;
while (list.length > 0) {
var fn = list.pop();
var new_data = fn(data, req);
if(new_data)
data = new_data;
}
},
callback: function () {
this.excCallbackSeq(this.req, this.callbacks);
},
errback: function() {
if(this.errbacks.length == 0)
alert("Error encountered:\n" + this.req.responseText);
this.excCallbackSeq(this.req, this.errbacks);
},
addErrback: function(fn) {
this.errbacks.unshift(fn);
},
addCallback: function(fn) {
this.callbacks.unshift(fn);
},
abort: function() {
this.req.abort();
},
addCallbacks: function(fn1, fn2) {
this.addCallback(fn1);
this.addErrback(fn2);
},
sendReq: function(data) {
if(AJS.isObject(data)) {
this.req.send(AJS.queryArguments(data));
}
else if(AJS.isDefined(data))
this.req.send(data);
else {
this.req.send("");
}
}
};//End deferred

script_loaded = true;
