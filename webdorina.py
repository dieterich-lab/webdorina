#!/usr/bin/env python

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
RESULT_TTL = 60
MAX_RESULTS = 100

app = Flask(__name__)
redis_store = Redis(app)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/clades')
def list_clades():
    available_genomes = utils.get_genomes(datadir=datadir)
    clades = available_genomes.keys()
    return jsonify(dict(clades=clades))


@app.route('/genomes/<clade>')
def list_genomes(clade):
    available_genomes = utils.get_genomes(datadir=datadir)
    if not clade in available_genomes:
        return jsonify(dict(clade=''))
    genomes = available_genomes[clade].keys()
    genomes.sort()
    return jsonify(dict(clade=clade, genomes=genomes))


@app.route('/assemblies/<clade>/<genome>')
def list_assemblies(clade, genome):
    available_genomes = utils.get_genomes(datadir=datadir)
    if not clade in available_genomes:
        return jsonify(dict(clade=''))
    if not genome in available_genomes[clade]:
        return jsonify(dict(clade=clade, genome=''))
    assemblies = available_genomes[clade][genome].keys()
    assemblies.sort()
    return jsonify(dict(clade=clade, genome=genome, assemblies=assemblies))


@app.route('/regulators/<clade>/<genome>/<assembly>')
def list_regulators(clade, genome, assembly):

    cache_key = "regulators:{0}:{1}:{2}".format(clade,genome,assembly)
    if redis_store.exists(cache_key):
        regulators = json.loads(redis_store.get(cache_key))
    else:
        available_regulators = utils.get_regulators(datadir=datadir)
        if not clade in available_regulators:
            return jsonify(dict(clade=''))
        if not genome in available_regulators[clade]:
            return jsonify(dict(clade=clade, genome=''))
        if not assembly in available_regulators[clade][genome]:
            return jsonify(dict(clade=clade, genome=genome, assembly=''))

        regulators = {}
        for key, val in available_regulators[clade][genome][assembly].items():
            regulators[key] = val


        redis_store.set(cache_key, json.dumps(regulators))
        redis_store.expire(cache_key, 3600)

    return jsonify(regulators)


@app.route('/search', methods=['POST'])
def search():
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
        redis_store.expire(query_key, RESULT_TTL)
        result = map(json.loads, redis_store.lrange(query_key, offset + 0, offset + MAX_RESULTS - 1))
        next_offset = offset + MAX_RESULTS
        more_results = True if redis_store.llen(query_key) > offset + MAX_RESULTS else False
        return jsonify(dict(state='done', results=result, more_results=more_results,
                       next_offset=next_offset))
    elif query['genes'][0] != u'all':
        full_query = dict(query)
        full_query['genes'] = [u'all']
        full_query_key = "results:%s" % json.dumps(full_query, sort_keys=True)
        full_query_pending_key = "%s_pending" % full_query_key

        if redis_store.exists(full_query_key):
            redis_store.expire(full_query_key, RESULT_TTL)
            redis_store.set(query_pending_key, True)
            redis_store.expire(query_pending_key, 30)
            q = Queue(connection=redis_store.connection)
            q.enqueue(run.filter, query['genes'], full_query_key, query_key, query_pending_key)
            return jsonify(dict(state='pending'))

        query = full_query
        query_key = full_query_key
        query_pending_key = full_query_pending_key

    if redis_store.get(query_pending_key):
        return jsonify(dict(state='pending'))

    redis_store.set(query_pending_key, True)
    redis_store.expire(query_pending_key, 30)

    q = Queue(connection=redis_store.connection)
    q.enqueue(run.run_analyse, datadir, query_key, query_pending_key, query)

    return jsonify(dict(state='pending'))


if __name__ == "__main__":
    app.run(debug=True)
