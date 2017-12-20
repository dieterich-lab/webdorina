webdorina
=========

web front-end for the doRiNA database


Installation
------------

```
$ git clone https://github.com/dieterich-lab/webdorina
$ cd webdorina
$ pip install -r requirements.txt 
```

Also make sure to have a Redis server running.

Running the Web UI
------------------

To run the development / test server:

```
redis-server &
python3 webdorina.py &
rqworker &
```

For a deployment setup, you will want to run a proper WSGI server.

License
-------

webdorina is licensed under the GNU Affero General Public Licence (AGPL) version 3.
See `LICENSE` file for details.

