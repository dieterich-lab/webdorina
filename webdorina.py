#!/usr/bin/env python
# :set fileencoding=utf-8 :

import uuid
from os import path
from flask import Flask, render_template, jsonify, request
from flask_redis import Redis
from rq import Queue
from dorina import utils, config
import run
import json

# basic doRiNA settings
datadir = path.join(path.dirname(__file__), 'test', 'data')
#datadir = "/data/projects/doRiNA2/"
# store results for 1 day
SESSION_TTL = 3600
RESULT_TTL = 86400
REGULATORS_TTL = 3600
MAX_RESULTS = 100

app = Flask(__name__)
redis_store = Redis(app)

@app.route('/')
def index():
    return render_template('index.html', genomes=_list_genomes(), assemblies=_list_assemblies())


def _list_genomes():
    available_genomes = utils.get_genomes(datadir=datadir)
    genome_list = available_genomes.values()
    for g in genome_list:
        del g['assemblies']
    genome_list.sort(lambda x,y: cmp(x['weight'], y['weight']), reverse=True)
    genome_json = json.dumps(genome_list)
    return genome_json


def _list_assemblies():
    available_genomes = utils.get_genomes(datadir=datadir)
    assemblies = []
    for g in available_genomes.values():
        for key, val in g['assemblies'].items():
            val['id'] = key
            val['weight'] = int(key[2:])
            val['genome'] = g['id']
            assemblies.append(val)

    return json.dumps(assemblies)


@app.route('/regulators/<assembly>')
def list_regulators(assembly):

    cache_key = "regulators:{0}".format(assembly)
    if redis_store.exists(cache_key):
        regulators = json.loads(redis_store.get(cache_key))
    else:
        regulators = {}
        available_regulators = utils.get_regulators(datadir=datadir)
        for genome in available_regulators:
            if assembly in available_regulators[genome]:
                for key, val in available_regulators[genome][assembly].items():
                    regulators[key] = val

                redis_store.set(cache_key, json.dumps(regulators))
                redis_store.expire(cache_key, REGULATORS_TTL)

    return jsonify(regulators)


@app.route('/status/<uuid>')
def status(uuid):
    key = "sessions:{0}".format(uuid)
    if redis_store.exists(key):
        status = json.loads(redis_store.get(key))
    else:
        status = dict(uuid=uuid, state='expired')

    return jsonify(status)


@app.route('/search', methods=['POST'])
def search():
    unique_id = str(uuid.uuid4())
    session = "sessions:{0}".format(unique_id)

    query = {}

    query['genes'] = request.form.get('genes', u'all').split()
    query['match_a'] = request.form.get('match_a', u'any')
    query['region_a'] = request.form.get('region_a', u'any')
    query['genome'] = request.form.get('assembly', None)
    query['set_a'] = request.form.getlist('set_a[]')
    offset = request.form.get('offset', 0, int)

    query['set_b'] = request.form.getlist('set_b[]')
    # werkzeug/Flask insists on returning an empty list, but dorina.analyse
    #expects 'None'
    if query['set_b'] == []:
        query['set_b'] = None
    query['match_b'] = request.form.get('match_b', u'any')
    query['region_b'] = request.form.get('region_b', u'any')
    query['combine'] = request.form.get('combinatorial_op', u'or')

    query_key = "results:%s" % json.dumps(query, sort_keys=True)
    query_pending_key = "%s_pending" % query_key

    print query_key

    if redis_store.exists(query_key):
        session_dict = dict(uuid=unique_id, state='done')
        redis_store.expire(query_key, RESULT_TTL)
        redis_store.set(session, json.dumps(session_dict))
        redis_store.expire(session, SESSION_TTL)
        redis_store.set("results:{0}".format(session), json.dumps(dict(redirect=query_key)))
        redis_store.expire("results:{0}".format(session), SESSION_TTL)
        return jsonify(session_dict)

    elif query['genes'][0] != u'all':
        full_query = dict(query)
        full_query['genes'] = [u'all']
        full_query_key = "results:%s" % json.dumps(full_query, sort_keys=True)
        full_query_pending_key = "%s_pending" % full_query_key

        if redis_store.exists(full_query_key):
            redis_store.expire(full_query_key, RESULT_TTL)
            redis_store.set(query_pending_key, True)
            redis_store.expire(query_pending_key, 30)
            session_dict = dict(state='pending', uuid=unique_id)
            redis_store.set('sessions:{0}'.format(unique_id), json.dumps(session_dict))
            redis_store.expire('sessions:{0}'.format(unique_id), SESSION_TTL)
            q = Queue(connection=redis_store.connection)
            q.enqueue(run.filter, query['genes'], full_query_key, query_key, query_pending_key, unique_id)
            return jsonify(session_dict)

        query = full_query
        query_key = full_query_key
        query_pending_key = full_query_pending_key

    session_dict = dict(state='pending', uuid=unique_id)
    redis_store.set('sessions:{0}'.format(unique_id), json.dumps(session_dict))
    redis_store.expire('sessions:{0}'.format(unique_id), SESSION_TTL)

    if redis_store.get(query_pending_key):
        return jsonify(session_dict)

    redis_store.set(query_pending_key, True)
    redis_store.expire(query_pending_key, 30)

    q = Queue(connection=redis_store.connection)
    q.enqueue(run.run_analyse, datadir, query_key, query_pending_key, query, unique_id)

    return jsonify(session_dict)


@app.route('/result/<uuid>', defaults={'offset': 0})
@app.route('/result/<uuid>/<int:offset>')
def get_result(uuid, offset):
    key = "results:sessions:{0}".format(uuid)
    if not redis_store.exists(key):
        return jsonify(dict(uuid=uuid, state='expired'))

    rec = json.loads(redis_store.get(key))
    query_key = str(rec['redirect'])
    redis_store.expire(query_key, RESULT_TTL)
    result = map(json.loads, redis_store.lrange(query_key, offset + 0, offset + MAX_RESULTS - 1))
    next_offset = offset + MAX_RESULTS
    more_results = True if redis_store.llen(query_key) > offset + MAX_RESULTS else False
    return jsonify(dict(state='done', results=result, more_results=more_results,
                   next_offset=next_offset))


if __name__ == "__main__":
    app.run(debug=True)
