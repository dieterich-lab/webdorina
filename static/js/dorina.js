function Regulator(name, data) {
    var self = this;

    self.name = name;
    self.summary = data.summary;
    self.description = data.description;
    self.methods = data.methods;
    self.references = data.references;
}

function DoRiNAViewModel(net) {
    var self = this;
    self.retry_after = 1000;
    self.clades = ko.observableArray([]);
    self.genomes = ko.observableArray([]);
    self.assemblies = ko.observableArray([]);

    self.chosenClade = ko.observable();
    self.chosenGenome = ko.observable();
    self.chosenAssembly = ko.observable();

    self.rbps = ko.observableArray([]);
    self.selected_rbps = ko.observableArray([]);
    self.selected_rbps_setb = ko.observableArray([]);

    self.mirnas = ko.observableArray([]);
    self.selected_mirnas = ko.observableArray([]);
    self.selected_mirnas_setb = ko.observableArray([]);

    self.results = ko.observableArray([]);

    self.more_results = ko.observable(false);
    self.offset = ko.observable(0);
    self.pending = ko.observable(true);

    self.genes = ko.observable('');
    self.match_a = ko.observable('any');
    self.region_a = ko.observable('any');

    self.match_b = ko.observable('any');
    self.region_b = ko.observable('any');

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

    self.get_clades = function() {
        return net.getJSON("clades").then(function(data) {
            self.clades.removeAll();
            for (var i in data.clades) {
                self.clades.push(data.clades[i]);
            }
        });
    };

    self.get_genomes = function(clade) {
        return net.getJSON("genomes/" + clade).then(function(data) {
            self.genomes.removeAll();
            for (var i in data.genomes) {
                self.genomes.push(data.genomes[i]);
            }
        });
    };

    self.get_assemblies = function(clade, genome) {
        return net.getJSON("assemblies/" + clade + "/" + genome).then(function(data) {
            self.assemblies.removeAll();
            for (var i in data.assemblies) {
                self.assemblies.push(data.assemblies[i]);
            }
        });
    };

    self.get_regulators = function(clade, genome, assembly) {
        var search_path = "regulators/";
        search_path += clade + "/";
        search_path += genome + "/";
        search_path += assembly;
        return net.getJSON(search_path).then(function(data) {
            self.rbps.removeAll();
            self.mirnas.removeAll();
            for (var i in data['RBP']) {
                self.rbps.push(new Regulator(i, data['RBP'][i]));
            }
            for (var i in data['miRNA']) {
                self.mirnas.push(new Regulator(i, data['miRNA'][i]));
            }
        });
    };

    self.show_simple_search = function() {
        self.get_regulators(self.chosenClade(), self.chosenGenome(),
                            self.chosenAssembly()).then(function() {
            $('#chooseDatabase').collapse('hide');
            $('#search').collapse('show');
        });
    };

    self.run_search = function(keep_data) {
        var regulators = [];
        var rbps = self.selected_rbps();
        var mirnas = self.selected_mirnas();

        for (var i in rbps) {
            regulators.push(rbps[i].name);
        }
        for (var i in mirnas) {
            regulators.push(mirnas[i].name);
        }

        var search_data = {
            set_a: regulators,
            assembly: self.chosenAssembly(),
            match_a: self.match_a(),
            region_a: self.region_a(),
            genes: self.candidate_genes(),
            offset: self.offset()
        };

        // if there's any selection made for set B regulators,
        // send set B data
        if (self.selected_mirnas_setb().length +
            self.selected_rbps_setb().length > 0) {
            var regulators_setb = [];
            var rbps = self.selected_rbps_setb();
            var mirnas = self.selected_mirnas_setb();

            for (var i in rbps) {
                regulators_setb.push(rbps[i].name);
            }
            for (var i in mirnas) {
                regulators_setb.push(mirnas[i].name);
            }

            search_data.set_b = regulators_setb;
            search_data.match_b= self.match_b();
            search_data.region_b = self.region_b();
            search_data.combinatorial_op = self.combinatorialOperation();
        }

        self.pending(true);
        if (!keep_data) {
            self.results.removeAll();
        }
        return net.post('search', search_data).then(function(data) {
            if (data.state == 'pending') {
                setTimeout(function() {
                    self.run_search(keep_data);
                }, self.retry_after);
                return;
            }

            self.pending(false);
            self.more_results(data.more_results);
            for (var i in data.results) {
                self.results.push(data.results[i]);
            }
            if (data.more_results && data.next_offset) {
                self.offset(data.next_offset);
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
        self.selected_mirnas.removeAll();
        self.selected_rbps.removeAll();
        self.selected_mirnas_setb.removeAll();
        self.selected_rbps_setb.removeAll();
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
        self.run_search(true);
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

