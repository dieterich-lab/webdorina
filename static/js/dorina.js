function Regulator(name, data) {
    var self = this;

    self.name = name;
    self.summary = data.summary;
    self.description = data.description;
    self.methods = data.methods;
    self.references = data.references;
}

function DoRiNAViewModel() {
    var self = this;
    self.clades = ko.observableArray([]);
    self.genomes = ko.observableArray([]);
    self.assemblies = ko.observableArray([]);

    self.chosenClade = ko.observable();
    self.chosenGenome = ko.observable();
    self.chosenAssembly = ko.observable();

    self.rbps = ko.observableArray([]);
    self.selected_rbps = ko.observableArray([]);

    self.mirnas = ko.observableArray([]);
    self.selected_mirnas = ko.observableArray([]);

    self.results = ko.observableArray([]);

    self.get_clades = function() {
        $.getJSON("clades", function(data) {
            self.clades.removeAll();
            for (var i in data.clades) {
                self.clades.push(data.clades[i]);
            }
        });
    };

    self.get_genomes = function(clade) {
        $.getJSON("genomes/" + clade, function(data) {
            self.genomes.removeAll();
            for (var i in data.genomes) {
                self.genomes.push(data.genomes[i]);
            }
        });
    };

    self.get_assemblies = function(clade, genome) {
        $.getJSON("assemblies/" + clade + "/" + genome, function(data) {
            self.assemblies.removeAll();
            for (var i in data.assemblies) {
                self.assemblies.push(data.assemblies[i]);
            }
        });
    };

    self.show_simple_search = function() {
        var search_path = "regulators/";
        search_path += self.chosenClade() + "/";
        search_path += self.chosenGenome() + "/";
        search_path += self.chosenAssembly();

        $.getJSON(search_path, function(data) {
            self.rbps.removeAll();
            self.mirnas.removeAll();
            for (var i in data['RBP']) {
                self.rbps.push(new Regulator(i, data['RBP'][i]));
            }
            for (var i in data['miRNA']) {
                self.mirnas.push(new Regulator(i, data['miRNA'][i]));
            }
            $('#chooseDatabase').collapse('hide');
            $('#search').collapse('show');
        });
    };

    self.run_simple_search = function() {
        var regulators = self.selected_rbps() + self.selected_mirnas();
        var search_data = {
            regulators: regulators,
            assembly: self.chosenAssembly()
        };
        $('#search').collapse('hide');
        $('#results').collapse('show');
        $.post('search', search_data, function(data) {
            console.log(data.results);
            self.results.removeAll();
            for (var i in data.results) {
                self.results.push(data.results[i]);
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

