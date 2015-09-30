(function (window) {
    /**
     * Bind the $tar variable for use in the page.
     *
     * Built in a modular fashion to avoid name conflicts etc.
     */
    var seqId = 1;
    var starProperties = {};
    var baseURL = "//receiver.star.ith.semcs.net/rest/log?";
    var metaTags = document.getElementsByTagName("meta");

    for (var idx = 0; idx < metaTags.length; idx++) {
        var tag = metaTags[idx];

        var tagName = tag.getAttribute('name');
        var tagVal = tag.getAttribute('content');

        if (tagName != null && tagName.toLowerCase().indexOf("st.") == 0) {
            starProperties[tag.getAttribute("name").substring('ST.'.length).toLowerCase()] = tagVal;
        }

        // Check for industry standard tags and use if not already specified
        if (starProperties['title'] == null) {
            if (tagName == 'citation_title' || tagName == 'citation_journal_title' || tagName == 'DC.title') {
                starProperties['title'] = tagVal;
            }
        }

        if (starProperties['yop'] == null) {
            if (tagName == 'citation_publication_date' || tagName == 'DC.issued') {
                starProperties['yop'] = tagVal.substring(0, 4);
            }
        }

        if (starProperties['publisher'] == null) {
            if (tagName == 'citation_dissertation_institution' || tagName == 'citation_technical_report_institution' || tagName == 'DC.publisher') {
                starProperties['publisher'] = tagVal;
            }
        }

        if (starProperties['onlineissn'] == null) {
            if (tagName == 'citation_issn') {
                starProperties['onlineissn'] = tagVal;
            }
        }

        if (starProperties['isbn'] == null) {
            if (tagName == 'citation_isbn') {
                starProperties['isbn'] = tagVal;
            }
        }

        if (starProperties['doi'] == null) {
            if (tagName == 'citation_doi') {
                starProperties['doi'] = tagVal;
            }
        }

        if (starProperties['pagetype'] == null) {
            if (tagName == 'DC.format') {
                starProperties['pagetype'] = tagVal;
            }
        }
    }

    /**
     * Mimic jQuery extend to remove dependency.
     *
     * @return {*}
     */
    function extend() {
        for (var i = 1; i < arguments.length; i++) {
            for (var key in arguments[i]) {
                if (arguments[i].hasOwnProperty(key)) {
                    arguments[0][key.toLowerCase()] = arguments[i][key];
                }
            }
        }

        return arguments[0];
    }

    /**
     * Cookie handling scriptlet.
     */
    function cookie(key, value, options) {
        // key and at least value given, set cookie...
        if (arguments.length > 1 && (!/Object/.test(Object.prototype.toString.call(value)) || value === null || value === undefined)) {
            options = extend({}, options);

            if (value === null || value === undefined) {
                options.expires = -1;
            }

            if (typeof options.expires === 'number') {
                var days = options.expires, t = options.expires = new Date();
                t.setDate(t.getDate() + days);
            }

            value = String(value);

            document.cookie = [
                encodeURIComponent(key), '=', options.raw ? value : encodeURIComponent(value),
                options.expires ? '; expires=' + options.expires.toUTCString() : '', // use expires attribute, max-age is not supported by IE
                '; path=/',
                options.domain ? '; domain=' + options.domain : '',
                options.secure ? '; secure' : ''
            ].join('');

            return options.raw ? value : encodeURIComponent(value);
        }

        // key and possibly options given, get cookie...
        options = value || {};
        var decode = options.raw ? function (s) {
            return s;
        } : decodeURIComponent;

        var pairs = document.cookie.split('; ');
        for (var i = 0, pair; pair = pairs[i] && pairs[i].split('='); i++) {
            if (decode(pair[0]) === key) {
                return decode(pair[1] || '');
            } // IE saves cookies with empty string as "c; ", e.g. without "=" as opposed to EOMB, thus pair[1] may be undefined
        }

        return null;
    }

    /**
     * Generate a portion of a UUID string
     *
     * @param size (in characters) of the portion to create
     * @return {String}
     */
    function generateUUIDPart(size) {
        var content = '';

        for (var i = 0; i < size; i++) {
            content += (Math.random() * 16 | 0).toString(16);
        }

        return content;
    }

    /**
     * Generate a Type-4 compliant UUID ("random number" based) with key fields as per spec.
     *
     * @param prefix Optional prefix
     */
    function generateUUID(prefix) {
        if (prefix == null) {
            prefix = '';
        } else {
            prefix = prefix + '-';
        }

        // Valid prefixes for Type-4 UUID part 4
        var prefixes = ['8', '9', 'a', 'b'];

        var uuid = prefix + [generateUUIDPart(8), generateUUIDPart(4), '4' + generateUUIDPart(3),
            prefixes[Math.random() * prefixes.length | 0] + generateUUIDPart(3), generateUUIDPart(12)].join('-');

        return (uuid);
    }

    /**
     * Lookup or retrieve the UUID for this session.
     *
     * @return {*}
     */
    function getOrCreateUUID() {
        var cookieVal = cookie('_starUuid');

        if (cookieVal == null) {
            cookieVal = cookie('_starUuid', generateUUID());
        }

        return cookieVal;
    }

    /**
     * Perform a tracking operation.
     *
     * @param obj javascript hash that will override meta tags
     */
    function track(obj) {
        var params = {};
        extend(params, starProperties, {uuid:getOrCreateUUID(),
            seqid:seqId++,
            reportingdate:new Date().getTime(),
            referer:window.location.hostname}, obj);

        var paramArray = [];

        for (var key in params) {
            if (params.hasOwnProperty(key)) {
                paramArray.push(encodeURIComponent(key) + '=' + encodeURIComponent(params[key]));
            }
        }

        new Image().src = baseURL + paramArray.join('&');
    }

    /**
     * Public function(s) to expose in the _$tarQ variable.
     * At present just re-use the array push function.
     */
    var q = window._$tarQ;

    // Bind callback response to global scoped variable
    window._$tarQ = {
        push:function (obj) {
            if (obj[0] == 'track') {
                track(obj[1]);
            }
        }
    };

    for (var i = 0; i < q.length; i++) {
        window._$tarQ.push(q[i]);
    }
})(window);
