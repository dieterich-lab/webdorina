import json
from redis import Redis
from dorina.run import analyse
import time

def run_analyse(datadir, query_key, query_pending_key, query, uuid, timeit=False):
    from webdorina import RESULT_TTL, SESSION_TTL, SESSION_STORE
    redis_store = Redis()

    if timeit:
        started = time.time()

    session_store = SESSION_STORE.format(unique_id=uuid)
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
        result = analyse(datadir=datadir, **query)
    except Exception as e:
        result = [{
            'data_source': 'Job failed: %s' % e,
            'score': -1,
            'track': '',
            'gene': '',
            'site': '',
            'strand': '',
            'location': ''
        }]


    if timeit:
        analysed = time.time()
        print "analyse() ran {} seconds".format(analysed - started)

    result.sort(key=lambda x: x['score'], reverse=True)

    if timeit:
        sorted_time = time.time()
        print "sort() ran {} seconds".format(sorted_time - analysed)

    num_results = len(result)
    print "returning %s rows" % num_results

    if num_results < 1:
        result.append({
            'data_source': 'no results found',
            'score': -1,
            'track': '',
            'gene': '',
            'site': '',
            'strand': '',
            'location': ''
        })
        num_results += 1

    json_results = map(json.dumps, result)

    if timeit:
        json_time = time.time()
        print "json.dumps ran {} seconds".format(json_time - sorted_time)

    for i in xrange(0, num_results, 1000):
        res = json_results[i:i+1000]
        redis_store.rpush(query_key, *res)


    redis_store.expire(query_key, RESULT_TTL)
    redis_store.setex('sessions:{0}'.format(uuid), json.dumps(dict(state='done', uuid=uuid)), SESSION_TTL)
    redis_store.setex('results:sessions:{0}'.format(uuid), json.dumps(dict(redirect=query_key)), SESSION_TTL)

    redis_store.delete(query_pending_key)
    if timeit:
        pushed = time.time()
        print "push() ran {} seconds".format(pushed - json_time)
        print "total time taken: {} seconds".format(pushed - started)


def filter(genes, full_query_key, query_key, query_pending_key, uuid):
    """Filter for a given set of gene names"""
    from webdorina import RESULT_TTL, SESSION_TTL
    redis_store = Redis()

    full_results = redis_store.lrange(full_query_key, 0, -1)
    for res_string in full_results:
        res = json.loads(res_string)
        if res['gene'] in genes:
            redis_store.rpush(query_key, json.dumps(res))

    redis_store.expire(query_key, RESULT_TTL)
    redis_store.delete(query_pending_key)

    redis_store.setex('sessions:{0}'.format(uuid), json.dumps(dict(state='done', uuid=uuid)), SESSION_TTL)
    redis_store.setex('results:sessions:{0}'.format(uuid), json.dumps(dict(redirect=query_key)), SESSION_TTL)
