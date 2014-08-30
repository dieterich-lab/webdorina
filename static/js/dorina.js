function DoRiNAViewModel(net, uuid, custom_regulator) {
    var self = this;
    self.retry_after = 1000;
    self.loading_regulators = ko.observable(false);
    self.uuid = ko.observable(uuid);
    self.custom_regulator = ko.observable(custom_regulator);

    self.chosenAssembly = ko.observable();

    self.regulators = ko.observableArray([]);
    self.selected_regulators = ko.observableArray([]);
    self.selected_regulators_setb = ko.observableArray([]);

    self.results = ko.observableArray([]);

    self.more_results = ko.observable(false);
    self.offset = ko.observable(0);
    self.pending = ko.observable(false);

    self.genes = ko.observable('');
    self.match_a = ko.observable('any');
    self.region_a = ko.observable('any');

    self.match_b = ko.observable('any');
    self.region_b = ko.observable('any');
    self.ucsc_url = ko.computed(function() {
        var url = "http://genome.ucsc.edu/cgi-bin/hgTracks?db=" + self.chosenAssembly();
        url += "&hubUrl=https://bimsbproxy.mdc-berlin.de/dorina2/dorinaHub/hub.txt"
        url += "&position="
        return url;
    }, self);

    self.combinatorialOperation = ko.observable('or');

    self.readableSetOperation = ko.computed(function() {
        switch (self.combinatorialOperation()) {
            case 'or':
                return "found in set A or set B";
            case 'and':
                return "found in set A and set B";
            case 'xor':
                return "found either in set A or in set B, but not in both";
            case 'not':
                return "found in set A but not in set B";
        }
    }, self);

    self.get_regulators = function(assembly) {
        var search_path = "regulators/" + assembly;
        return net.getJSON(search_path).then(function(data) {
            self.regulators.removeAll();
            for (var i in data) {
                self.regulators.push(data[i]);
            }
        });
    };

    self.show_simple_search = function() {
        self.loading_regulators(true);
        setTimeout(function() {
            self.get_regulators(self.chosenAssembly()).then(function() {
                $('#chooseDatabase').collapse('hide');
                $('#search').collapse('show');
                $('#regulators').selectize({
                    options: self.regulators(),
                    create: false,
                    valueField: 'id',
                    labelField: 'summary',
                    searchField: 'summary',
                    render: {
                        option: function(item, escape) {
                            return '<div><span class="regulator">' + escape(item.summary) +
                                   '</span><br><span class="description">' + escape(item.description) +
                                   '</span></div>';
                        }
                    }
                });
                $('#regulators_setb').selectize({
                    options: self.regulators(),
                    create: false,
                    valueField: 'id',
                    labelField: 'summary',
                    searchField: 'summary',
                    render: {
                        option: function(item, escape) {
                            return '<div><span class="regulator">' + escape(item.summary) +
                                   '</span><br><span class="description">' + escape(item.description) +
                                   '</span></div>';
                        }
                    }
                });
                self.loading_regulators(false);
            });
        }, 10);
    };

    self.run_search = function(keep_data) {
        var search_data = {
            set_a: self.selected_regulators(),
            assembly: self.chosenAssembly(),
            match_a: self.match_a(),
            region_a: self.region_a(),
            genes: self.candidate_genes(),
            offset: self.offset()
        };

        // if there's any selection made for set B regulators,
        // send set B data
        if (self.selected_regulators_setb().length > 0) {
            search_data.set_b = self.selected_regulators_setb()
            search_data.match_b= self.match_b();
            search_data.region_b = self.region_b();
            search_data.combinatorial_op = self.combinatorialOperation();
        }

        self.pending(true);
        if (!keep_data) {
            self.results.removeAll();
        }
        return net.post('search', search_data).then(function(data) {
            self.poll_result(data.uuid);
        });
    };

    self.poll_result = function(uuid) {
        var url = 'status/' + uuid;
        net.getJSON(url).then(function(data) {
            if (data.state == 'pending') {
                setTimeout(function() {
                    self.poll_result(uuid);
                }, self.retry_after);
                return;
            }
            return self.get_results(uuid);
        });
    };


    self.get_results = function(uuid, more) {
        var url = 'result/' + uuid;
        if (more) {
            url += '/' + self.offset();
        }

        net.getJSON(url).then(function(data) {
            self.pending(false);
            self.more_results(data.more_results);
            for (var i in data.results) {
                self.results.push(data.results[i]);
            }
            if (data.more_results && data.next_offset) {
                self.offset(data.next_offset);
                self.uuid(uuid);
            }
        });
    };

    self.reset_search_state = function() {
        self.more_results(false);
        self.offset(0);
        self.match_a('any');
        self.match_b('any');
        self.region_a('any');
        self.region_b('any');
        self.genes('');
        self.uuid('');
    };

    self.clear_selections = function() {
        $('#rbps')[0].selectize.clear();
        $('#mirnas')[0].selectize.clear();
        $('#rbps_setb')[0].selectize.clear();
        $('#mirnas_setb')[0].selectize.clear();
    };

    self.candidate_genes = ko.computed(function() {
        if (self.genes() == '') {
            return 'all';
        }
        return self.genes();
    });


    /* These functions break the ViewModel abstraction a bit, as they trigger
     * view changes, but I can't think of a better way to implement this at the
     * moment */
    self.run_simple_search = function() {
        self.run_search(false);
        $('#search').collapse('hide');
        $('#results').collapse('show');
    };

    self.load_more_results = function() {
        self.get_results(self.uuid(), true);
    };

    self.new_search = function() {
        self.reset_search_state();
        $('#search').collapse('hide');
        $('#results').collapse('hide');
        $('#chooseDatabase').collapse('show');
    };

}

function SetViewModel(view_model) {
        $(document).data('view_model', view_model);
}

function GetViewModel() {
        return $(document).data('view_model');
}

