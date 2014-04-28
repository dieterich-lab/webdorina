test:
	nosetests -v

coverage:
	nosetests --with-coverage --cover-html --cover-package="webdorina,run"

.PHONY: test coverage
