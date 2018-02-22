# !/usr/bin/env python3
# coding=utf-8
from __future__ import print_function
from __future__ import unicode_literals

import json
import os
import sys
import uuid
from io import StringIO

import flask
from dorina.genome import Genome
from dorina.regulator import Regulator
from redis import Redis
from rq import Queue

from webdorina.workers import filter_genes, run_analyse

this_dir = os.path.dirname(os.path.abspath(__file__))
app = flask.Flask('webdorina',
                  template_folder=os.path.join(this_dir, 'templates'),
                  static_folder=os.path.join(this_dir, 'static'))
app.secret_key = os.urandom(24)
app.config.from_pyfile(os.path.join(this_dir, 'config.py'))
try:
    user_config = app.config.from_pyfile(sys.argv[1])
except FileNotFoundError:
    msg = 'Using app defaults, please provide a valid config file'
    app.logger.warn(msg)
except IndexError:
    msg = 'webdorina/app.py receives a optional parameter, a Flask ' \
          'configuration file. Please see example_user_config.py'
    app.logger.warn(msg)

redis_store = Redis(charset="utf-8", decode_responses=True)
# assert redis is running
redis_store.ping()

Genome.init(app.config['DATA_PATH'])
Regulator.init(app.config['DATA_PATH'])


def _create_session(create_dir=False):
    unique_id = str(uuid.uuid4())
    session = "sessions:{0}".format(unique_id)
    session_dict = dict(uuid=unique_id, state='initialised')
    redis_store.setex(name=session,
                      value=json.dumps(session_dict),
                      time=app.config['SESSION_TTL'])
    if create_dir:
        os.mkdir(app.config['SESSION_STORE'].format(unique_id=unique_id))
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


def _dict_to_bed(data):
    """Convert dorina dict to BED format"""
    chrom, coords = data['location'].split(':')
    start, end = coords.split('-')

    data['chrom'] = chrom
    data['start'] = start
    data['end'] = end

    return "{chrom}\t{start}\t{end}\t{data_source}#{track}*{site}\t{score}\t{strand}".format(
        **data)


@app.route('/')
def welcome():
    return flask.render_template('welcome.html')


@app.route('/go', methods=['GET', 'POST'])
def index():
    custom_regulator = 'false'
    if flask.request.method == 'POST':
        unique_id = _create_session(True)
        bedfile = flask.request.files['bedfile']
        if bedfile and bedfile.filename.endswith('.bed'):
            filename = "{}.bed".format(unique_id)
            dirname = app.config['SESSION_STORE'].format(unique_id=unique_id)
            bedfile.save(os.path.join(dirname, filename))
            custom_regulator = 'true'
            flask.flash(u'File loaded"', 'success')
        else:
            flask.flash(u'The file must end on ".bed"', 'danger')
            return flask.render_template('welcome.html')
    else:
        unique_id = _create_session()

    genomes = json.dumps(_list_genomes())
    assemblies = json.dumps(_list_assemblies())
    return flask.render_template('index.html', genomes=genomes,
                                 assemblies=assemblies, uuid=unique_id,
                                 custom_regulator=custom_regulator)


@app.route('/api/v1.0/status/<uuid>')
def status(uuid):
    # uuid here shadows global uuid var,
    # but it seems a feature, not a bug
    key = "sessions:{0}".format(uuid)
    if redis_store.exists(key):
        _status = json.loads(redis_store.get(key))
        _status['ttl'] = redis_store.ttl(key)
    else:
        _status = dict(uuid=uuid, state='expired')

    return flask.jsonify(_status)


@app.route('/api/v1.0/search', methods=['POST'])
def search():
    query = {'genes': flask.request.form.getlist('genes[]')}

    if not query['genes']:
        query['genes'] = [u'all']

    query['match_a'] = flask.request.form.get('match_a', u'any')
    query['region_a'] = flask.request.form.get('region_a', u'any')
    query['genome'] = flask.request.form.get('assembly', None)
    query['set_a'] = flask.request.form.getlist('set_a[]')
    # offset = request.form.get('offset', 0, int)

    query['set_b'] = flask.request.form.getlist('set_b[]')
    # werkzeug/Flask insists on returning an empty list, but dorina.analyse
    # expects 'None'
    if not query['set_b']:
        query['set_b'] = None
    query['match_b'] = flask.request.form.get('match_b', u'any')
    query['region_b'] = flask.request.form.get('region_b', u'any')
    query['combine'] = flask.request.form.get('combinatorial_op', u'or')

    window_a = flask.request.form.get('window_a', -1, int)
    if window_a > -1:
        query['window_a'] = window_a
    window_b = flask.request.form.get('window_b', -1, int)
    if window_b > -1:
        query['window_b'] = window_b

    query_key = "results:%s" % json.dumps(query, sort_keys=True)
    query_pending_key = "%s_pending" % query_key

    print(query_key)

    unique_id = flask.request.form.get('uuid', u'invalid')
    session = "sessions:{}".format(unique_id)
    if unique_id == 'invalid' or not redis_store.exists(session):
        unique_id = _create_session()
        session = "sessions:{}".format(unique_id)

    if redis_store.exists(query_key):
        session_dict = dict(uuid=unique_id, state='done')
        redis_store.expire(query_key, app.config['RESULT_TTL'])
        redis_store.set(session, json.dumps(session_dict))
        redis_store.expire(session, app.config['SESSION_TTL'])
        redis_store.set("results:{0}".format(session),
                        json.dumps(dict(redirect=query_key)))
        redis_store.expire("results:{0}".format(session),
                           app.config['SESSION_TTL'])
        return flask.jsonify(session_dict)

    elif query['genes'][0] != u'all':
        full_query = dict(query)
        full_query['genes'] = [u'all']
        full_query_key = "results:%s" % json.dumps(full_query, sort_keys=True)

        if redis_store.exists(full_query_key):
            redis_store.expire(full_query_key, app.config['RESULT_TTL'])
            redis_store.set(query_pending_key, True)
            redis_store.expire(query_pending_key, 30)
            session_dict = dict(state='pending', uuid=unique_id)
            redis_store.set('sessions:{0}'.format(unique_id),
                            json.dumps(session_dict))
            redis_store.expire(
                'sessions:{0}'.format(unique_id), app.config['SESSION_TTL'])
            q = Queue(connection=redis_store, default_timeout=600)

            q.enqueue(filter_genes, query['genes'], full_query_key, query_key,
                      query_pending_key, unique_id,
                      SESSION_TTL=app.config['SESSION_TTL'],
                      RESULT_TTL=app.config['RESULT_TTL'])
            return flask.jsonify(session_dict)

    session_dict = dict(state='pending', uuid=unique_id)
    redis_store.set('sessions:{0}'.format(unique_id), json.dumps(session_dict))
    redis_store.expire('sessions:{0}'.format(unique_id),
                       app.config['SESSION_TTL'])

    if redis_store.get(query_pending_key):
        return flask.jsonify(session_dict)

    redis_store.set(query_pending_key, True)
    redis_store.expire(query_pending_key, 30)

    q = Queue(connection=redis_store, default_timeout=600)
    q.enqueue(run_analyse, app.config['DATA_PATH'], query_key,
              query_pending_key, query, unique_id,
              SESSION_STORE=app.config['SESSION_STORE'],
              RESULT_TTL=app.config['RESULT_TTL'],
              SESSION_TTL=app.config['SESSION_TTL'])

    return flask.jsonify(session_dict)


