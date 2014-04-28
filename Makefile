test:
	nosetests -v
	mocha-phantomjs test/runner.html

coverage:
	nosetests --with-coverage --cover-html --cover-package="webdorina,run"

.PHONY: test coverage
