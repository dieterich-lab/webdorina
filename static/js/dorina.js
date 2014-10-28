function DoRiNAResult(line) {
    var self = this;
    self.cols = line.split('\t');
    self.error_state = ko.observable(false);

    self.annotations = ko.computed(function() {
        return (self.cols.length > 12) ? self.cols[12] : 'unknown#unknown*unknown';
    }, self);

    self.ann_regex = /(.*)#(.*)\*(.*)/;

    self.track = ko.computed(function() {
        var match = self.annotations().match(self.ann_regex);

        if (self.error_state()) {
            return '';
        }

        if (match) {
            return match[2];
        }

        if (self.annotations().indexOf('|') > -1) {
            match = self.annotations().split('|');
            return match[0];
        }

        var track = self.annotations();
        if (track == '') {
            track = 'unknown';
        }
        return track;
    }, self);

    self.data_source = ko.computed(function() {
        var match = self.annotations().match(self.ann_regex);
        if (self.error_state()) {
            return '';
        }

        if (match) {
            return match[1];
        }

        if (self.annotations().indexOf('|') > -1) {
            match = self.annotations().split('|');
            return match[1];
        }

        return 'CUSTOM';
    }, self);

    self.site = ko.computed(function() {
        var match = self.annotations().match(self.ann_regex);
        if (self.error_state()) {
            return '';
        }

        if (match) {
            return match[3];
        }

        if (self.annotations().indexOf('|') > -1) {
            match = self.annotations().split('|');
            return match[0];
        }

        var site = self.annotations();
        if (site == '') {
            site = 'unknown';
        }
        return site;
    }, self);

    self.gene = ko.computed(function() {
        if (self.cols.length < 9) {
            return 'unknown';
        }
        var keyvals = self.cols[8];
        var match = keyvals.match(/ID=(.*?)($|;\w+.*?=.*)/);
        if (match) {
            return match[1];
        }

        if (keyvals == '') {
            return 'unknown';
        }

        self.error_state(true);
        return keyvals;
    }, self);

    self.score = ko.computed(function() {
        if (self.error_state()) {
            return '';
        }
        return (self.cols.length > 13) ? self.cols[13] : '-1';
    }, self);

    self.location = ko.computed(function() {
        if (self.error_state()) {
            return '';
        }
        if (self.cols.length < 5) {
            return 'unknown:0-0';
        }
        return self.cols[0] + ':' + self.cols[3] + '-' + self.cols[4];
    }, self);

    self.feature_location = ko.computed(function() {
        if (self.error_state()) {
            return '';
        }
        if (self.cols.length < 12) {
            return 'unknown:0-0';
        }
        return self.cols[9] + ':' + self.cols[10] + '-' + self.cols[11];
    }, self);

    self.strand = ko.computed(function() {
        if (self.error_state()) {
            return '';
        }
        return (self.cols.length > 6) ? self.cols[6] : '.';
    }, self);

    self.feature_strand = ko.computed(function() {
        if (self.error_state()) {
            return '';
        }
        return (self.cols.length > 14) ? self.cols[14] : '.';
    }, self);
};

