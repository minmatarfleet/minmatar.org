
var fitting = new function () {
    var self = this;

    this.options = {};
    try {
        this.options = JSON.parse(localStorage.ccpwgloptions);
    }
    catch (e) {
    }

    function decodeUrlOptions() {
        var match,
            pl     = /\+/g,  // Regex for replacing addition symbol with a space
            search = /([^&=]+)=?([^&]*)/g,
            decode = function (s) { return decodeURIComponent(s.replace(pl, " ")); },
            query  = window.location.search.substring(1);

        self.options = {};
        while (match = search.exec(query)) {
            self.options[decode(match[1])] = decode(match[2]);
        }
    }

    function saveOptions() {
        localStorage.ccpwgloptions = JSON.stringify(self.options);
    }

    function onPopState(state) {
        if (state) {
            self.options = state.options || {};
        }
        decodeUrlOptions();
        saveOptions();
    }

    onPopState(history.state);

    if ('resUrl' in this.options) {
        ccpwgl.setResourcePath('res', this.options.resUrl);
        //this.options.resUrl = 'http://developers.eveonline.com/ccpwgl/assetpath/860161/';// window.location.protocol + '//' + window.location.host + ':8880/';
    }
};