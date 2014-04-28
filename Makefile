test: pythontest jstest

pythontest:
	nosetests -v

jstest:
	mocha-phantomjs test/runner.html


coverage:
	nosetests --with-coverage --cover-html --cover-package="webdorina,run"

.PHONY: test pythontest jstest coverage
