#!/usr/bin/env python3
# coding=utf-8
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import json
from io import StringIO

import sys
from flask import (Flask, flash, render_template, jsonify, request, abort,
                   send_file, make_response)
from redis import Redis
from rq import Queue
import uuid

from dorina.genome import Genome
from dorina.regulator import Regulator
import run

# basic doRiNA settings
# load config.json if exists to overwrite settings
config_file = os.path.join(os.path.dirname(__file__), 'config.json')
conf = {}

# can be overwritten with config.json
if os.path.isfile(config_file):
    conf = json.load(open(config_file))

datadir = conf.get('datadir', os.path.join(
    os.path.dirname(__file__), 'test', 'data'))
# store results for 1 day
SESSION_TTL = conf.get('session_ttl', 3600)
RESULT_TTL = conf.get('result_ttl', 86400)
REGULATORS_TTL = conf.get('regulators_ttl', 3600)
MAX_RESULTS = conf.get('max_results', 100)
SESSION_STORE = conf.get('session_store', "/tmp/dorina-{unique_id}")
HOST = conf.get('host', '0.0.0.0')
PORT = conf.get('port', 5000)

# Initialise genomes and regulators once.

Genome.init(datadir)
Regulator.init(datadir)

app = Flask(__name__)

# generate session key
app.secret_key = os.urandom(24)
redis_store = Redis(charset="utf-8", decode_responses=True)
# assert redis is running
redis_store.ping()

