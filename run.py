import json
from redis import Redis
from dorina.run import analyse

def run_analyse(datadir, query_key, query_pending_key, query):
    redis_store = Redis()
    result = analyse(datadir=datadir, **query)
    result.sort(key=lambda x: x['score'], reverse=True)

    print "returning %s rows" % len(result)

    if len(result) < 1:
        result.append({
            'data_source': 'no results found',
            'score': -1,
            'track': '',
            'gene': '',
            'site': '',
            'strand': '',
            'location': ''
        })

    for res in result:
        redis_store.rpush(query_key, json.dumps(res))


    redis_store.expire(query_key, 60)

    redis_store.delete(query_pending_key)
