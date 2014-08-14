var FakeNet = function() {
    self = this;
    self.return_data = [];
    self.expected_url = [];
    self.expected_data = [];

    self.getJSON = function(url) {
        var deferred = $.Deferred();
        var data = self.return_data.shift();
        var exp_url = self.expected_url.shift();

        url.should.eql(exp_url);
        deferred.resolve(data);
        return deferred.promise();
    };

    self.post = function(url, data) {
        var deferred = $.Deferred();
        var return_data = self.return_data.shift();
        var exp_url = self.expected_url.shift();
        var exp_data = self.expected_data.shift();

        url.should.eql(exp_url);
        data.should.eql(exp_data);

        deferred.resolve(return_data);
        return deferred.promise();
    };

    self.ajax = function(options) {
        var deferred = $.Deferred();
        var return_data = self.return_data.shift();
        var exp_url = self.expected_url.shift();
        var exp_data = self.expected_data.shift();

        options.url.should.eql(exp_url);
        options.data.should.eql(exp_data);

        deferred.reslove(return_data);
        return deferred.promise();
    };
};


describe('DoRiNAViewModel', function() {
    var fn;
    var vm;

    beforeEach(function() {
        fn = new FakeNet();
        vm = new DoRiNAViewModel(fn);
    });

    afterEach(function() {
        fn = undefined;
        vm = undefined;
    });


    describe('#regulators', function() {
        it('should not have miRNAs or RBPs selected', function() {
            vm.mirnas().should.have.length(0);
            vm.rbps().should.have.length(0);
        });

        it('should have miRNAs and RBPs loaded after getting the regulators', function() {
            fn.expected_url.push('regulators/hg19');
            fn.return_data.push({'RBP': {'fake_rbp': {} }, 'miRNA': {'fake_mirna': {} } });

            return vm.get_regulators('hg19').then(function() {
                vm.mirnas().should.have.length(1);
                vm.rbps().should.have.length(1);
            });
        });
    });


    describe('#search', function() {
        it('should use the selected set_a values to build the post request', function() {
            fn.expected_url.push('search');
            fn.return_data.push({'state': 'done'});
            fn.expected_data.push({
                'set_a': ['fake_rbp', 'fake_mirna'],
                'assembly': 'hg19',
                'match_a': 'any',
                'region_a': 'CDS',
                'genes': 'all',
                'offset': 0
            });
            vm.selected_rbps().push('fake_rbp');
            vm.selected_mirnas().push('fake_mirna');
            vm.chosenAssembly('hg19');
            vm.region_a('CDS');

            return vm.run_search(false);
        });

        it('should use the selected set_a and set_b values to build the post request', function() {
            fn.expected_url.push('search');
            fn.return_data.push({'state': 'done'});
            fn.expected_data.push({
                'set_a': ['fake_rbp'],
                'assembly': 'hg19',
                'match_a': 'any',
                'region_a': 'CDS',
                'genes': 'all',
                'offset': 0,
                'set_b': ['fake_mirna'],
                'match_b': 'any',
                'region_b': 'CDS',
                'combinatorial_op': 'or'
            });
            vm.selected_rbps().push('fake_rbp');
            vm.selected_mirnas_setb().push('fake_mirna');
            vm.chosenAssembly('hg19');
            vm.region_a('CDS');
            vm.region_b('CDS');
            vm.combinatorialOperation('or');

            return vm.run_search(false);
        });

        it('should retry the search if state=pending', function(done) {
            fn.expected_url.push('search');
            fn.expected_url.push('search');
            fn.return_data.push({'state': 'pending'});
            fn.return_data.push({'state': 'done'});
            fn.expected_data.push({
                'set_a': ['fake_rbp', 'fake_mirna'],
                'assembly': 'hg19',
                'match_a': 'any',
                'region_a': 'any',
                'genes': 'all',
                'offset': 0
            });
            fn.expected_data.push({
                'set_a': ['fake_rbp', 'fake_mirna'],
                'assembly': 'hg19',
                'match_a': 'any',
                'region_a': 'any',
                'genes': 'all',
                'offset': 0
            });
            vm.selected_rbps().push('fake_rbp');
            vm.selected_mirnas().push('fake_mirna');
            vm.chosenAssembly('hg19');
            vm.retry_after = 1;

            vm.run_search(false);
            /* wait for the retry to fire */
            setTimeout(function() {
                fn.expected_url.should.have.length(0);
                done();
            }, 2);

        });

        it('should set the offset to the next_offset if there are more results', function() {
            fn.expected_url.push('search');
            fn.return_data.push({
                'state': 'done',
                'next_offset': 23,
                'more_results': true
            });
            fn.expected_data.push({
                'set_a': ['fake_rbp', 'fake_mirna'],
                'assembly': 'hg19',
                'match_a': 'any',
                'region_a': 'any',
                'genes': 'all',
                'offset': 0
            });
            vm.selected_rbps().push('fake_rbp');
            vm.selected_mirnas().push('fake_mirna');
            vm.chosenAssembly('hg19');

            vm.run_search(false);
            vm.offset().should.eql(23);
        });

        it('should not set the offset if there are no more results', function() {
            fn.expected_url.push('search');
            fn.return_data.push({
                'state': 'done',
                'next_offset': 23,
                'more_results': false
            });
            fn.expected_data.push({
                'set_a': ['fake_rbp', 'fake_mirna'],
                'assembly': 'hg19',
                'match_a': 'any',
                'region_a': 'any',
                'genes': 'all',
                'offset': 0
            });
            vm.selected_rbps().push('fake_rbp');
            vm.selected_mirnas().push('fake_mirna');
            vm.chosenAssembly('hg19');

            vm.run_search(false);
            vm.offset().should.eql(0);
        });
    });


    describe('#reset_search_state', function() {
        it('should reset the more_results field', function() {
            vm.more_results(true);
            vm.more_results().should.be.true;
            vm.reset_search_state();
            vm.more_results().should.be.false;
        });

        it('should reset the offset field', function() {
            vm.offset(23);
            vm.offset().should.eql(23);
            vm.reset_search_state();
            vm.offset().should.eql(0);
        });

        it('should reset the match_a field', function() {
            vm.match_a('all');
            vm.match_a().should.eql('all');
            vm.reset_search_state();
            vm.match_a().should.eql('any');
        });

        it('should reset the region_a field', function() {
            vm.region_a('CDS');
            vm.region_a().should.eql('CDS');
            vm.reset_search_state();
            vm.region_a().should.eql('any');
        });

        it('should reset the match_b field', function() {
            vm.match_b('all');
            vm.match_b().should.eql('all');
            vm.reset_search_state();
            vm.match_b().should.eql('any');
        });

        it('should reset the region_b field', function() {
            vm.region_b('CDS');
            vm.region_b().should.eql('CDS');
            vm.reset_search_state();
            vm.region_b().should.eql('any');
        });

        it('should reset the genes field', function() {
            vm.genes('foo');
            vm.genes().should.eql('foo');
            vm.reset_search_state();
            vm.genes().should.eql('');
        });
    });
});