log = logging.getLogger(__name__)
logging.captureWarnings(True)
logging.basicConfig(stream=sys.stderr, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s ')


@app.route('/')
def welcome():
    return render_template('welcome.html')


@app.route('/go', methods=['GET', 'POST'])
def index():
    custom_regulator = 'false'
    if request.method == 'POST':
        unique_id = _create_session(True)
        bedfile = request.files['bedfile']
        if bedfile and bedfile.filename.endswith('.bed'):
            filename = "{}.bed".format(unique_id)
            dirname = SESSION_STORE.format(unique_id=unique_id)
            bedfile.save(os.path.join(dirname, filename))
            custom_regulator = 'true'
        else:
            flash(u'Bedfile must end on ".bed"', 'error')
    else:
        unique_id = _create_session()

    genomes = json.dumps(_list_genomes())
    assemblies = json.dumps(_list_assemblies())
    return render_template('index.html', genomes=genomes,
                           assemblies=assemblies, uuid=unique_id,
                           custom_regulator=custom_regulator)


def _create_session(create_dir=False):
    unique_id = str(uuid.uuid4())
    session = "sessions:{0}".format(unique_id)
    session_dict = dict(uuid=unique_id, state='initialised')
    redis_store.setex(name=session,
                      value=json.dumps(session_dict),
                      time=SESSION_TTL)
    if create_dir:
        os.mkdir(SESSION_STORE.format(unique_id=unique_id))
    return unique_id


def _list_genomes():
    def without_assemblies(h):
        h1 = h.copy()
        del h1['assemblies']
        return h1


    # genome_list = [without_assemblies(x) for x in Genome.all().values()]
    genome_list = list(map(without_assemblies, Genome.all().values()))
    # genome_list.sort(key=lambda x, y: cmp(x['weight'], y['weight']),
    #                  reverse=True)
    return genome_list


def _list_assemblies():
    assemblies = []
    for g in list(Genome.all().values()):
        for key, val in list(g['assemblies'].items()):
            val['id'] = key
            val['weight'] = int(key[2:])
            val['genome'] = g['id']
            assemblies.append(val)

    return assemblies


@app.route('/api/v1.0/genomes')
def api_list_genomes():
    return jsonify(dict(genomes=_list_genomes()))


@app.route('/api/v1.0/assemblies/<genome>')
def api_list_assemblies(genome):
    assemblies = [x for x in _list_assemblies() if x['genome'] == genome]
    # assemblies.sort(lambda x, y: cmp(x['weight'], y['weight']), reverse=True)
    return jsonify(dict(assemblies=assemblies))


@app.route('/api/v1.0/regulators/<assembly>')
def list_regulators(assembly):
    cache_key = "regulators:{0}".format(assembly)
    if redis_store.exists(cache_key):
        regulators = json.loads(redis_store.get(cache_key))
    else:
        regulators = {}
        available_regulators = Regulator.all()
        for genome in available_regulators:
            if assembly in available_regulators[genome]:
                for key, val in list(
                        available_regulators[genome][assembly].items()):
                    regulators[key] = val

                redis_store.set(cache_key, json.dumps(regulators))
                redis_store.expire(cache_key, REGULATORS_TTL)

    return jsonify(regulators)


@app.route('/api/v1.0/genes/<assembly>', defaults={'query': ''})
@app.route('/api/v1.0/genes/<assembly>/<query>')
def list_genes(assembly, query):
    if query != '':
        start = "[{0}".format(query)
        end = "(" + start[1:-1] + chr(ord(start[-1]) + 1)
    else:
        start = "-"
        end = "+"

    cache_key = "genes:{0}".format(assembly)

    if not redis_store.exists(cache_key):
        new_genes = Genome.get_genes(assembly)
        for gene in new_genes:
            redis_store.zadd(cache_key, gene, 0)

    genes = redis_store.zrangebylex(cache_key, start, end)
    return jsonify(dict(genes=genes[:500]))


@app.route('/api/v1.0/status/<uuid>')
def status(uuid):
    key = "sessions:{0}".format(uuid)
    if redis_store.exists(key):
        status = json.loads(redis_store.get(key))
        status['ttl'] = redis_store.ttl(key)
    else:
        status = dict(uuid=uuid, state='expired')

    return jsonify(status)


@app.route('/api/v1.0/search', methods=['POST'])
def search():
    query = {}

    query['genes'] = request.form.getlist('genes[]')
    if query['genes'] == []:
        query['genes'] = [u'all']

    query['match_a'] = request.form.get('match_a', u'any')
    query['region_a'] = request.form.get('region_a', u'any')
    query['genome'] = request.form.get('assembly', None)
    query['set_a'] = request.form.getlist('set_a[]')
    offset = request.form.get('offset', 0, int)

    query['set_b'] = request.form.getlist('set_b[]')
    # werkzeug/Flask insists on returning an empty list, but dorina.analyse
    # expects 'None'
    if query['set_b'] == []:
        query['set_b'] = None
    query['match_b'] = request.form.get('match_b', u'any')
    query['region_b'] = request.form.get('region_b', u'any')
    query['combine'] = request.form.get('combinatorial_op', u'or')

    window_a = request.form.get('window_a', -1, int)
    if window_a > -1:
        query['window_a'] = window_a
    window_b = request.form.get('window_b', -1, int)
    if window_b > -1:
        query['window_b'] = window_b

    query_key = "results:%s" % json.dumps(query, sort_keys=True)
    query_pending_key = "%s_pending" % query_key

    print(query_key)

    unique_id = request.form.get('uuid', u'invalid')
    session = "sessions:{}".format(unique_id)
    if unique_id == 'invalid' or not redis_store.exists(session):
        unique_id = _create_session()
        session = "sessions:{}".format(unique_id)

    if redis_store.exists(query_key):
        session_dict = dict(uuid=unique_id, state='done')
        redis_store.expire(query_key, RESULT_TTL)
        redis_store.set(session, json.dumps(session_dict))
        redis_store.expire(session, SESSION_TTL)
        redis_store.set("results:{0}".format(session),
                        json.dumps(dict(redirect=query_key)))
        redis_store.expire("results:{0}".format(session), SESSION_TTL)
        return jsonify(session_dict)

    elif query['genes'][0] != u'all':
        full_query = dict(query)
        full_query['genes'] = [u'all']
        full_query_key = "results:%s" % json.dumps(full_query, sort_keys=True)

        if redis_store.exists(full_query_key):
            redis_store.expire(full_query_key, RESULT_TTL)
            redis_store.set(query_pending_key, True)
            redis_store.expire(query_pending_key, 30)
            session_dict = dict(state='pending', uuid=unique_id)
            redis_store.set('sessions:{0}'.format(unique_id),
                            json.dumps(session_dict))
            redis_store.expire('sessions:{0}'.format(unique_id), SESSION_TTL)
            q = Queue(connection=redis_store, default_timeout=600)
            q.enqueue(run.filter, query['genes'], full_query_key, query_key,
                      query_pending_key,
                      unique_id)
            return jsonify(session_dict)

    session_dict = dict(state='pending', uuid=unique_id)
    redis_store.set('sessions:{0}'.format(unique_id), json.dumps(session_dict))
    redis_store.expire('sessions:{0}'.format(unique_id), SESSION_TTL)

    if redis_store.get(query_pending_key):
        return jsonify(session_dict)

    redis_store.set(query_pending_key, True)
    redis_store.expire(query_pending_key, 30)

    q = Queue(connection=redis_store, default_timeout=600)
    q.enqueue(run.run_analyse, datadir, query_key, query_pending_key, query,
              unique_id)

    return jsonify(session_dict)


@app.route('/api/v1.0/result/<uuid>', defaults={'offset': 0})
@app.route('/api/v1.0/result/<uuid>/<int:offset>')
def get_result(uuid, offset):
    key = "results:sessions:{0}".format(uuid)
    if not redis_store.exists(key):
        return jsonify(dict(uuid=uuid, state='expired'))

    rec = json.loads(redis_store.get(key))
    query_key = str(rec['redirect'])
    redis_store.expire(query_key, RESULT_TTL)
    result = redis_store.lrange(query_key, offset + 0, offset + MAX_RESULTS - 1)
    next_offset = offset + MAX_RESULTS
    total_results = redis_store.llen(query_key)
    more_results = True if total_results > offset + MAX_RESULTS else False
    return jsonify(dict(state='done', results=result, more_results=more_results,
                        next_offset=next_offset, total_results=total_results))


@app.route('/api/v1.0/download/regulator/<assembly>/<name>')
def download_regulator(assembly, name):
    try:
        regulator = Regulator.from_name(name, assembly)
    except:
        return abort(404)

    return send_file(regulator.path, as_attachment=True)


@app.route('/api/v1.0/download/results/<uuid>')
def download_results(uuid):
    key = "results:sessions:{0}".format(uuid)
    if not redis_store.exists(key):
        abort(404)

    result_key = json.loads(redis_store.get(key))['redirect']
    results = redis_store.lrange(result_key, 0, -1)

    out = StringIO()
    for res in results:
        out.write("{}\n".format(res))

    response = make_response(out.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=dorina.tsv"
    return response


def _dict_to_bed(data):
    '''Convert dorina dict to BED format'''
    chrom, coords = data['location'].split(':')
    start, end = coords.split('-')

    data['chrom'] = chrom
    data['start'] = start
    data['end'] = end

    return "{chrom}\t{start}\t{end}\t{data_source}#{track}*{site}\t{score}\t{strand}".format(
        **data)


@app.route('/news')
def news():
    return render_template('news.html')


@app.route('/tutorials')
def tutorials():
    return render_template('tutorials.html')


@app.route('/docs')
def docs():
    return render_template('api_docs.html')


@app.route('/help')
def help():
    return render_template('api_docs.html')


@app.route('/acknowledgements')
def acknowledgements():
    return render_template('acknowledgements.html')


@app.route('/regulators')
def regulators():

    return render_template('regulators.html')


@app.route('/docs/api/<page>')
def docs_api(page):
    return render_template('api_{}.html'.format(page))


if __name__ == "__main__":
    app.run(debug=True, host=HOST, port=PORT)  # TODO this is not  right for production
