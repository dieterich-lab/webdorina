describe('Regulator', function() {
    var name = 'test_regulator',
        data = {'summary': 'test summary',
                'description': 'test description',
                'methods': 'test methods',
                'references': 'test references'};
    var reg = new Regulator(name, data);

    describe('#name', function() {
        it('should be the name passed to the constructor', function() {
            reg.name.should.eql(name);
        });
    });

    describe('#summary', function() {
        it('should be taken from the data object', function() {
            reg.summary.should.eql(data.summary);
        });
    });

    describe('#description', function() {
        it('should be taken from the data object', function() {
            reg.description.should.eql(data.description);
        });
    });

    describe('#references', function() {
        it('should be taken from the data object', function() {
            reg.references.should.eql(data.references);
        });
    });
});
