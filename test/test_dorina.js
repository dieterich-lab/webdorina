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
        vm = new DoRiNAViewModel(fn, 'fake-uuid');
    });

    afterEach(function() {
        fn = undefined;
        vm = undefined;
    });


    describe('#regulators', function() {
        it('should not have miRNAs or RBPs loaded', function() {
            vm.regulators().should.have.length(0);
        });

        it('should have miRNAs and RBPs loaded after getting the regulators', function() {
            fn.expected_url.push('api/v1.0/regulators/hg19');
            fn.return_data.push({'fake_rbp': {}, 'fake_mirna': {} });

            return vm.get_regulators('hg19').then(function() {
                vm.regulators().should.have.length(2);
            });
        });

        it('should have the custom regulator entry if there is a custom regulator', function() {
            vm.custom_regulator(true);
            fn.expected_url.push('api/v1.0/regulators/hg19');
            fn.return_data.push({'fake_rbp': {}, 'fake_mirna': {} });

            return vm.get_regulators('hg19').then(function() {
                vm.regulators().should.have.length(3);
                vm.regulators()[0].id.should.eql(vm.uuid());
            });
        });

    });


    describe('#search', function() {
        it('should use the selected set_a values to build the post request', function() {
            fn.expected_url.push('api/v1.0/search');
            fn.return_data.push({'uuid': 'fake-uuid', 'state': 'done'});
            fn.expected_data.push({
                'set_a': ['fake_rbp', 'fake_mirna'],
                'assembly': 'hg19',
                'match_a': 'any',
                'region_a': 'CDS',
                'genes': 'all',
                'offset': 0,
                'uuid': 'fake-uuid'
            });
            vm.poll_result = function(uuid) {
                uuid.should.eql('fake-uuid');
            };
            vm.selected_regulators().push('fake_rbp');
            vm.selected_regulators().push('fake_mirna');
            vm.chosenAssembly('hg19');
            vm.region_a('CDS');

            return vm.run_search(false);
        });

        it('should use the selected set_a and set_b values to build the post request', function() {
            fn.expected_url.push('api/v1.0/search');
            fn.return_data.push({'uuid': 'fake-uuid', 'state': 'done'});
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
                'combinatorial_op': 'or',
                'uuid': 'fake-uuid'
            });
            vm.poll_result = function(uuid) {
                uuid.should.eql('fake-uuid');
            };
            vm.selected_regulators().push('fake_rbp');
            vm.selected_regulators_setb().push('fake_mirna');
            vm.chosenAssembly('hg19');
            vm.region_a('CDS');
            vm.region_b('CDS');
            vm.combinatorialOperation('or');

            return vm.run_search(false);
        });

        it('should send all slop-related settings if use_slop is true', function() {
            fn.expected_url.push('api/v1.0/search');
            fn.return_data.push({'uuid': 'fake-uuid', 'state': 'done'});
            fn.expected_data.push({
                'set_a': ['fake_rbp', 'fake_mirna'],
                'assembly': 'hg19',
                'match_a': 'any',
                'region_a': 'CDS',
                'genes': 'all',
                'offset': 0,
                'slop': 23,
                'uuid': 'fake-uuid'
            });
            vm.poll_result = function(uuid) {
                uuid.should.eql('fake-uuid');
            };
            vm.selected_regulators().push('fake_rbp');
            vm.selected_regulators().push('fake_mirna');
            vm.chosenAssembly('hg19');
            vm.region_a('CDS');
            vm.slop(23);
            vm.use_slop(true);

            return vm.run_search(false);
        });
    });

    describe('#poll_result', function() {
        it('should keep polling while state=pending', function(done) {
            fn.expected_url.push('api/v1.0/status/fake-uuid');
            fn.expected_url.push('api/v1.0/status/fake-uuid');
            fn.return_data.push({'state': 'pending'});
            fn.return_data.push({'state': 'done'});
            vm.retry_after = 1;
            vm.get_results = function(uuid) {
                uuid.should.eql('fake-uuid');
            };

            vm.poll_result('fake-uuid');
            /* wait for the retry to fire */
            setTimeout(function() {
                fn.expected_url.should.have.length(0);
                done();
            }, 2);

        });
    });

    describe('#get_results', function() {
        it('should set the offset to the next_offset if there are more results', function() {
            fn.expected_url.push('api/v1.0/result/fake-uuid');
            fn.return_data.push({
                'state': 'done',
                'next_offset': 23,
                'more_results': true
            });

            vm.get_results('fake-uuid');
            vm.offset().should.eql(23);
        });

        it('should not set the offset if there are no more results', function() {
            fn.expected_url.push('api/v1.0/result/fake-uuid');
            fn.return_data.push({
                'state': 'done',
                'next_offset': 23,
                'more_results': false
            });

            vm.get_results('fake-uuid');
            vm.offset().should.eql(0);
        });

        it('should get more resuts at the stored offset when instructed', function() {
            fn.expected_url.push('api/v1.0/result/fake-uuid/23');
            fn.return_data.push({
                'state': 'done',
                'next_offset': 42,
                'more_results': false
            });
            vm.offset(23);

            vm.get_results('fake-uuid', true);
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
