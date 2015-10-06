import json
from redis import Redis
import time
from dorina import run

def run_analyse(datadir, query_key, query_pending_key, query, uuid, timeit=False):
    dorina = run.Dorina(datadir)

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
        result = str(dorina.analyse(**query))
    except Exception as e:
        result = '\t\t\t\t\t\t\t\tJob failed: %s' % str(e).replace('\n', ' ').replace('\t', ' ')

    if timeit:
        analysed = time.time()
        print "analyse() ran {} seconds".format(analysed - started)

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

    if timeit:
        sorted_time = time.time()
        print "sort() ran {} seconds".format(sorted_time - analysed)

    num_results = len(lines)
    print "returning %s rows" % num_results

    if num_results == 0:
        lines = ['\t\t\t\t\t\t\t\tNo results found']
        num_results += 1

    for i in xrange(0, num_results, 1000):
        res = lines[i:i+1000]
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

    for i in xrange(0, num_results, 1000):
        res = results[i:i+1000]
        redis_store.rpush(query_key, *res)

    redis_store.expire(query_key, RESULT_TTL)
    redis_store.delete(query_pending_key)

    redis_store.setex('sessions:{0}'.format(uuid), json.dumps(dict(state='done', uuid=uuid)), SESSION_TTL)
    redis_store.setex('results:sessions:{0}'.format(uuid), json.dumps(dict(redirect=query_key)), SESSION_TTL)
