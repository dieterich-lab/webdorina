## python 3 migration
`pip install future`

From the parent directory run:
`futurize -u *.py test/*.py maintenance/*.py`
`futurize --stage1 *.py test/*.py maintenance/*.py`
`futurize --stage2 *.py test/*.py maintenance/*.py`

To check changes, apply changes with the -w parameter, run test in py2
and py3.

Most error are related with mocking:
- expect unicode and got bitstring
- different order of the redis response
- changes in dorina/webdorina which were not tested

# TODO
replace timings for logging with timestamps
log info instead print()
log error for every try except errors

# How to debug rq failed workers

python3

`from redis import Redis`
`from rq import Queue`
`q = Queue('failed', connection=Redis())`
`print(q.jobs[-1].exc_info)`

Will print the stacktrace of the last failed job