function DoRiNAViewModel(net, uuid, custom_regulator) {
    var self = this;
    self.mode = ko.observable("choose_db");
    self.retry_after = 1000;
    self.loading_regulators = ko.observable(false);
    self.uuid = ko.observable(uuid);
    self.custom_regulator = ko.observable(custom_regulator);

    self.chosenAssembly = ko.observable();

    self.regulators = ko.observableArray([]);
    self.regulator_types = ko.observableArray([]);
    self.selected_regulators = ko.observableArray([]);
    self.selected_regulators_setb = ko.observableArray([]);

    self.results = ko.observableArray([]);
    self.total_results = ko.observable(0);

    self.more_results = ko.observable(false);
    self.offset = ko.observable(0);
    self.pending = ko.observable(false);

    self.genes = ko.observableArray([]);
    self.match_a = ko.observable('any');
    self.region_a = ko.observable('any');

    self.match_b = ko.observable('any');
    self.region_b = ko.observable('any');

    self.use_window_a = ko.observable(false);
    self.window_a = ko.observable(0);
    self.use_window_b = ko.observable(false);
    self.window_b = ko.observable(0);

    self.ucsc_url = ko.computed(function() {
        var url = "http://genome.ucsc.edu/cgi-bin/hgTracks?db=" + self.chosenAssembly();
        url += "&hubUrl=http://dorina2.mdc-berlin.de/dorinaHub/hub.txt"
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

    self.combinatorialOpImagePath = ko.computed(function() {
        return "/static/images/" + self.combinatorialOperation() + ".svg";
    }, self);

    self.get_regulators = function(assembly) {
        var search_path = "api/v1.0/regulators/" + assembly;
        return net.getJSON(search_path).then(function(data) {
            self.regulators.removeAll();
            self.regulator_types.removeAll();
            var regulator_types = {};

            if (self.custom_regulator()) {
                self.regulators.push({
                    id: self.uuid(),
                    experiment: 'CUSTOM',
                    summary: 'uploaded custom regulator',
                    description: 'Custom regulator uploaded by user'
                });
                regulator_types['CUSTOM'] = true;
            }

            for (var i in data) {
                regulator_types[data[i].experiment] = true;
                self.regulators.push(data[i]);
            }
            for (var e in regulator_types) {
                self.regulator_types.push({id: e});
            }

        });
    };

    self.show_simple_search = function() {
        self.loading_regulators(true);
        setTimeout(function() {
            self.get_regulators(self.chosenAssembly()).then(function() {
                $('#chooseDatabase').collapse('hide');
                $('#search').collapse('show');
                self.mode('search');

                var $genes, genes;
                var $regulators, regulators;
                var $regulators_setb, regulators_setb;
                var $shown_types, shown_types;
                var $shown_types_setb, shown_types_setb;

                $genes = $('#genes').selectize({
                    options: [],
                    valueField: 'id',
                    labelField: 'id',
                    searchField: 'id',
                    create: false,
                    load: function(query, callback) {
                        if (query.length == 0) {
                            return callback();
                        }
                        net.getJSON('api/v1.0/genes/' + self.chosenAssembly() + '/' + query).then(function(res) {

                            callback(res.genes.map(function(r) {return {id: r}}));
                        });
                    }
                });

                $shown_types = $('#shown-types').selectize({
                    options: self.regulator_types(),
                    valueField: 'id',
                    labelField: 'id',
                    onChange: function(values) {
                        regulators.disable();
                        regulators.clearOptions();
                        if (values && values.length > 0) {
                            var filtered_regs = self.regulators().filter(function(reg) {
                                return values.indexOf(reg.experiment) > -1
                            });

                            for (var i in filtered_regs) {
                                regulators.addOption(filtered_regs[i]);
                            }
                        }

                        regulators.refreshOptions();
                        regulators.enable();
                    }
                });
                shown_types = $shown_types[0].selectize;

                $shown_types_setb = $('#shown-types-setb').selectize({
                    options: self.regulator_types(),
                    valueField: 'id',
                    labelField: 'id',
                    onChange: function(values) {
                        regulators_setb.disable();
                        regulators_setb.clearOptions();
                        if (values && values.length > 0) {
                            var filtered_regs = self.regulators().filter(function(reg) {
                                return values.indexOf(reg.experiment) > -1
                            });

                            for (var i in filtered_regs) {
                                regulators_setb.addOption(filtered_regs[i]);
                            }
                        }

                        regulators_setb.refreshOptions();
                        regulators_setb.enable();
                    }
                });
                shown_types_setb = $shown_types_setb[0].selectize;

                $regulators = $('#regulators').selectize({
                    options: self.regulators(),
                    create: false,
                    valueField: 'id',
                    labelField: 'summary',
                    searchField: 'summary',
                    optgroups: self.regulator_types(),
                    optgroupField: 'experiment',
                    optgroupValueField: 'id',
                    optgroupLabelField: 'id',
                    render: {
                        option: function(item, escape) {
                            return '<div><span class="regulator">' + escape(item.summary) +
                                   '</span><br><span class="description">(' + escape(item.sites) + ' sites) '
                                   + escape(item.description) + '</span></div>';
                        }
                    }
                });
                regulators = $regulators[0].selectize;

                $regulators_setb = $('#regulators_setb').selectize({
                    options: self.regulators(),
                    create: false,
                    valueField: 'id',
                    labelField: 'summary',
                    searchField: 'summary',
                    optgroups: self.regulator_types(),
                    optgroupField: 'experiment',
                    optgroupValueField: 'id',
                    optgroupLabelField: 'id',
                    render: {
                        option: function(item, escape) {
                            return '<div><span class="regulator">' + escape(item.summary) +
                                   '</span><br><span class="description">(' + escape(item.sites) + ' sites) '
                                   + escape(item.description) + '</span></div>';
                        }
                    }
                });
                regulators_setb = $regulators_setb[0].selectize;

                for (var i in self.regulator_types()) {
                    var reg = self.regulator_types()[i].id
                    shown_types.addItem(reg);
                    shown_types_setb.addItems(reg);
                }

                if (self.custom_regulator()) {
                    regulators.addItem(self.uuid());
                }

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
            genes: self.genes(),
            offset: self.offset(),
            uuid: self.uuid()
        };

        if (self.use_window_a()) {
            search_data.window_a = self.window_a();
        }
        // if there's any selection made for set B regulators,
        // send set B data
        if (self.selected_regulators_setb().length > 0) {
            search_data.set_b = self.selected_regulators_setb()
            search_data.match_b= self.match_b();
            search_data.region_b = self.region_b();
            search_data.combinatorial_op = self.combinatorialOperation();
            if (self.use_window_b()) {
                search_data.window_b = self.window_b();
            }
        }


        self.pending(true);
        if (!keep_data) {
            self.results.removeAll();
        }
        return net.post('api/v1.0/search', search_data).then(function(data) {
            self.uuid(data.uuid);
            self.poll_result(data.uuid);
        });
    };

    self.poll_result = function(uuid) {
        var url = 'api/v1.0/status/' + uuid;
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
        var url = 'api/v1.0/result/' + uuid;
        if (more) {
            url += '/' + self.offset();
        }

        net.getJSON(url).then(function(data) {
            self.pending(false);
            self.more_results(data.more_results);
            self.total_results(data.total_results);
            for (var i in data.results) {
                self.results.push(new DoRiNAResult(data.results[i]));
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
    };

    self.clear_selections = function() {
        $('#regulators')[0].selectize.clear();
        $('#regulators_setb')[0].selectize.clear();
    };

    /* These functions break the ViewModel abstraction a bit, as they trigger
     * view changes, but I can't think of a better way to implement this at the
     * moment */
    self.run_simple_search = function() {
        self.run_search(false);
        $('#search').collapse('hide');
        $('#results').collapse('show');
        self.mode('results');
    };

    self.load_more_results = function() {
        self.get_results(self.uuid(), true);
    };

    self.new_search = function() {
        self.reset_search_state();
        $('#search').collapse('hide');
        $('#results').collapse('hide');
        $('#chooseDatabase').collapse('show');
        self.mode('choose_db');
    };

}

function RegulatorViewModel(net) {
    var self = this;
    self.genomes = ko.observableArray([]);
    self.assemblies = ko.observableArray([]);
    self.regulators = ko.observableArray([]);

    self.selected_assembly = ko.observable();

    self.init = function() {
        self.get_genomes().then(function() {
            var promises = [];
            for (var i in self.genomes()) {
                var genome = self.genomes()[i].id;
                promises.push(self.get_assemblies(genome))
            }

            $.when.apply(null, promises).then(function() {
                $('#assembly').selectize({
                    valueField: 'id',
                    labelField: 'id',
                    searchField: 'id',
                    options: self.assemblies(),
                    sortField: [{ field: 'weight', direction: 'desc'}],
                    optgroupField: 'genome',
                    optgroupValueField: 'id',
                    optgroups: self.genomes(),
                    plugins: ['optgroup_columns'],
                    render: {
                        optgroup_header: function(data, escape) {
                            return '<div class="optgroup-header">' + escape(data.label) +
                                   ' (<span class="scientific">' + escape(data.scientific) +
                                   '</span>)</div>';
                         }
                    },
                    onChange: function(value) {
                        if (!value) {
                            return;
                        }
                        self.get_regulators(value);
                    }
                });
            });
        });
    };

    self.get_genomes = function() {
        return net.getJSON('api/v1.0/genomes').then(function(data) {
            self.genomes = ko.observableArray(data.genomes);
        });
    };

    self.get_assemblies = function(genome) {
        return net.getJSON('api/v1.0/assemblies/' + genome).then(function(data) {
            for (var i in data.assemblies) {
                self.assemblies.push(data.assemblies[i])
            }
        });
    };

    self.get_regulators = function(assembly) {
        return net.getJSON('api/v1.0/regulators/' + assembly).then(function(data) {
            self.regulators.removeAll();
            self.regulators.extend({ rateLimit: 100 });
            for (var reg in data) {
                self.regulators.push(data[reg]);
            }
        });
    };

}

function SetViewModel(view_model) {
        $(document).data('view_model', view_model);
}

function GetViewModel() {
        return $(document).data('view_model');
}

