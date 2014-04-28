describe('DoRiNAViewModel', function() {
    var vm = new DoRiNAViewModel();
    describe('clades', function() {
        it('should be an empty array on instantiation', function() {
            vm.clades().should.have.length(0);
        });
    });
});
