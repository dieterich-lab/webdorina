describe('DoRiNAResult', function() {

    var line = 'chr1	doRiNA2	gene	1	1000	.	+	.	ID=gene01.01	chr1	250	260	PARCLIP#scifi*scifi_cds	6	+	250	260';
    var no_result = '\t\t\t\t\t\t\t\tNo results found';
    var res;

    beforeEach(function() {
        res = new DoRiNAResult(line);
        no_res = new DoRiNAResult(no_result);
    });

    afterEach(function() {
        res = null;
        no_res = null;
    });


    describe('#annotations', function() {
        it('should return the correct field if present', function() {
            res.annotations().should.eql('PARCLIP#scifi*scifi_cds');
        });

        it('should return unknown if the field is absent', function() {
            res = new DoRiNAResult('');
            res.annotations().should.eql('unknown#unknown*unknown');
        });
    });


    describe('#track', function() {
        it('should be parsed correctly', function() {
            res.track().should.eql('scifi');
        });

        it('should deal with invalid fields', function() {
            res = new DoRiNAResult('\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t');
            res.track().should.eql('unknown');
        });

        it('should not display anything in error state', function() {
            no_res.track().should.eql('');
        });
    });


    describe('#data_source', function() {
        it('should be parsed correctly', function() {
            res.data_source().should.eql('PARCLIP');
        });

        it('should deal with invalid fields', function() {
            res = new DoRiNAResult('\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t');
            res.data_source().should.eql('unknown');
        });

        it('should not display anything in error state', function() {
            no_res.data_source().should.eql('');
        });
    });


    describe('#site', function() {
        it('should be parsed correctly', function() {
            res.site().should.eql('scifi_cds');
        });

        it('should deal with invalid fields', function() {
            res = new DoRiNAResult('\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t');
            res.site().should.eql('unknown');
        });

        it('should not display anything in error state', function() {
            no_res.site().should.eql('');
        });
    });


    describe('#gene', function() {
        it('should be parsed correctly', function() {
            res.gene().should.eql('gene01.01');
        });

        it('should deal with invalid fields', function() {
            res = new DoRiNAResult('\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t');
            res.gene().should.eql('unknown');
        });

        it('should display error output if needed', function() {
            no_res.gene().should.eql('No results found');
        });
    });


    describe('#score', function() {
        it('should be parsed correctly', function() {
            res.score().should.eql('6');
        });

        it('should deal with invalid fields', function() {
            res = new DoRiNAResult('');
            res.score().should.eql('-1');
        });

        it('should not display anything in error state', function() {
            no_res.score().should.eql('');
        });
    });


    describe('#location', function() {
        it('should be parsed correctly', function() {
            res.location().should.eql('chr1:250-260');
        });

        it('should deal with invalid fields', function() {
            res = new DoRiNAResult('');
            res.location().should.eql('unknown:0-0');
        });

        it('should not display anything in error state', function() {
            no_res.location().should.eql('');
        });
    });


    describe('#strand', function() {
        it('should be parsed correctly', function() {
            res.strand().should.eql('+');
        });

        it('should deal with invalid fields', function() {
            res = new DoRiNAResult('');
            res.strand().should.eql('.');
        });

        it('should not display anything in error state', function() {
            no_res.strand().should.eql('');
        });
    });

    describe('#feature_strand', function() {
        it('should be parsed correctly', function() {
            res.feature_strand().should.eql('+');
        });

        it('should deal with invalid fields', function() {
            res = new DoRiNAResult('');
            res.feature_strand().should.eql('.');
        });

        it('should not display anything in error state', function() {
            no_res.feature_strand().should.eql('');
        });
    });
});
