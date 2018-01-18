# !/usr/bin/env python3
# coding=utf-8
from __future__ import print_function
from __future__ import unicode_literals

import sys
import json
import os
import uuid

from dorina import run
from dorina.genome import Genome
from dorina.regulator import Regulator
from redis import Redis
import flask

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


def run_analyse(datadir, query_key, query_pending_key, query, uuid):
    app.logger.info('Running analysis for {}'.format(query_key))
    dorina = run.Dorina(datadir)

    redis_store = Redis(charset="utf-8", decode_responses=True)

    session_store = app.config['session_store'].format(unique_id=uuid)
    custom_regulator_file = '{session_store}/{uuid}.bed'.format(
        session_store=session_store, uuid=uuid)
    set_a = []
    for regulator in query['set_a']:
        if regulator == uuid:
            set_a.append(custom_regulator_file)
        else:
            set_a.append(regulator)
        query['set_a'] = set_a

    if query['set_b'] is not None:
        set_b = []
        for regulator in query['set_b']:
            if regulator == uuid:
                set_b.append(custom_regulator_file)
            else:
                set_b.append(regulator)
        query['set_b'] = set_b
    try:
        app.logger.debug('Storing analysis result for {}'.format(query_key))
        result = str(dorina.analyse(**query))
    except Exception as e:
        result = '\t\t\t\t\t\t\t\tJob failed: %s' % str(e).replace(
            '\n', ' ').replace('\t', ' ')

    lines = result.split('\n')
    if lines[-1] == '':
        lines = lines[:-1]

    def get_score(x):
        cols = x.split('\t')
        if len(cols) < 14:
            return -1
        try:
            return float(cols[13])
        except ValueError:
            return -1

    lines.sort(key=get_score, reverse=True)

    num_results = len(lines)
    app.logger.debug("returning {} rows".format(num_results))

    if num_results == 0:
        lines = ['\t\t\t\t\t\t\t\tNo results found']
        num_results += 1

    for i in range(0, num_results, 1000):
        res = lines[i:i + 1000]
        redis_store.rpush(query_key, *res)

    redis_store.expire(query_key, app.config['RESULT_TTL'])
    redis_store.setex('sessions:{0}'.format(uuid), json.dumps(dict(
        state='done', uuid=uuid)), app.config['SESSION_TTL'])
    redis_store.setex('results:sessions:{0}'.format(uuid), json.dumps(dict(
        redirect=query_key)), app.config['SESSION_TTL'])

    redis_store.delete(query_pending_key)


def _filter(genes, full_query_key, query_key, query_pending_key, uuid):
    """Filter for a given set of gene names"""
    redis_store = Redis(charset="utf-8", decode_responses=True)

    full_results = redis_store.lrange(full_query_key, 0, -1)
    results = []
    for res_string in full_results:
        if res_string == '':
            continue
        cols = res_string.split('\t')
        annotations = cols[8]
        for field in annotations.split(';'):
            key, val = field.split('=')
            if key == 'ID' and val in genes:
                results.append(res_string)

    num_results = len(results)
    if num_results == 0:
        results.append('\t\t\t\t\t\t\t\tNo results found')
        num_results += 1

    for i in range(0, num_results, 1000):
        res = results[i:i + 1000]
        redis_store.rpush(query_key, *res)

    redis_store.expire(query_key, app.config['RESULT_TTL'])
    redis_store.delete(query_pending_key)

    redis_store.setex('sessions:{0}'.format(uuid), json.dumps(dict(
        state='done', uuid=uuid)), app.config['SESSION_TTL'])
    redis_store.setex('results:sessions:{0}'.format(uuid), json.dumps(dict(
        redirect=query_key)), app.config['SESSION_TTL'])


if __name__ == "__main__":
    app.run(debug=app.config['DEBUG'], host=app.config['HOST'], port=app.config[
        'PORT'])
