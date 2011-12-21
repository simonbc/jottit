var Utils = {
    trim: function(str) {
        str = str.replace(/ +/g, ' ');
        str = str.replace(/^\s+|\s+$/g, '');
        if (str == ' ') { str = ''; }
        return str;
    },

    htmlquote: function(text) {
        text = text.replace(/&/g, "&amp;") // Must be done first!
        text = text.replace(/</g, "&lt;")
        text = text.replace(/>/g, "&gt;")
        text = text.replace(/'/g, "&#39;")
        text = text.replace(/"/g, "&quot;")
        return text     
    }
}

var Site = {
    url: null,
    security: null
}

var Create = {
    saveCaretPos: function() {
        var input = $('content_text');
        $('scroll_pos').value = input.scrollTop;
        $('caret_pos').value = Edit.getCaretPos(input);
        return false;
    }
}

var Page = {
    name: null,
    url: null,
    esc_event: function(e) {
        if (e.key == 27) {
            Page.hide_new();
        }    
    },

    show_new: function() {
        hideElement($('new_page'));
        showElement($('new_page_input'));
        $('new_page_name').focus();
        AEV(document, 'keyup', Page.esc_event);
        return false;
    },

    hide_new: function() {
        $('new_page_name').value = '';
        hideElement($('new_page_input'));
        showElement($('new_page'));
        REV(document, 'keyup', Page.esc_event);
        return false;
    },

    create: function() {
        var name = $('new_page_name').value.replace(/ /g, '_');
        name = name.replace(/(page|draft|site|admin)\/(.*)/, '$1_/$2')
        name = urlencode(name);
        window.location = Site.url+name+'?m=edit';
        return false;
    },

    signout: function() {
        var f = FORM({id: 'signout', 
                      method: 'POST', 
                      action: Site.url+'site/signout', 
                      style: 'display: none;'}, 
                      INPUT({name: 'return_to', 
                             value: Page.name ? urlencode(Page.name) : ''}));
        getBody().appendChild(f);
        $('signout').submit();
        return false;
    },

    undelete: function() {
        var f = FORM({id: 'undelete', 
                      method: 'POST', 
                      action: Page.url+'?m=undelete', 
                      style: 'display: none;'});
        getBody().appendChild(f);
        $('undelete').submit();
        return false;
    },

    focusWrong: function() {
        var wrongs = $bytc(null, 'wrong');
        if (wrongs.length > 0) {
            wrongs[0].focus();
        }
    }
}

var View = {
    init: function() {
        var datestr = $('datestr');
        if (datestr) {
            d = loadJSONDoc(Page.url);
            d.addCallback(function(o) {
                datestr.innerHTML = o.datestr;
                View.scheduleDateUpdate();
            });
            d.sendReq({m: 'datestr', page_name: Page.name});
        }
    },

    hidePrimer: function() {
        var d = getRequest(Site.url+'site/hide-primer');
        d.sendReq();
        hideElement($('primer'));
        return false;
    },

    scheduleDateUpdate: function() {
        if (!$('count')) return;
        
        var count = parseInt($('count').innerHTML);
        var unit = $('unit').innerHTML;
        if (unit.match(/second/)) {
            callLater(View.updateDate, 1000*(10-(count%10)));
        } else if (unit.match(/minute/)) {
            callLater(View.updateDate, 1000*60);
        } else if (unit.match(/hour/)) {
            callLater(View.updateDate, 1000*60*60);
        }
    },

    updateDate: function(count, unit) {
        count = count || parseInt($('count').innerHTML);
        unit = unit || $('unit').innerHTML;
        if (unit.match(/second/)) {
            if (count >= 50) {
                $('count').innerHTML = '1';
                $('unit').innerHTML = 'minute';
            } else {
                $('count').innerHTML = count-(count % 10)+10;
                $('unit').innerHTML = 'seconds';
            }
        } else if (unit.match(/minute/)) {
            if (count == 59) {
                $('count').innerHTML = '1';
                $('unit').innerHTML = 'hour';
            } else {
                $('count').innerHTML = count+1;
                $('unit').innerHTML = 'minutes';
            }
        } else if (unit.match(/hour/)) {
            if (count == 23) {
                $('count').innerHTML = '1';
                $('unit').innerHTML = 'day';
            } else {
                $('count').innerHTML = count+1;
                $('unit').innerHTML = 'hours';
            }
        }
        View.scheduleDateUpdate();
    }
}

var Edit = {
    orig_len: null,
    lastText: null,
    lastRoomLeft: null,
    lastTextSave: null,
    syncScrollbarsEvent: null,
    inputPos: null,
    input: null,
    preview: null,
    help: null,
    converter: null,
    convertTimer: null,
    maxDelay: 3000,
    processingTime: null,
    inputScrollPos: null,
    previewScrollPos: null,

    init: function() {
        Edit.input = $('content_text');
        Edit.preview = $('preview');
        Edit.help = $('help');

        Edit.orig_len = Edit.input.value.length;
        Edit.lastTextSave = Edit.input.value;
        
        // Resize panes
        AEV(window, 'resize', Edit.resizePanes);
        Edit.resizePanes();

        // Set caret position
        var caret_pos = $('caret_pos').value;
        var scroll_pos = $('scroll_pos').value;
        Edit.setCaretPos(Edit.input, caret_pos, scroll_pos);

        // Autosave
        if (Page.exists) {
            window.setInterval(function() {
                Edit.save_draft(true);
            }, 1000*30);

        // Draft
            AEV(document, 'keyup', function() {
                var content = Edit.input.value;
                var unsaved = $('unsaved');
                if (content != Edit.lastTextSave && isElementHidden(unsaved)) {
                    var saved = $('saved');
                    hideElement(saved);
                    showElement(unsaved);
                }
            });
        }

        Edit.show_preview();
        Edit.input.focus();

        if (Page.exists) {
            d = loadJSONDoc(Page.url);
            d.addCallback(function(o) {
                if (o.revision) {
                    $('current_revision').value = o.revision;
                }
            });
            d.sendReq({m: 'current-revision'});
        }
    },

    conflict_init: function() {
        Edit.input = $('content_text');

        // Resize panes
        AEV(window, 'resize', Edit.resizePanes);
        Edit.resizePanes();
    },

    save_draft: function(autosave) {
        if (!Page.exists) {
            // Page deleted or not created yet
            return;
        }
        var content = Edit.input.value;
        var changed = (Utils.trim(content) != Utils.trim(Edit.lastTextSave))
        if (changed) {
            var d = getRequest(Site.url+'draft/save');
            d.sendReq({page_name: Page.name, content: content});
        }
        Edit.lastTextSave = content;

        if (autosave && changed || !autosave)  {
            var saved = $('saved');
            var unsaved = $('unsaved');
            hideElement(unsaved);
            showElement(saved);
            Edit.input.focus();
        }
        return false;
    },

    hideHasDraft: function() {
        hideElement($('has_draft'));
        Edit.resizePanes();
        Edit.input.focus();
        return false;
    },

    recoverLiveVersion: function() {
        d = loadJSONDoc(Site.url+'draft/recover-live-version');
        d.addCallback(function(o) {
            hideElement($('has_draft'));
            Edit.input.value = o.content; 
            Edit.resizePanes();
            Edit.input.focus();
        });
        d.sendReq({page_name: Page.name});
        return false;
    },

    syncScrollbars: function() {
        if (Edit.inputPos != Edit.input.scrollTop) {
            if (Edit.input.scrollHeight <= Edit.input.clientHeight) {
                Edit.preview.scrollTop = Edit.preview.scrollHeight; 
                return;
            }
            var preview_height = Edit.getElementSize(Edit.preview).height; 
            var input_height = Edit.getElementSize(Edit.input).height;
            var proportion = (Edit.preview.scrollHeight-preview_height)/(Edit.input.scrollHeight-input_height);
            Edit.preview.scrollTop = parseInt(Edit.input.scrollTop*proportion);
            Edit.inputPos = Edit.input.scrollTop;
        } 
    },
    
    toggle_tabs: function() {
        if ($('show_preview').className == 'selected') {
            Edit.show_help()
        } else {
            Edit.show_preview()
        }
    },

    selectTab: function(tab) {
        var deselect, select;
        if (tab == 'help') {    
            deselect = 'show_preview';
            select = 'show_help';
        } else if (tab == 'preview') {
            deselect = 'show_help';
            select = 'show_preview';
        } 
        $(deselect).className = '';
        $(select).className = 'selected';
        Edit.resizePanes();
    },

    show_help: function() {
        Edit.selectTab('help');
        Edit.hidePreview();
        showElement($('help'));

        Edit.input.focus();
        return false;
    },

    hidePreview: function() {
        hideElement(Edit.preview);
        window.clearInterval(Edit.syncScrollbarsEvent);
	window.onkeyup = Edit.input.onkeyup = null;
        if (Edit.pollingFallback!=null) {
            window.clearInterval(Edit.pollingFallback);
            Edit.pollingFallback = null;
        }
    },
    
    show_preview: function() {
	// Poll for changes in scrollTop
        Edit.syncScrollbarsEvent = window.setInterval(Edit.syncScrollbars, 250);

	// First, try registering for keyup events
	// (There's no harm in calling on_input() repeatedly)
	window.onkeyup = Edit.input.onkeyup = Edit.on_input;

	// In case we can't capture paste events, poll for them
	var pollingFallback = window.setInterval(function(){
            if(Edit.input.value != Edit.lastText)
		Edit.on_input();
	}, 1000);

	// Try registering for paste events
	Edit.input.onpaste = function() {
	    // It worked! Cancel paste polling.
	    if (pollingFallback!=null) {
                window.clearInterval(pollingFallback);
                pollingFallback = null;
            }
            Edit.on_input();
	}

	// Try registering for input events (the best solution)
	if (Edit.input.addEventListener) {
            // Let's assume input also fires on paste.
            // No need to cancel our keyup handlers;
            // they're basically free.
            Edit.input.addEventListener("input",Edit.input.onpaste,false);
	}

	// Do an initial conversion to avoid a hiccup
        Edit.converter = new Showdown.converter();
	Edit.convertText();

        Edit.selectTab('preview');
        hideElement($('help'));
        showElement(Edit.preview);

        Edit.input.focus();
        return false;
    },

    on_input: function() {
	if (Edit.convertTimer) {
	    window.clearTimeout(Edit.convertTimer);
	    Edit.convertTimer = null;
	}

        var timeUntilConvertText = Edit.processingTime;
        if (timeUntilConvertText > Edit.maxDelay)
            timeUntilConvertText = Edit.maxDelay;

        Edit.convertTimer = window.setTimeout(Edit.convertText, timeUntilConvertText);
    },

    convertText: function() {
	// get input text
	var text = Edit.input.value;
	
	// if there's no change to input, cancel conversion
	if (text && text == Edit.lastText) {
	    return;
	} else {
	    Edit.lastText = text;
	}

	// Do the conversion
	var startTime = new Date().getTime();
	text = Edit.converter.makeHtml(text, sanitize=(Site.security == 'open'));
	var endTime = new Date().getTime();	
	Edit.processingTime = endTime - startTime;

        // output preview
        var div = DIV();
        div.innerHTML = text;
        RCN(Edit.preview, div);
    },

    save: function() {
        Edit.saveCaretPos();
        $('edit_form').submit();
    },

    cancel: function (e) {
        Edit.saveCaretPos();
        var caret_pos = $('caret_pos').value;
        if (Edit.orig_len < caret_pos) {
            caret_pos = Edit.orig_len;
        }
        if (!Page.exists) {
            window.location = Site.url;
            return false;
        }
        var d = getRequest(Page.url);
        d.addCallback(function() {
            window.location = Page.url;
        });
        d.sendReq({m: 'cancel', caret_pos: caret_pos, scroll_pos: $('scroll_pos').value});
        return false;
    },

    deleteDraft: function() {
        var d = getRequest(Site.url+'draft/delete');
        d.sendReq({page_name: Page.name});
    },

    getCaretPos: function(elm) {
        var pos = 0;

        if (document.selection) { // IE
            elm.focus();
            var range = document.selection.createRange();
            range.moveStart ('character', -elm.value.length);
            pos = range.text.length;
        } else if (elm.selectionStart || elm.selectionStart == '0') { // Firefox
            pos = elm.selectionStart;
        }

        return pos;
    },

    setCaretPos: function(elm, caret_pos, scroll_pos) {
        // Safari won't let us scroll the textarea, so don't position the caret
        if (isSafari()) {
            caret_pos = 0;
        }

        if (document.selection) { // IE
            elm.focus();
            sel = document.selection.createRange();
        } else if (elm.selectionStart || elm.selectionStart == '0') { // Firefox
            elm.selectionStart = caret_pos;
            elm.selectionEnd = caret_pos;
            elm.scrollTop = scroll_pos;
        }
    },

    saveCaretPos: function(callback, cancel) {
        var trimmed = Utils.trim(Edit.input.value);
        var caret_pos = Edit.getCaretPos(Edit.input);
        var scroll_pos = Edit.input.scrollTop;
        if (cancel && caret_pos > Edit.orig_len) {
            caret_pos = Edit.orig_len;
            scroll_pos = Edit.input.scrollHeight;
        } else if (caret_pos > trimmed.length) {
            caret_pos = trimmed.length;
            scroll_pos = Edit.input.scrollHeight;
        }

        $('scroll_pos').value = scroll_pos
        $('caret_pos').value = caret_pos;
    },

    getTop: function(elm) {
        var sum = elm.offsetTop;
        while(elm = elm.offsetParent)
            sum += elm.offsetTop;
        return sum;
    },

    getElementSize: function(elm) {
        if (elm.clientHeight) {
            return {width: elm.clientWidth, height: elm.clientHeight};
        } else {
            return {width: elm.scrollWidth, height: elm.scrollHeight};
        }
    },

    getWindowSize: function() {
        if (window.innerHeight)
            return { width: window.innerWidth, height: window.innerHeight };
        else if (document.documentElement && document.documentElement.clientHeight)
            return { width: document.documentElement.clientHeight, height: document.documentElement.clientHeight };
        else if (document.body)
            return { width: document.body.clientHeight, height: document.body.clientHeight };
    },

    resizePanes: function() {
        var buttons = $('buttons');
        var windowSize = Edit.getWindowSize();
        var buttonsHeight = Edit.getElementSize(buttons).height;
        var inputTop = Edit.getTop(Edit.input);

        var roomLeft = windowSize.height - buttonsHeight - inputTop - 15;

        if (roomLeft < 0) roomLeft = 0;

        Edit.lastRoomLeft = roomLeft;

        Edit.input.style.height = roomLeft + 'px';
        if (Edit.preview) {
            Edit.preview.style.height = roomLeft + 'px';
        }
        if (Edit.help) {
            Edit.help.style.height = roomLeft + 'px';
            if (isIe()) {
                Edit.help.style.width = (windowSize.width-120)+ 'px';
            }
        }
    }
}

var History = {
    num: null,

    init: function() {
        var form = $('history_form');
        map(History.getCheckboxes(form), function(c) {
            AEV(c, 'click', function() { 
                History.markRevision(form, c);
            });
            if (c.checked) {
                History.markRevision(form, c);
            }
        });
    },

    getCheckboxes: function(form) {
        return filter(form.elements, function(e) {
            return e.type == 'checkbox';
        });
    },

    getChecked: function(checkboxes) {
        return filter(checkboxes, function(e) {
            return e.checked;    
        });
    },

    markRevision: function(form, checkbox) {
        var tr = getParentBytc(checkbox, 'tr');
        if (checkbox.checked) {
            tr.style.backgroundColor = '#ffc';
        } else {
            if (tr.className == 'gray') {
                tr.style.backgroundColor = '#eee';
            } else {
                tr.style.backgroundColor = '#fff';
            }
        }
        var checkboxes = History.getCheckboxes(form);
        var checked = History.getChecked(checkboxes);
        if (checked.length == 2) {
            History.disableCheckboxes(checkboxes); 
        } else if (checked.length == 1) {
            History.enableCheckboxes(checkboxes); 
        }
    },

    disableCheckboxes: function(checkboxes) {
        map(checkboxes, function(c) {
            if(!c.checked) {
                c.disabled = 'disabled';
            }
        });
    },

    enableCheckboxes: function(checkboxes) {
        map(checkboxes, function(c) {
            c.disabled = '';
        });
    }
}

var Diff = {
    init: function() {
        AEV($('a'), 'change', Diff.changeCompare);
        AEV($('b'), 'change', Diff.changeCompare);
    },

    changeCompare: function() {
        $('diff_form').submit();
    }
}

var BrowseRevs = {
    init: function() {
        AEV($('change_rev'), 'change', BrowseRevs.changeRev);
    },

    changeRev: function() {
        var r = $('change_rev').value;
        window.location = Page.url+'?r='+r;
    }
}

var Settings = {
    change_timer: null,

    init: function() {
        Settings.last_url = Settings.old_url;
        AEV($('settings_form'), 'submit', function() {
            return false;
        });
        if ($('_title').value) {
            $('title').innerHTML = Utils.htmlquote($('_title').value);
        }
        if ($('_subtitle').value) {
            $('subtitle').innerHTML = Utils.htmlquote($('_subtitle').value);
        }
        Page.focusWrong();
        AEV($('_title'), 'keyup', function() {
            $('title').innerHTML = Utils.htmlquote($('_title').value);
            if ($('_title').value.length) {
                showElement(getParentBytc($('title'), 'h1'));
            } else {
                hideElement(getParentBytc($('title'), 'h1'));
            }
            Settings.on_change();
        });
        AEV($('_subtitle'), 'keyup', function() {
            $('subtitle').innerHTML = Utils.htmlquote($('_subtitle').value);
            if ($('_subtitle').value.length) {
                showElement($('subtitle'));
            } else {
                hideElement($('subtitle'));
            }
            Settings.on_change();
        });
        if ($('email')) {
            AEV($('email'), 'keyup', function() { 
                if($('email').value) {
                    Settings.on_change();
                    $('email').className = '';
                } else {
                    $('email').className = 'wrong';
                }
            });
        }
        if ($('security')) {
            map(['private', 'public', 'open'], function(s) { 
                AEV($(s), 'click', function() {
                    map($bytc('label', null, $('security')), function(elm) {
                        elm.style.fontWeight = 'normal';
                    });
                    map($bytc('label', null, $(s)), function(elm) {
                        elm.style.fontWeight = 'bold';
                    });
                    map($bytc('input', null, $(s)), function(elm) {
                        elm.checked = true;
                    });
                    Settings.on_change();
                });
            });
            map($bytc('input', null, $('security')), function(i) { 
                if (i.checked) {
                    i.click();
                }
            });
        }
    },

    on_change: function() {
	if (Settings.change_timer) {
	    window.clearTimeout(Settings.change_timer);
	    Settings.change_timer = null;
	}
        Settings.change_timer = window.setTimeout(Settings.save, 500);
    },

    save: function() {
        var d = getRequest('settings');
        var security = '';
        if ($('security')) {
            if ($('private_input').checked) {
                security = 'private';
            } else if ($('open_input').checked) {
                security = 'open';
            } else {
                security = 'public';
            }
        }
        var data = {title: $('_title').value,
                    subtitle: $('_subtitle').value,
                    email: $('email') ? $('email').value : '',
                    security: security};
        if (!$('email') || $('email').value) {
            d.sendReq(data);
        }
    }
}

var ChangePublicUrl = {
    old_url: null,
    last_url: null,
    availability_timer: null,

   init: function() { 
        AEV($('public_url'), 'keyup', function() { 
	    if (ChangePublicUrl.availability_timer) {
	        window.clearTimeout(ChangePublicUrl.availability_timer);
	        ChangePublicUrl.availability_timer = null;
	    }
            var url = Utils.trim($('public_url').value);
            if (!url.length) {
               ChangePublicUrl.display_available();
               return
            } 
            ChangePublicUrl.availability_timer = window.setTimeout(ChangePublicUrl.check_availability, 500);
        });
        AEV(AJS.$('change_public_url'), 'submit', function() { AJS.$('change_button').value='Changing address...'; AJS.$('change_button').disabled = true; });
        $('public_url').focus();
        ChangePublicUrl.check_availability();
    },

    display_available: function() {
        hideElement($('indicator'));
        hideElement($('error_msg'));
    },

    display_unavailable: function() {
            var url = Utils.trim($('public_url').value);
            var msg = url+' is taken, please try a different one';
            ChangePublicUrl.error(msg);
    },

    display_checking: function() {
        hideElement($('error_msg'));
        showElement($('indicator'));
    },

    error: function(msg) {
        var error_msg = $('error_msg');
        var url = Utils.trim($('public_url').value);
        hideElement($('indicator'));
        showElement(error_msg);
        error_msg.style.color = 'red';
        error_msg.innerHTML = msg;
    },

    check_availability: function() {
        var url = Utils.trim($('public_url').value);
        if (url == ChangePublicUrl.last_url) {
            return;
        }

        ChangePublicUrl.last_url = url;
        if (!url || url == ChangePublicUrl.old_url) {
            ChangePublicUrl.display_available();
            return;
        }

        if (!url.match(/^[a-zA-Z0-9-]+$/)) {
            var msg = url+' is not valid, only use letters and numbers'
            ChangePublicUrl.error(msg);
            return;
        }

        if (url.length > 30) {
            var msg = 'the address must be shorter than 30 characters'
            ChangePublicUrl.error(msg);
            return;
        }

        if (url.length < 3) {
            ChangePublicUrl.display_unavailable();
            return;
        }

        ChangePublicUrl.display_checking();
        d = loadJSONDoc('url-available');
        d.addCallback(function(o) {
            if (o.available) {
                ChangePublicUrl.display_available();
            } else {
                ChangePublicUrl.display_unavailable();
            }
        })
        d.sendReq({url:url});
    }
}

var Design = {
    hue: null,
    brightness: null,
    panel: null,
    color_slider_initialized: false,
    change_timer: null,
    backup: null,

    init: function(design) {
        Design.init_color_sliders();
        map(['title', 'subtitle', 'headings', 'content'], function(e) {
            AEV($(e+'_font'), 'change', function() {
                if (!isIe()) {
                    $(e+'_font').style.fontFamily = Design.font_family($(e+'_font').value);
                }
                Design.changeFont(e);
            }); 
            AEV($(e+'_size'), 'change', function() {
                Design.changeFontSize(e);
            });
            if (!isIe()) {
                $(e+'_font').style.fontFamily = Design.font_family($(e+'_font').value);
            }
        });
        var menu_links = $bytc('a', null, $('menu'));
        map(menu_links, function(l) {
            AEV(l, 'mouseover', function() {
                l.style.color = 'white';
            })     
            AEV(l, 'mouseout', function() {
                l.style.color = $('subtitle').style.color;
            })     
        });
        $('title').style.fontFamily = Design.font_family($('title_font').value);
        $('title').style.fontSize = $('title_size').value+'%';
        $('subtitle').style.fontFamily = Design.font_family($('subtitle_font').value);
        $('subtitle').style.fontSize = $('subtitle_size').value+'%';
        Design.backup = {
            hue: $('hue').value,
            brightness: $('brightness').value,
            title_font: $('title_font').value,
            title_size: $('title_size').value,
            subtitle_font: $('subtitle_font').value,
            subtitle_size: $('subtitle_size').value,
            headings_font: $('headings_font').value,
            headings_size: $('headings_size').value,
            content_font: $('content_font').value,
            content_size: $('content_size').value
        };
    },

    on_change: function() {
	if (Design.change_timer) {
	    window.clearTimeout(Design.change_timer);
	    Design.change_timer = null;
	}
        Design.change_timer = window.setTimeout(Design.save, 500);
    },

    save: function() {
        var d = getRequest('design');
        var data = {title_font: $('title_font').value, 
                   subtitle_font: $('subtitle_font').value, 
                   headings_font: $('headings_font').value, 
                   content_font: $('content_font').value, 
                   header_color: $('header_color').value, 
                   title_color: $('title_color').value, 
                   subtitle_color: $('subtitle_color').value, 
                   title_size: $('title_size').value, 
                   subtitle_size: $('subtitle_size').value, 
                   headings_size: $('headings_size').value, 
                   content_size: $('content_size').value, 
                   hue: $('hue').value, 
                   brightness: $('brightness').value};
        d.sendReq(data);
    },

    revert: function() {
        $('title_font').value = Design.backup.title_font; 
        $('subtitle_font').value  = Design.backup.subtitle_font; 
        $('headings_font').value  = Design.backup.headings_font; 
        $('content_font').value  = Design.backup.content_font; 
        $('header_color').value  = Design.backup.header_color; 
        $('title_color').value  = Design.backup.title_color; 
        $('subtitle_color').value  = Design.backup.subtitle_color;
        $('title_size').value  = Design.backup.title_size;
        $('subtitle_size').value = Design.backup.subtitle_size;
        $('headings_size').value  = Design.backup.headings_size;
        $('content_size').value  = Design.backup.content_size;
        $('hue').value  = Design.backup.hue;
        $('brightness').value  = Design.backup.brightness;
        Design.hue.setValue(parseInt($('hue').value));
        Design.brightness.setValue(parseInt($('brightness').value));
        Design.createScheme();
        map(['title', 'subtitle', 'headings', 'content'], function(e) {
            Design.changeFont(e);
            Design.changeFontSize(e);
            if (!isIe()) {
                $(e+'_font').style.fontFamily = Design.font_family($(e+'_font').value);
            }
        });
        Design.on_change();
        return false;
    },

    font_family: function(font) {
        return {
            Arial_Black: '"Arial Black", sans-serif',
            Courier: '"Courier New", courier, monospace, sans-serif',
            Georgia: 'georgia, "Times New Roman", times, serif',
            Helvetica: 'helvetica, arial,  sans-serif',
            Lucida_Grande: '"Lucida Grande", verdana, sans-serif',
            Times: '"Times New Roman", times, serif',
            Verdana: 'verdana, sans-serif'
        }[font]
    },

    init_color_sliders: function () {
        Design.hue = YAHOO.widget.Slider.getHorizSlider("hue_slider", "hue_handle", 0, 255);
        Design.hue.subscribe("change", Design.hueUpdate);
        Design.hue.setValue(parseInt($('hue').value));

        Design.brightness = YAHOO.widget.Slider.getHorizSlider("brightness_slider", "brightness_handle", 0, 255);
        Design.brightness.subscribe("change", Design.brightnessUpdate);
        Design.brightness.setValue(parseInt($('brightness').value));
    },

    hueUpdate: function(offset) {
        $('hue').value = offset;
        Design.createScheme();
    },

    brightnessUpdate: function(offset) {
        $('brightness').value = offset;
        Design.createScheme();
    },

    getHue: function() {
        var h = $('hue').value;
        return h/255;
    },

    getBrightness: function() {
        var b = $('brightness').value;
        b = (b*200/255)/100;
        return b;
    },

    getHsv: function() {
        var h = Design.getHue();
        var brightness = Design.getBrightness();
        var s, v;
        if (brightness <= 1) {
            s = brightness; 
            v = 1; 
        } else {
            s = 1; 
            v = 2 - brightness; 
        }

        return {h: h, s: s, v: v}
    },

    createScheme: function() {
        var hsv = Design.getHsv();
        var rgb = Color.hsv2rgb(hsv.h, hsv.s, hsv.v);
        var header = '#'+Color.rgb2hex(rgb.r, rgb.g, rgb.b);

        var subtitle_s, subtitle_v, title;
        if (hsv.v < 0.3*hsv.s+0.6) {
            subtitle_s = 0.25, subtitle_v = 1;
            title = '#fff';
        } else {
            subtitle_s = 1, subtitle_v = 0.4*hsv.v;
            title = '#000';
        }
        rgb = Color.hsv2rgb(hsv.h, subtitle_s, subtitle_v);
        var subtitle = '#'+Color.rgb2hex(rgb.r, rgb.g, rgb.b);

        Design.changeScheme(header, title, subtitle, hsv);
        $('selected_color').style.backgroundColor = header;

        rgb = Color.hsv2rgb(hsv.h, 1, 1);
        var brightness_bg_color = '#'+Color.rgb2hex(rgb.r, rgb.g, rgb.b);
        $('brightness_slider').style.backgroundColor = brightness_bg_color;
    },

    changeScheme: function(header, title, subtitle, hsv) {
        $('header').style.backgroundColor = header;
        $('header_color').value = header;
        if ($('title')) $('title').style.color = title;
        $('title_color').value = title;
        if ($('subtitle')) $('subtitle').style.color = subtitle;
        $('menu').style.color = subtitle;
        $('subtitle_color').value = subtitle;
        var links = $bytc('a', null, $('menu'));
        map(links, function(l) {
            l.style.color = subtitle;
        });
        Design.on_change();
    },

    changeFont: function(elm_name) {
        if (isIn(elm_name, ['title', 'subtitle'])) {
            $(elm_name).style.fontFamily = Design.font_family($(elm_name+'_font').value);
        }
        Design.on_change();
    },

    changeFontSize: function(elm_name) {
        if (isIn(elm_name, ['title', 'subtitle'])) {
            $(elm_name).style.fontSize = $(elm_name+'_size').value+'%';
        }
        Design.on_change();
    }
}

var Color = {
    hexchars: "0123456789ABCDEF",

    hsv2rgb: function (h, s, v) {
        var r, g, b;
        if ( s == 0 ) {
            r = v * 255;
            g = v * 255;
            b = v * 255;
        } else {

            // h must be < 1
            var var_h = h * 6;
            if ( var_h == 6 ) {
                var_h = 0;
            }

            //Or ... var_i = floor( var_h )
            var var_i = Math.floor( var_h );
            var var_1 = v * ( 1 - s );
            var var_2 = v * ( 1 - s * ( var_h - var_i ) );
            var var_3 = v * ( 1 - s * ( 1 - ( var_h - var_i ) ) );

            if ( var_i == 0 ) { 
                var_r = v; 
                var_g = var_3; 
                var_b = var_1;
            } else if ( var_i == 1 ) { 
                var_r = var_2;
                var_g = v;
                var_b = var_1;
            } else if ( var_i == 2 ) {
                var_r = var_1;
                var_g = v;
                var_b = var_3
            } else if ( var_i == 3 ) {
                var_r = var_1;
                var_g = var_2;
                var_b = v;
            } else if ( var_i == 4 ) {
                var_r = var_3;
                var_g = var_1;
                var_b = v;
            } else { 
                var_r = v;
                var_g = var_1;
                var_b = var_2
            }

            r = var_r * 255          //rgb results = 0 ÷ 255
                g = var_g * 255
                b = var_b * 255

        }
        return {r: Math.round(r), g: Math.round(g), b: Math.round(b)};
    },

    rgb2hex: function (r,g,b) {
        return Color.toHex(r) + Color.toHex(g) + Color.toHex(b);
    },

    toHex: function(n) {
        n = n || 0;
        n = parseInt(n, 10);
        if (isNaN(n)) n = 0;
        n = Math.round(Math.min(Math.max(0, n), 255));

        return Color.hexchars.charAt((n - n % 16) / 16) + Color.hexchars.charAt(n % 16);
    }
}

var ClaimSite = {
    init: function () {        
        var password = $('password'); 
        var email = $('email'); 
        if (!password.value || !email.value) {
            $('submit').disabled = true;
        }
        map([password, email], function(e) {
            AEV(e, 'keyup', function() {
                if (password.value && email.value) {
                    $('submit').disabled = false;
                } else {
                    $('submit').disabled = true;
                }
            });
        });

        map(['private', 'public', 'open'], function(s) { 
            AEV($(s), 'click', function() {
                map($bytc('label', null, $('security')), function(elm) {
                    elm.style.fontWeight = 'normal';
                });
                map($bytc('label', null, $(s)), function(elm) {
                    elm.style.fontWeight = 'bold';
                });
                map($bytc('input', null, $(s)), function(elm) {
                    elm.checked = true;
                });
            });
            map($bytc('input', null, $(s)), function(elm) {
                if (elm.checked) {
                    $(elm).click();
                }
            });
        });
        if(password.value) {
            email.focus();
        } else {
            password.focus();
        }
    }    
}