@app.route('/api/v1.0/download/regulator/<assembly>/<name>')
def download_regulator(assembly, name):
    try:
        regulator = Regulator.from_name(name, assembly)
    except Exception as e:
        app.logger.error(e, assembly, name)
        return flask.abort(404)

    return flask.send_file(regulator.path, as_attachment=True)


@app.route('/api/v1.0/download/results/<uuid>')
def download_results(uuid):
    key = "results:sessions:{0}".format(uuid)
    if not redis_store.exists(key):
        flask.abort(404)

    result_key = json.loads(redis_store.get(key))['redirect']
    results = redis_store.lrange(result_key, 0, -1)

    out = StringIO()
    for res in results:
        out.write("{}\n".format(res))

    response = flask.make_response(out.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=dorina.tsv"
    return response


@app.route('/news')
def news():
    return flask.render_template('news.html')


@app.route('/tutorials')
def tutorials():
    return flask.render_template('tutorials.html')


@app.route('/docs')
def docs():
    return flask.render_template('api_docs.html')


@app.route('/acknowledgements')
def acknowledgements():
    return flask.render_template('acknowledgements.html')


@app.route('/regulators')
def regulators():
    return flask.render_template('regulators.html')


@app.route('/docs/api/<page>')
def docs_api(page):
    return flask.render_template('api_{}.html'.format(page))


@app.route('/api/v1.0/genomes')
def api_list_genomes():
    return flask.jsonify(dict(genomes=_list_genomes()))


@app.route('/api/v1.0/assemblies/<genome>')
def api_list_assemblies(genome):
    assemblies = [x for x in _list_assemblies() if x['genome'] == genome]
    # assemblies.sort(lambda x, y: cmp(x['weight'], y['weight']), reverse=True)
    return flask.jsonify(dict(assemblies=assemblies))


@app.route('/api/v1.0/regulators/<assembly>')
def list_regulators(assembly):
    cache_key = "regulators:{0}".format(assembly)
    if redis_store.exists(cache_key):
        regulators_ = json.loads(redis_store.get(cache_key))
    else:
        regulators_ = {}
        available_regulators = Regulator.all()
        for genome in available_regulators:
            if assembly in available_regulators[genome]:
                for key, val in list(
                        available_regulators[genome][assembly].items()):
                    regulators_[key] = val

                redis_store.set(cache_key, json.dumps(regulators_))
                redis_store.expire(cache_key, app.config['REGULATORS_TTL'])

    return flask.jsonify(regulators_)


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
    return flask.jsonify(dict(genes=genes[:500]))


@app.route('/api/v1.0/result/<uuid>', defaults={'offset': 0})
@app.route('/api/v1.0/result/<uuid>/<int:offset>')
def get_result(uuid, offset):
    key = "results:sessions:{0}".format(uuid)
    if not redis_store.exists(key):
        return flask.jsonify(dict(uuid=uuid, state='expired'))

    rec = json.loads(redis_store.get(key))
    query_key = str(rec['redirect'])
    redis_store.expire(query_key, app.config['RESULT_TTL'])
    result = redis_store.lrange(
        query_key, offset + 0, offset + app.config['MAX_RESULTS'] - 1)
    next_offset = offset + app.config['MAX_RESULTS']
    total_results = redis_store.llen(query_key)
    more_results = True if total_results > offset + app.config[
        'MAX_RESULTS'] else False
    return flask.jsonify(
        dict(state='done', results=result, more_results=more_results,
             next_offset=next_offset, total_results=total_results))


if __name__ == "__main__":
    app.run(debug=app.config['DEBUG'], host=app.config['HOST'], port=app.config[
        'PORT'])
